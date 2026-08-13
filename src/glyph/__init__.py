"""Glyph trajectory module — text to writing path conversion.

Key types:
  - ``Point2D``, ``GlyphPath``, ``WritingTrajectory`` are the core data structures.
  - ``FontManager`` discovers and loads system fonts.
  - ``GlyphExtractor`` extracts glyph outlines from a TrueType font.
  - ``LayoutEngine`` positions glyphs on a page.

Usage::

    from src.glyph import LayoutEngine, LayoutConfig, build_trajectory, WritingTrajectory
    from src.glyph.font_manager import load_font, get_chinese_fonts
    from src.glyph.svg_export import save_trajectory_svg

    fonts = get_chinese_fonts()
    font = load_font(fonts[0].path)
    config = LayoutConfig(char_size=12.0)
    engine = LayoutEngine(font, config)
    trajectory = build_trajectory(engine, "你好世界")
    save_trajectory_svg(trajectory, "output.svg")
"""

from __future__ import annotations

from src.glyph.bezier import flatten_quadratic, flatten_bezier_points
from src.glyph.font_manager import (
    FontInfo,
    discover_fonts,
    get_chinese_fonts,
    load_font,
)
from src.glyph.glyph_extractor import GlyphExtractor
from src.glyph.hanzi_writer import (
    HanziWriterData,
    HanziWriterDataError,
    SingleLineLayoutEngine,
)
from src.glyph.layout_engine import LayoutConfig, LayoutEngine
from src.glyph.trajectory import (
    GlyphPath,
    PenState,
    Point2D,
    StrokePoint,
    WritingTrajectory,
    build_trajectory_points,
    iter_stroke_points,
)


def build_trajectory(
    engine: LayoutEngine | SingleLineLayoutEngine,
    text: str,
    page_width_mm: float | None = None,
    page_height_mm: float | None = None,
) -> WritingTrajectory:
    """Layout text and build a complete WritingTrajectory in one call.

    Args:
        engine: A configured LayoutEngine.
        text: The text to lay out.
        page_width_mm: Override for page width (default from config).
        page_height_mm: Override for page height (default from config).

    Returns:
        A WritingTrajectory ready for preview or export.
    """
    glyphs = engine.layout(text)
    points = build_trajectory_points(glyphs)

    return WritingTrajectory(
        text=text,
        glyphs=glyphs,
        points=points,
        page_width_mm=page_width_mm or engine.config.page_width,
        page_height_mm=page_height_mm or engine.config.page_height,
    )
