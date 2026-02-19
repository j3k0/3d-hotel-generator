#!/usr/bin/env python3
"""
Render all 8 styles in a 2x4 comparison grid.

Used for visual distinctiveness checking -- all styles at the same angle,
same scale, same lighting, laid out side by side. The resulting grid can
be sent to a vision model for cross-style comparison.

Usage:
    PYOPENGL_PLATFORM=osmesa python scripts/render_style_grid.py
    PYOPENGL_PLATFORM=osmesa python scripts/render_style_grid.py --output renders/grid.png
    PYOPENGL_PLATFORM=osmesa python scripts/render_style_grid.py --critique

Environment:
    PYOPENGL_PLATFORM=osmesa  (required for headless rendering)
"""
import argparse
import os
import sys
from pathlib import Path

if "PYOPENGL_PLATFORM" not in os.environ:
    os.environ["PYOPENGL_PLATFORM"] = "osmesa"

ALL_STYLES = [
    # Row 1
    "modern", "art_deco", "classical", "victorian",
    # Row 2
    "mediterranean", "tropical", "skyscraper", "townhouse",
]


def render_style_grid(
    output_path: str = "renders/style_grid.png",
    cell_resolution: int = 512,
    seed: int = 42,
    printer_type: str = "resin",
) -> str:
    """
    Generate all 8 styles and render them in a 2x4 grid.
    Returns path to the grid image.
    """
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        print("ERROR: Grid rendering requires Pillow. Install with: pip install Pillow")
        sys.exit(1)

    sys.path.insert(0, str(Path(__file__).parent))
    from render_hotel import render_manifold_to_images
    from hotel_generator.assembly.building import HotelBuilder
    from hotel_generator.config import BuildingParams
    from hotel_generator.settings import Settings

    builder = HotelBuilder(Settings())
    cell_images = []
    tmp_dir = Path(output_path).parent / "grid_tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    # Single angle for comparison: 3/4 front view
    angles = [(45, 30, "grid")]

    for style in ALL_STYLES:
        print(f"Generating {style}...")
        params = BuildingParams(
            style_name=style,
            width=8.0,
            depth=6.0,
            num_floors=4,
            floor_height=0.8,
            printer_type=printer_type,
            seed=seed,
        )
        result = builder.build(params)

        paths = render_manifold_to_images(
            result.manifold,
            output_dir=str(tmp_dir),
            style_name=style,
            resolution=(cell_resolution, cell_resolution),
            angles=angles,
        )
        cell_images.append(Image.open(paths[0]))

    # Assemble 2x4 grid
    cols, rows = 4, 2
    label_height = 30
    grid_w = cols * cell_resolution
    grid_h = rows * (cell_resolution + label_height)
    grid = Image.new("RGB", (grid_w, grid_h), (255, 255, 255))
    draw = ImageDraw.Draw(grid)

    for i, (img, style) in enumerate(zip(cell_images, ALL_STYLES)):
        row, col = divmod(i, cols)
        x = col * cell_resolution
        y = row * (cell_resolution + label_height)

        # Paste render
        grid.paste(img, (x, y))

        # Add label below
        label_y = y + cell_resolution + 5
        label = style.replace("_", " ").title()
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 16)
        except (OSError, IOError):
            font = ImageFont.load_default()
        bbox = draw.textbbox((0, 0), label, font=font)
        text_w = bbox[2] - bbox[0]
        draw.text((x + (cell_resolution - text_w) // 2, label_y), label, fill=(0, 0, 0), font=font)

    # Save
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    grid.save(output)
    print(f"\nStyle grid saved to {output}")

    # Cleanup temp files
    for f in tmp_dir.iterdir():
        f.unlink()
    tmp_dir.rmdir()

    return str(output)


def main():
    parser = argparse.ArgumentParser(description="Render all 8 styles in a comparison grid")
    parser.add_argument("--output", default="renders/style_grid.png", help="Output path for grid image")
    parser.add_argument("--resolution", type=int, default=512, help="Per-cell resolution")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for all styles")
    parser.add_argument("--printer", default="resin", choices=["fdm", "resin"])
    parser.add_argument("--critique", action="store_true", help="Also run vision model critique on the grid")
    parser.add_argument("--model", default="claude-sonnet-4-20250514", help="Vision model for critique")
    args = parser.parse_args()

    grid_path = render_style_grid(
        output_path=args.output,
        cell_resolution=args.resolution,
        seed=args.seed,
        printer_type=args.printer,
    )

    if args.critique:
        from scripts.critique_hotel import critique_grid
        import json

        print(f"\nSending grid to vision model for distinctiveness check...")
        result = critique_grid(grid_path, model=args.model)
        print(json.dumps(result, indent=2))

        result_path = Path(args.output).with_suffix(".critique.json")
        result_path.write_text(json.dumps(result, indent=2))
        print(f"\nGrid critique saved to {result_path}")


if __name__ == "__main__":
    main()
