"""Coordinate transformation from SVG-style to machine-style coordinates.

Handles:
- Optional X-axis flipping for different machine installations
- Y-axis flipping (SVG Y-down -> machine Y-up)
- Scaling to fit the physical work area
- Translation to machine origin

Coordinate systems:

    Font / Page coordinates (input):
        origin = top-left,  Y-down,  units = mm

    Machine coordinates (output):
        origin = bottom-left (or configurable),  Y-up,  units = mm
"""

from __future__ import annotations

from src.glyph.trajectory import Point2D, StrokePoint
from src.trajectory.config import MotionConfig


class CoordinateTransformer:
    """Transform page-space StrokePoint list into machine-space StrokePoint list."""

    def __init__(self, config: MotionConfig) -> None:
        self._cfg = config
        self._scale_x = 1.0
        self._scale_y = 1.0
        self._offset_x = 0.0
        self._offset_y = 0.0
        self._page_w = 0.0
        self._page_h = 0.0

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def fit_bounds(self, page_width_mm: float, page_height_mm: float) -> None:
        """Compute scale and offset so the page fits within the work area.

        Call once before ``transform``.
        """
        self._page_w = page_width_mm
        self._page_h = page_height_mm

        if self._cfg.scale_to_fit and self._cfg.work_width_mm > 0 and self._cfg.work_height_mm > 0:
            sx = self._cfg.work_width_mm / page_width_mm
            sy = self._cfg.work_height_mm / page_height_mm
            if self._cfg.keep_aspect_ratio:
                self._scale_x = self._scale_y = min(sx, sy)
            else:
                self._scale_x = sx
                self._scale_y = sy

            # Center scaled page in work area.
            sw = page_width_mm * self._scale_x
            sh = page_height_mm * self._scale_y
            self._offset_x = (self._cfg.work_width_mm - sw) / 2
            self._offset_y = (self._cfg.work_height_mm - sh) / 2
        else:
            self._scale_x = self._scale_y = 1.0
            self._offset_x = self._offset_y = 0.0

    def transform(self, points: list[StrokePoint]) -> list[StrokePoint]:
        """Transform a StrokePoint list from page space to machine space."""
        if not self._page_w or not self._page_h:
            raise RuntimeError("Call fit_bounds() before transform()")

        result: list[StrokePoint] = []
        for sp in points:
            result.append(StrokePoint(
                point=self._transform_point(sp.point),
                state=sp.state,
            ))
        return result

    def transform_point(self, pt: Point2D) -> Point2D:
        """Transform a single Point2D (convenience, calls _transform_point)."""
        return self._transform_point(pt)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _transform_point(self, pt: Point2D) -> Point2D:
        """Page (Y-down, top-left) -> machine (Y-up, bottom-left)."""
        # 1. Scale.
        x = pt.x * self._scale_x
        y = pt.y * self._scale_y

        # 2. Flip axes inside the scaled page bounds if needed.
        if self._cfg.flip_x:
            x = self._page_w * self._scale_x - x
        if self._cfg.flip_y:
            y = self._page_h * self._scale_y - y

        # 3. Translate.
        x += self._offset_x
        y += self._offset_y

        return Point2D(round(x, 3), round(y, 3))
