"""Extract glyph outlines from TTFont as polyline contours."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from fontTools.pens.basePen import decomposeQuadraticSegment
from fontTools.pens.recordingPen import RecordingPen
from fontTools.ttLib import TTFont

from src.glyph.bezier import flatten_quadratic
from src.glyph.trajectory import GlyphPath, Point2D

logger = logging.getLogger(__name__)


@dataclass
class GlyphExtractor:
    """Extract Chinese character outlines from a TrueType font.

    Usage::

        extractor = GlyphExtractor(font)
        glyph = extractor.extract("你")
        # glyph.contours is a list of list[Point2D] in font-unit space.
    """

    font: TTFont
    tolerance: float = 5.0  # flattening tolerance in font-unit space (~=0.05mm at 12mm char size)
    glyph_cache: dict[str, GlyphPath] = field(default_factory=dict)

    def extract(self, char: str) -> GlyphPath | None:
        """Extract a single character's glyph outlines.

        Args:
            char: A single Chinese character.

        Returns:
            GlyphPath with contours in font-unit coordinates (Y-up),
            or None if the character is not in the font.
        """
        if char in self.glyph_cache:
            return self.glyph_cache[char]

        cmap = self.font.getBestCmap()
        if cmap is None:
            return None

        code_point = ord(char)
        glyph_name = cmap.get(code_point)
        if glyph_name is None:
            logger.debug("Character U+%04X (%s) not found in font cmap.", code_point, char)
            return None

        glyph_set = self.font.getGlyphSet()
        if glyph_name not in glyph_set:
            return None

        pen = RecordingPen()
        glyph_set[glyph_name].draw(pen)

        # Get horizontal advance width (font units).
        hmtx = self.font.get("hmtx")
        if hmtx is not None:
            adv = hmtx.metrics.get(glyph_name)
            advance_width = adv[0] if adv else 0
        else:
            advance_width = 0

        contours = self._pen_to_contours(pen.value)

        glyph_path = GlyphPath(
            char=char,
            contours=contours,
            advance_width_mm=float(advance_width),  # stored in font units; scaled later
        )

        self.glyph_cache[char] = glyph_path
        return glyph_path

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _pen_to_contours(
        self, pen_commands: list[tuple[str, tuple[float, float]]],
    ) -> list[list[Point2D]]:
        """Convert RecordingPen commands into polyline contours.

        RecordingPen records:
            ('moveTo',    ((x, y),))
            ('lineTo',    ((x, y),))
            ('qCurveTo',  ((x1,y1), (x2,y2), ...))  — off-curve points + endpoint
            ('curveTo',   ((x1,y1), (x2,y2), (x3,y3)))
            ('closePath', ())

        Each contour starts with moveTo and ends at either closePath or the
        next moveTo.  Quadratic Bézier curves (the default in TrueType)
        are flattened into polyline segments.
        """
        contours: list[list[Point2D]] = []
        current: list[tuple[str, float, float]] = []  # (cmd, x, y)

        for cmd, args in pen_commands:
            if cmd == "moveTo":
                if current:
                    contour = self._flatten_contour(current)
                    if contour:
                        contours.append(contour)
                x, y = args[0]
                current = [("M", x, y)]

            elif cmd == "lineTo":
                x, y = args[0]
                current.append(("L", x, y))

            elif cmd == "qCurveTo":
                raw_points = list(args)
                if raw_points and raw_points[-1] is None:
                    off_curve = [pt for pt in raw_points[:-1] if pt is not None]
                    if off_curve:
                        implied_start = (
                            (off_curve[-1][0] + off_curve[0][0]) * 0.5,
                            (off_curve[-1][1] + off_curve[0][1]) * 0.5,
                        )
                        raw_points = off_curve + [implied_start]
                        if not current:
                            current = [("M", implied_start[0], implied_start[1])]
                q_points = [
                    pt for pt in raw_points
                    if pt is not None and pt[0] is not None and pt[1] is not None
                ]
                if len(q_points) == 1:
                    current.append(("L", q_points[0][0], q_points[0][1]))
                elif len(q_points) >= 2:
                    for pt in q_points[:-1]:
                        current.append(("Q", pt[0], pt[1]))
                    endpoint = q_points[-1]
                    current.append(("QE", endpoint[0], endpoint[1]))

            elif cmd == "curveTo":
                for pt in args:
                    if pt is None or pt[0] is None or pt[1] is None:
                        continue
                    current.append(("C", pt[0], pt[1]))

            elif cmd == "closePath":
                if current:
                    start_x, start_y = current[0][1], current[0][2]
                    end_x, end_y = current[-1][1], current[-1][2]
                    if end_x != start_x or end_y != start_y:
                        current.append(("L", start_x, start_y))
                    contour = self._flatten_contour(current)
                    if contour:
                        contours.append(contour)
                    current = []

        # Flush final contour.
        if current:
            contour = self._flatten_contour(current)
            if contour:
                contours.append(contour)

        return contours

    # ------------------------------------------------------------------
    # Per-contour flattening
    # ------------------------------------------------------------------

    def _flatten_contour(
        self, cmds: list[tuple[str, float, float]],
    ) -> list[Point2D] | None:
        """Flatten a single contour's (cmd, x, y) list into Point2D polyline."""
        result: list[Point2D] = []
        i = 0

        while i < len(cmds):
            cmd, x, y = cmds[i]

            if cmd == "M":
                result.append(Point2D(x, y))
                i += 1

            elif cmd == "L":
                result.append(Point2D(x, y))
                i += 1

            elif cmd in ("Q", "QE"):
                # Collect one qCurveTo command, ending at its QE marker.
                q_pts: list[tuple[float, float]] = [(x, y)]
                i += 1
                while cmd != "QE" and i < len(cmds) and cmds[i][0] in ("Q", "QE"):
                    cmd = cmds[i][0]
                    q_pts.append((cmds[i][1], cmds[i][2]))
                    i += 1

                if len(q_pts) < 2 or not result:
                    continue

                # TrueType permits multiple consecutive off-curve controls.
                # fontTools inserts each implied on-curve midpoint for us.
                for control, endpoint in decomposeQuadraticSegment(q_pts):
                    cx, cy = control
                    ex, ey = endpoint
                    start = result[-1]
                    flat = flatten_quadratic(
                        start, Point2D(cx, cy), Point2D(ex, ey),
                        tolerance=self.tolerance,
                    )
                    result.extend(flat[1:])  # skip duplicated start point

            elif cmd == "C":
                # Cubic control points — fallback: add linearly.
                result.append(Point2D(x, y))
                i += 1

            else:
                i += 1

        # Remove consecutive duplicates that are within tolerance.
        if len(result) <= 1:
            return result if result else None
        dedup = [result[0]]
        for pt in result[1:]:
            dx = pt.x - dedup[-1].x
            dy = pt.y - dedup[-1].y
            if dx * dx + dy * dy > 0.01:  # > 0.1 font-unit threshold
                dedup.append(pt)
        return dedup if dedup else None

    @staticmethod
    def _last_point_of(cmds: list[tuple[str, float, float]]) -> tuple[float, float]:
        """Return (x, y) of the last non-M command's endpoint."""
        for cmd, x, y in reversed(cmds):
            if cmd in ("L", "Q", "C"):
                return (x, y)
        # Fallback to move point.
        if cmds:
            return (cmds[0][1], cmds[0][2])
        return (0.0, 0.0)

    def get_upem(self) -> int:
        """Return the font's units-per-em value."""
        return self.font["head"].unitsPerEm
