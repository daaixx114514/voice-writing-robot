"""Text layout engine — converts text string to positioned glyphs on a page."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from fontTools.ttLib import TTFont

from src.glyph.glyph_extractor import GlyphExtractor
from src.glyph.skeleton import contours_to_skeleton
from src.glyph.trajectory import GlyphPath, Point2D

logger = logging.getLogger(__name__)


@dataclass
class LayoutConfig:
    """Page layout parameters.

    All length values are in **millimeters**.
    """

    page_width: float = 148.0       # A5 landscape
    page_height: float = 210.0

    margin_left: float = 14.0
    margin_top: float = 14.0
    margin_right: float = 14.0
    margin_bottom: float = 14.0

    char_size: float = 12.0         # target character height (mm)
    char_spacing: float = 2.0       # extra horizontal gap between chars
    line_spacing: float = 6.0       # extra vertical gap between lines

    flatten_tolerance: float = 5.0  # font-unit tolerance for Bezier flattening

    use_skeleton: bool = False      # extract single-line strokes via skeletonization


class LayoutEngine:
    """Layout Chinese text onto a page, producing positioned GlyphPath objects.

    Usage::

        engine = LayoutEngine(font, config)
        glyphs = engine.layout("你好世界")
    """

    def __init__(self, font: TTFont, config: LayoutConfig | None = None) -> None:
        self.font = font
        self.config = config or LayoutConfig()
        self.extractor = GlyphExtractor(font, tolerance=self.config.flatten_tolerance)
        self._upem = self.extractor.get_upem()
        # Scale: font-units → mm.  em-square = upem units → char_size mm.
        self._scale = self.config.char_size / self._upem

    def layout(self, text: str) -> list[GlyphPath]:
        """Layout a text string into positioned glyphs.

        Handles automatic line wrapping. Characters not found in the font
        are silently skipped.  ``\\n`` starts a new line.

        Args:
            text: Chinese text string (may include ASCII/newlines).

        Returns:
            List of GlyphPath objects with positions in page coordinates
            (mm, Y-down, origin at top-left of character box).
        """
        content_width = (
            self.config.page_width
            - self.config.margin_left
            - self.config.margin_right
        )
        result: list[GlyphPath] = []

        cursor_x = self.config.margin_left
        cursor_y = self.config.margin_top

        for char in text:
            if char == "\n":
                cursor_x = self.config.margin_left
                cursor_y += self.config.char_size + self.config.line_spacing
                continue
            if char == "\r":
                continue

            glyph = self.extractor.extract(char)
            if glyph is None:
                logger.debug("Skipping character not in font: %r", char)
                continue

            # Optionally extract single-line strokes from closed outlines.
            if self.config.use_skeleton and glyph.contours:
                skel = contours_to_skeleton(glyph.contours, width_px=200, height_px=200)
                if skel:
                    glyph.contours = skel

            # advance_width is in font-units (stored in the advance_width_mm
            # field for historical reasons).  Scale it to mm.
            advance_fu = glyph.advance_width_mm if glyph.advance_width_mm > 0 else self._upem
            char_mm = advance_fu * self._scale

            # Line wrap.
            if cursor_x + char_mm > self.config.margin_left + content_width:
                cursor_x = self.config.margin_left
                cursor_y += self.config.char_size + self.config.line_spacing

            positioned = self._position_glyph(glyph, cursor_x, cursor_y)
            result.append(positioned)

            cursor_x += char_mm + self.config.char_spacing

        return result

    def _position_glyph(
        self, glyph: GlyphPath, page_x: float, page_y: float,
    ) -> GlyphPath:
        """Transform contour points from font-unit (Y-up) to page mm (Y-down).

        *page_x*, *page_y* is the top-left corner of the character box in mm.
        """
        new_contours: list[list[Point2D]] = []

        for contour in glyph.contours:
            new_contour: list[Point2D] = []
            for pt in contour:
                mm_x = pt.x * self._scale
                mm_y = pt.y * self._scale
                # X: rightward offset.
                # Y: flip (font Y-up → page Y-down) + offset.
                new_contour.append(Point2D(
                    page_x + mm_x,
                    page_y + self.config.char_size - mm_y,
                ))
            new_contours.append(new_contour)

        return GlyphPath(
            char=glyph.char,
            contours=new_contours,
            advance_width_mm=glyph.advance_width_mm,
            origin=Point2D(page_x, page_y),
        )

    def normalize_to_box(self, glyph: GlyphPath) -> GlyphPath:
        """Normalize a glyph's contours to fit a unit box [0,1] × [0,1]."""
        if not glyph.contours:
            return glyph

        all_x = [pt.x for c in glyph.contours for pt in c]
        all_y = [pt.y for c in glyph.contours for pt in c]
        min_x, max_x = min(all_x), max(all_x)
        min_y, max_y = min(all_y), max(all_y)

        span_x = max_x - min_x or 1.0
        span_y = max_y - min_y or 1.0

        new_contours = [
            [Point2D((pt.x - min_x) / span_x, (pt.y - min_y) / span_y) for pt in c]
            for c in glyph.contours
        ]

        return GlyphPath(
            char=glyph.char,
            contours=new_contours,
            advance_width_mm=glyph.advance_width_mm,
            origin=glyph.origin,
        )
