#!/usr/bin/env python
"""Standalone demo — text → SVG writing trajectory (no GUI needed).

Usage::

    python demo_glyph.py                    # renders built-in sample text
    python demo_glyph.py "你好世界"          # renders your text
    python demo_glyph.py --font simkai.ttf  # use specific font
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from src.glyph import (
    LayoutConfig,
    LayoutEngine,
    build_trajectory,
    get_chinese_fonts,
    load_font,
)
from src.glyph.svg_export import save_trajectory_svg

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

OUTPUT_DIR = Path(__file__).parent / "output"
DEFAULT_TEXT = "你好世界\n语音写作机器人"


def main() -> None:
    ap = argparse.ArgumentParser(description="Render Chinese text to SVG writing trajectory")
    ap.add_argument(
        "text", nargs="*",
        help="Chinese text to render (default: built-in sample)",
    )
    ap.add_argument(
        "--font", "-f", default=None,
        help="Font name or path (e.g. simkai.ttf or 楷体)",
    )
    ap.add_argument(
        "--char-size", type=float, default=14.0,
        help="Character size in mm (default: 14)",
    )
    ap.add_argument(
        "--output", "-o", default=None,
        help="Output SVG path (default: output/<timestamp>.svg)",
    )
    ap.add_argument(
        "--skeleton", action="store_true",
        help="Extract single-line strokes via skeletonization (better for writing simulation)",
    )
    ap.add_argument(
        "--list-fonts", action="store_true",
        help="List available Chinese fonts and exit",
    )
    args = ap.parse_args()

    # ── List fonts mode ─────────────────────────────────────────────────
    if args.list_fonts:
        fonts = get_chinese_fonts()
        print(f"\nAvailable Chinese fonts ({len(fonts)}):\n")
        for f in fonts:
            print(f"  {f.name:30s}  {f.path}")
        print()
        return

    # ── Resolve font ────────────────────────────────────────────────────
    font_path = _resolve_font(args.font)

    # ── Build text ──────────────────────────────────────────────────────
    text = " ".join(args.text) if args.text else DEFAULT_TEXT
    logger.info("Rendering text: %r", text)

    # ── Layout ──────────────────────────────────────────────────────────
    font = load_font(font_path)
    logger.info("Font: %s (UPEM=%d)", font_path.name, font["head"].unitsPerEm)

    config = LayoutConfig(
        char_size=args.char_size,
        char_spacing=2.0,
        line_spacing=6.0,
        page_width=210,
        page_height=297,
        use_skeleton=args.skeleton,
    )
    engine = LayoutEngine(font, config)
    trajectory = build_trajectory(engine, text)

    # ── Stats ───────────────────────────────────────────────────────────
    total_points = sum(len(g.contours[0]) if g.contours else 0 for g in trajectory.glyphs)
    total_contours = sum(len(g.contours) for g in trajectory.glyphs)
    logger.info(
        "Generated %d glyphs, %d contours, ~%d points",
        len(trajectory.glyphs), total_contours, total_points,
    )

    # ── Export ──────────────────────────────────────────────────────────
    out = args.output
    if out is None:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        import time
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        out = str(OUTPUT_DIR / f"trajectory_{timestamp}.svg")

    save_trajectory_svg(trajectory, out, stroke_width=0.3)
    logger.info("Saved SVG to: %s", out)

    # ── Also export stroke-point SVG for debugging ──────────────────────
    debug_out = str(Path(out).with_suffix(".debug.svg"))
    from src.glyph.svg_export import stroke_points_to_svg
    svg = stroke_points_to_svg(
        trajectory.points,
        page_width_mm=trajectory.page_width_mm,
        page_height_mm=trajectory.page_height_mm,
    )
    with open(debug_out, "w", encoding="utf-8") as fh:
        fh.write(svg)
    logger.info("Debug SVG with pen-up lines saved to: %s", debug_out)


def _resolve_font(font_spec: str | None) -> Path:
    """Resolve a font name/path to an absolute path."""
    fonts = get_chinese_fonts()

    if not fonts:
        logger.error("No Chinese fonts found on this system.")
        # Fall back to any TTF.
        from src.glyph.font_manager import discover_fonts
        all_fonts = discover_fonts()
        if all_fonts:
            logger.warning("Falling back to first available font: %s", all_fonts[0].path)
            return all_fonts[0].path
        sys.exit(1)

    if font_spec is None:
        # Preferred order for CLI.  Keep in sync with main_window.py if you
        # want the GUI and CLI to use the same font.  Currently unified.
        preferred = ["stxingka", "stkaiti", "simkai", "simsun", "msyh"]
        for name in preferred:
            for f in fonts:
                if name in f.name.lower():
                    logger.info("Auto-selected font: %s", f.path)
                    return f.path
        logger.info("Auto-selected font: %s", fonts[0].path)
        return fonts[0].path

    # By name (partial match).
    spec_lower = font_spec.lower()
    for f in fonts:
        if spec_lower in f.name.lower():
            return f.path

    # As a direct path.
    path = Path(font_spec)
    if path.is_file():
        return path

    logger.error("Font not found: %s. Use --list-fonts to see available fonts.", font_spec)
    sys.exit(1)


if __name__ == "__main__":
    main()
