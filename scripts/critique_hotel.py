#!/usr/bin/env python3
"""
Vision model critique loop for hotel style quality.

Renders a hotel style, sends images to a multimodal LLM for structured
feedback, and reports scores + actionable improvement suggestions.

The agent uses this to iteratively improve style implementations:
  1. Generate + render hotel
  2. Send to vision model for critique
  3. If score < 4.0, read suggestions and modify code
  4. Repeat (max 3 iterations)

Usage:
    python scripts/critique_hotel.py --style modern --seed 42
    python scripts/critique_hotel.py --style victorian --threshold 3.5

Environment:
    ANTHROPIC_API_KEY   (required)
    PYOPENGL_PLATFORM=osmesa  (required for headless rendering)
"""
import argparse
import base64
import json
import os
import sys
from pathlib import Path

# Must be set before any OpenGL import
if "PYOPENGL_PLATFORM" not in os.environ:
    os.environ["PYOPENGL_PLATFORM"] = "osmesa"


STYLE_MARKERS = {
    "modern": "flat roof, horizontal window bands, clean rectangular geometry, possible cantilever or penthouse box",
    "art_deco": "stepped/ziggurat profile (each tier smaller than below), vertical fins, geometric crown at top, symmetric facade",
    "classical": "triangular pediment above entrance, columns or pilasters, symmetrical facade, horizontal cornice, entablature",
    "victorian": "asymmetric L-shaped plan, round turret with conical cap, bay windows protruding from wall, complex roofline with multiple gables",
    "mediterranean": "barrel or hip roof with deep eaves, arched windows (resin) or rectangular (FDM), thick walls, possible courtyard (U-shape)",
    "tropical": "deep overhanging eaves with angled supports underneath, raised on stilts/columns, multi-tier roof layers",
    "skyscraper": "tall slender tower rising from wider podium base, crown/spire element at top, dense regular window grid",
    "townhouse": "narrow and tall rectangle, mansard roof (steep lower + shallow upper), front stoop with 2-3 steps, bay window projection",
}

CRITIQUE_PROMPT = """You are reviewing rendered images of a 3D model of a miniature hotel game piece
(Monopoly-scale, approximately 1-2cm tall). The hotel is in the "{style_name}" architectural style.

These images show the same model from multiple camera angles.

Evaluate the following and score each 1-5 (5 = excellent):

1. **Style Recognition** (1-5): Does this clearly look like a {style_name} building?
   Would someone familiar with architecture identify the style at a glance?
   Key markers to look for: {style_markers}

2. **Silhouette Distinctiveness** (1-5): Is the overall shape distinctive?
   Would you recognize this as different from a plain rectangular box?
   Look at the roofline, massing, and any protruding elements.

3. **Hotel-ness** (1-5): Does this look like a hotel specifically (not a house, office,
   or church)? Hotels should have: multiple floors with repeated window patterns,
   a clear entrance on the ground floor, commercial-scale proportions.

4. **Printability Assessment** (1-5): Visually, does the geometry look clean and solid?
   Are there any obviously thin/fragile elements, impossible overhangs, or disconnected
   floating parts? Remember this is ~15mm tall.

5. **Aesthetic Quality** (1-5): Is the overall design pleasing? Good proportions?
   Balanced detail? Does it look like a well-crafted game piece?

For each category scoring below 4, provide a SPECIFIC, ACTIONABLE suggestion for
improvement. Reference concrete geometric changes (e.g., "make the roof overhang
wider by 0.5mm", "add 2 more window rows", "the turret diameter should be 30% larger").

Respond in valid JSON only (no markdown code fences):
{{
  "scores": {{
    "style_recognition": 0,
    "silhouette_distinctiveness": 0,
    "hotel_ness": 0,
    "printability": 0,
    "aesthetic_quality": 0
  }},
  "overall_score": 0.0,
  "improvements": [
    {{
      "category": "category_name",
      "problem": "what is wrong",
      "suggestion": "specific geometric change to make"
    }}
  ],
  "pass": false
}}

Set "pass" to true only if overall_score >= {threshold}.
"""

GRID_CRITIQUE_PROMPT = """These are 8 different architectural styles of miniature hotel game pieces,
rendered from the same 3/4 front angle. They are arranged in a 2x4 grid:

Top row (L to R): Modern, Art Deco, Classical, Victorian
Bottom row (L to R): Mediterranean, Tropical, Skyscraper, Townhouse

Evaluate:
1. Can you distinguish each style from its neighbors? (score 1-5 for each)
2. Which pairs look too similar? List them.
3. For each pair that looks too similar, suggest a specific geometric change
   to one of them to increase distinctiveness.
4. Are any styles unrecognizable as their intended architectural style? Which ones, and why?
5. Do all of them read as "hotels" (multiple floors, commercial scale, entrance)?

Respond in valid JSON only (no markdown code fences):
{{
  "per_style_scores": {{
    "modern": 0, "art_deco": 0, "classical": 0, "victorian": 0,
    "mediterranean": 0, "tropical": 0, "skyscraper": 0, "townhouse": 0
  }},
  "confusable_pairs": [
    {{
      "style_a": "name",
      "style_b": "name",
      "change_to": "which style to modify",
      "recommendation": "specific geometric change"
    }}
  ],
  "unrecognizable": [
    {{
      "style": "name",
      "problem": "why it fails",
      "fix": "what to change"
    }}
  ],
  "distinct_count": 0,
  "overall_pass": false
}}
"""


def critique_images(
    image_paths: list[str],
    style_name: str,
    threshold: float = 3.5,
    model: str = "claude-sonnet-4-20250514",
) -> dict:
    """Send rendered images to a vision model for structured critique."""
    try:
        import anthropic
    except ImportError:
        print("ERROR: critique requires the anthropic package.")
        print("Install with: pip install anthropic")
        sys.exit(1)

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("WARNING: ANTHROPIC_API_KEY not set. Returning placeholder scores.")
        print("  Set ANTHROPIC_API_KEY to enable vision model critique.")
        return {
            "scores": {
                "style_recognition": 3,
                "silhouette_distinctiveness": 3,
                "hotel_ness": 3,
                "printability": 3,
                "aesthetic_quality": 3,
            },
            "overall_score": 3.0,
            "improvements": [
                {
                    "category": "setup",
                    "problem": "No API key available for vision model critique",
                    "suggestion": "Set ANTHROPIC_API_KEY to enable automated visual feedback",
                }
            ],
            "pass": False,
        }

    client = anthropic.Anthropic()

    # Build message content with images
    content = []
    for path in image_paths:
        with open(path, "rb") as f:
            img_data = base64.standard_b64encode(f.read()).decode("utf-8")
        content.append({
            "type": "image",
            "source": {"type": "base64", "media_type": "image/png", "data": img_data},
        })

    content.append({
        "type": "text",
        "text": CRITIQUE_PROMPT.format(
            style_name=style_name,
            style_markers=STYLE_MARKERS.get(style_name, "general architectural features"),
            threshold=threshold,
        ),
    })

    response = client.messages.create(
        model=model,
        max_tokens=2000,
        messages=[{"role": "user", "content": content}],
    )

    # Parse JSON response
    response_text = response.content[0].text
    # Strip markdown code fences if present
    if response_text.startswith("```"):
        lines = response_text.split("\n")
        response_text = "\n".join(lines[1:-1])

    return json.loads(response_text)


def critique_grid(
    grid_path: str,
    model: str = "claude-sonnet-4-20250514",
) -> dict:
    """Send a style comparison grid to a vision model for distinctiveness check."""
    try:
        import anthropic
    except ImportError:
        print("ERROR: critique requires the anthropic package.")
        sys.exit(1)

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("WARNING: ANTHROPIC_API_KEY not set. Returning placeholder result.")
        return {
            "per_style_scores": {s: 3 for s in STYLE_MARKERS},
            "confusable_pairs": [],
            "unrecognizable": [],
            "distinct_count": 0,
            "overall_pass": False,
        }

    client = anthropic.Anthropic()

    with open(grid_path, "rb") as f:
        img_data = base64.standard_b64encode(f.read()).decode("utf-8")

    response = client.messages.create(
        model=model,
        max_tokens=2000,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": img_data}},
                {"type": "text", "text": GRID_CRITIQUE_PROMPT},
            ],
        }],
    )

    response_text = response.content[0].text
    if response_text.startswith("```"):
        lines = response_text.split("\n")
        response_text = "\n".join(lines[1:-1])

    return json.loads(response_text)


def run_critique_loop(
    style_name: str,
    seed: int = 42,
    printer_type: str = "fdm",
    threshold: float = 3.5,
    max_iterations: int = 3,
    output_dir: str = "renders",
) -> dict:
    """
    Full render-critique loop for a single style.

    Returns the final critique result with iteration history.
    The agent should read the 'improvements' list and modify the
    style code accordingly between iterations.
    """
    from scripts.render_hotel import generate_and_render

    history = []

    for iteration in range(max_iterations):
        print(f"\n--- Iteration {iteration + 1}/{max_iterations} for {style_name} ---\n")

        # Render
        iter_dir = f"{output_dir}/{style_name}_iter{iteration}"
        image_paths = generate_and_render(
            style_name=style_name,
            seed=seed,
            printer_type=printer_type,
            output_dir=iter_dir,
        )

        # Critique
        print(f"\nSending to vision model for critique...")
        critique = critique_images(image_paths, style_name, threshold)
        history.append(critique)

        # Report
        scores = critique["scores"]
        print(f"\nScores (iteration {iteration + 1}):")
        for k, v in scores.items():
            status = "OK" if v >= 4 else "NEEDS WORK"
            print(f"  {k}: {v}/5 [{status}]")
        print(f"  Overall: {critique['overall_score']:.1f}/5")
        print(f"  Pass: {critique['pass']}")

        if critique["improvements"]:
            print(f"\nImprovements needed:")
            for imp in critique["improvements"]:
                print(f"  [{imp['category']}] {imp['problem']}")
                print(f"    -> {imp['suggestion']}")

        if critique["pass"] and critique["overall_score"] >= 4.0:
            print(f"\nStyle {style_name} PASSED at iteration {iteration + 1}")
            return {
                "status": "pass",
                "iterations": iteration + 1,
                "final_score": critique["overall_score"],
                "history": history,
            }

        if iteration < max_iterations - 1:
            print(f"\n>>> Agent should now modify styles/{style_name}.py based on")
            print(f">>> the improvements above, then re-run this script. <<<")
            # In autonomous mode, the agent reads the improvements,
            # modifies the code, and re-runs. This script exits here
            # so the agent can act on the feedback.
            break

    final = history[-1]
    if not final["pass"]:
        print(f"\nStyle {style_name} did NOT pass after {len(history)} iteration(s).")
        print("Consider: manual review or different approach.")

    return {
        "status": "pass" if final["pass"] else "needs_review",
        "iterations": len(history),
        "final_score": final["overall_score"],
        "history": history,
    }


def main():
    parser = argparse.ArgumentParser(description="Vision model critique for hotel styles")
    parser.add_argument("--style", required=True, help="Style name (e.g., modern, victorian)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--printer", default="fdm", choices=["fdm", "resin"])
    parser.add_argument("--threshold", type=float, default=3.5, help="Minimum passing score")
    parser.add_argument("--output", default="renders", help="Output directory")
    parser.add_argument("--grid", help="Path to style grid image for distinctiveness critique")
    parser.add_argument("--model", default="claude-sonnet-4-20250514", help="Vision model to use")
    args = parser.parse_args()

    if args.grid:
        print(f"Critiquing style grid: {args.grid}")
        result = critique_grid(args.grid, model=args.model)
        print(json.dumps(result, indent=2))
    else:
        result = run_critique_loop(
            style_name=args.style,
            seed=args.seed,
            printer_type=args.printer,
            threshold=args.threshold,
            output_dir=args.output,
        )
        # Save result
        result_path = Path(args.output) / f"{args.style}_critique.json"
        result_path.write_text(json.dumps(result, indent=2))
        print(f"\nCritique saved to {result_path}")


if __name__ == "__main__":
    main()
