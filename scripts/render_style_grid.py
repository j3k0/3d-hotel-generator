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

if "PYOPENGL_PLATFORM" not in os.environ and sys.platform != "darwin":
    os.environ["PYOPENGL_PLATFORM"] = "osmesa"

ALL_STYLES = [
    # Row 1
    "modern", "art_deco", "classical", "victorian",
    # Row 2
    "mediterranean", "tropical", "skyscraper", "townhouse",
]

ALL_PRESETS = [
    # Row 1
    "royal", "fujiyama", "waikiki", "president",
    # Row 2
    "safari", "taj_mahal", "letoile", "boomerang",
]


def _assemble_grid(cell_images, labels, cols, cell_resolution, output_path):
    """Assemble cell images into a labeled grid and save."""
    from PIL import Image, ImageDraw, ImageFont

    rows = (len(cell_images) + cols - 1) // cols
    label_height = 30
    grid_w = cols * cell_resolution
    grid_h = rows * (cell_resolution + label_height)
    grid = Image.new("RGB", (grid_w, grid_h), (255, 255, 255))
    draw = ImageDraw.Draw(grid)

    for i, (img, label_text) in enumerate(zip(cell_images, labels)):
        row, col = divmod(i, cols)
        x = col * cell_resolution
        y = row * (cell_resolution + label_height)
        grid.paste(img, (x, y))

        label_y = y + cell_resolution + 5
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 16)
        except (OSError, IOError):
            font = ImageFont.load_default()
        bbox = draw.textbbox((0, 0), label_text, font=font)
        text_w = bbox[2] - bbox[0]
        draw.text((x + (cell_resolution - text_w) // 2, label_y), label_text, fill=(0, 0, 0), font=font)

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    grid.save(output)
    print(f"\nGrid saved to {output}")
    return str(output)


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
        from PIL import Image
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

    angles = [(45, 30, "grid")]

    for style in ALL_STYLES:
        print(f"Generating {style}...")
        params = BuildingParams(
            style_name=style,
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

    labels = [s.replace("_", " ").title() for s in ALL_STYLES]
    grid_path = _assemble_grid(cell_images, labels, 4, cell_resolution, output_path)

    # Cleanup temp files
    for f in tmp_dir.iterdir():
        f.unlink()
    tmp_dir.rmdir()

    return grid_path


def render_preset_grid(
    output_path: str = "renders/preset_grid.png",
    cell_resolution: int = 512,
    seed: int = 42,
    printer_type: str = "fdm",
) -> str:
    """
    Generate all 8 presets and render them in a 2x4 grid.
    Returns path to the grid image.
    """
    try:
        from PIL import Image
    except ImportError:
        print("ERROR: Grid rendering requires Pillow. Install with: pip install Pillow")
        sys.exit(1)

    sys.path.insert(0, str(Path(__file__).parent))
    from render_hotel import render_manifold_to_images
    from hotel_generator.complex.builder import ComplexBuilder
    from hotel_generator.complex.presets import get_preset
    from hotel_generator.config import ComplexParams
    from hotel_generator.settings import Settings

    builder = ComplexBuilder(Settings())
    cell_images = []
    tmp_dir = Path(output_path).parent / "preset_grid_tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    angles = [(45, 30, "grid")]

    for preset_name in ALL_PRESETS:
        print(f"Generating preset '{preset_name}'...")
        preset = get_preset(preset_name)
        params = ComplexParams(
            style_name=preset.style_name,
            num_buildings=preset.num_buildings,
            preset=preset_name,
            printer_type=printer_type,
            seed=seed,
        )
        result = builder.build(params)

        paths = render_manifold_to_images(
            result.combined,
            output_dir=str(tmp_dir),
            style_name=preset_name,
            resolution=(cell_resolution, cell_resolution),
            angles=angles,
        )
        cell_images.append(Image.open(paths[0]))

    labels = [f"{p.title()} ({get_preset(p).style_name})" for p in ALL_PRESETS]
    grid_path = _assemble_grid(cell_images, labels, 4, cell_resolution, output_path)

    # Cleanup temp files
    for f in tmp_dir.iterdir():
        f.unlink()
    tmp_dir.rmdir()

    return grid_path


def main():
    parser = argparse.ArgumentParser(description="Render all 8 styles or presets in a comparison grid")
    parser.add_argument("--output", default=None, help="Output path for grid image")
    parser.add_argument("--resolution", type=int, default=512, help="Per-cell resolution")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for all styles")
    parser.add_argument("--printer", default="fdm", choices=["fdm", "resin"])
    parser.add_argument("--presets", action="store_true", help="Render preset grid instead of style grid")
    parser.add_argument("--critique", action="store_true", help="Also run vision model critique on the grid")
    parser.add_argument("--model", default="claude-sonnet-4-20250514", help="Vision model for critique")
    args = parser.parse_args()

    if args.presets:
        output = args.output or "renders/preset_grid.png"
        grid_path = render_preset_grid(
            output_path=output,
            cell_resolution=args.resolution,
            seed=args.seed,
            printer_type=args.printer,
        )
    else:
        output = args.output or "renders/style_grid.png"
        grid_path = render_style_grid(
            output_path=output,
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

        result_path = Path(output).with_suffix(".critique.json")
        result_path.write_text(json.dumps(result, indent=2))
        print(f"\nGrid critique saved to {result_path}")


if __name__ == "__main__":
    main()
