"""Single-line Chinese stroke trajectories from Hanzi Writer Data."""

from __future__ import annotations

import gzip
import json
import math
import sys
from dataclasses import dataclass, field
from pathlib import Path

from src.glyph.layout_engine import LayoutConfig
from src.glyph.trajectory import GlyphPath, Point2D


DATA_VERSION = "2.0.1"
SOURCE_BOX_SIZE = 1024.0
SOURCE_TOP_Y = 900.0


class HanziWriterDataError(RuntimeError):
    """Raised when the offline stroke data cannot be loaded or is invalid."""


def default_data_path() -> Path:
    return (
        Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
        / "data"
        / "hanzi_writer"
        / f"medians-{DATA_VERSION}.json.gz"
    )


@dataclass
class HanziWriterData:
    """Load ordered single-line stroke medians from the local compact index."""

    path: Path = field(default_factory=default_data_path)
    _characters: dict[str, list[list[list[float]]]] | None = field(
        default=None, init=False, repr=False,
    )

    def _load(self) -> None:
        if self._characters is not None:
            return
        try:
            with gzip.open(self.path, "rt", encoding="utf-8") as file_obj:
                payload = json.load(file_obj)
            characters = payload["characters"]
            if not isinstance(characters, dict):
                raise TypeError("characters must be an object")
        except (OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
            raise HanziWriterDataError(
                f"Cannot load Hanzi Writer data from {self.path}: {exc}"
            ) from exc
        self._characters = characters

    def get_medians(self, char: str) -> list[list[list[float]]] | None:
        """Return ordered median strokes for one character, or ``None``."""
        if len(char) != 1:
            raise ValueError("get_medians() requires exactly one character")
        self._load()
        assert self._characters is not None
        return self._characters.get(char)

    def __contains__(self, char: str) -> bool:
        return self.get_medians(char) is not None

    @property
    def character_count(self) -> int:
        self._load()
        assert self._characters is not None
        return len(self._characters)


class SingleLineLayoutEngine:
    """Lay out Hanzi Writer median strokes in page-space millimeters.

    Hanzi Writer uses a 1024-unit em square with Y increasing upward. Its
    documented upper-left is ``(0, 900)`` and lower-right is ``(1024, -124)``.
    Output uses this project's page coordinates: top-left origin and Y-down.
    """

    def __init__(
        self,
        data: HanziWriterData | None = None,
        config: LayoutConfig | None = None,
        smooth_strokes: bool = True,
    ) -> None:
        self.data = data or HanziWriterData()
        self.config = config or LayoutConfig()
        self.smooth_strokes = smooth_strokes
        self.missing_characters: list[str] = []

    def layout(self, text: str) -> list[GlyphPath]:
        self.missing_characters = []
        glyphs: list[GlyphPath] = []
        cursor_x = self.config.margin_left
        cursor_y = self.config.margin_top
        content_right = self.config.page_width - self.config.margin_right

        for char in text:
            if char == "\r":
                continue
            if char == "\n":
                cursor_x = self.config.margin_left
                cursor_y += self.config.char_size + self.config.line_spacing
                continue
            if char.isspace():
                cursor_x += self.config.char_size + self.config.char_spacing
                continue
            if cursor_x + self.config.char_size > content_right:
                cursor_x = self.config.margin_left
                cursor_y += self.config.char_size + self.config.line_spacing

            medians = self.data.get_medians(char)
            if not medians:
                if char not in self.missing_characters:
                    self.missing_characters.append(char)
                cursor_x += self.config.char_size + self.config.char_spacing
                continue

            contours = []
            for stroke in medians:
                if len(stroke) < 2:
                    continue
                points = [
                    self._to_page_point(point, cursor_x, cursor_y)
                    for point in stroke
                ]
                contours.append(self._smooth_stroke(points) if self.smooth_strokes else points)
            glyphs.append(GlyphPath(
                char=char,
                contours=contours,
                advance_width_mm=self.config.char_size,
                origin=Point2D(cursor_x, cursor_y),
            ))
            cursor_x += self.config.char_size + self.config.char_spacing

        return glyphs

    def _to_page_point(
        self,
        point: list[float],
        origin_x: float,
        origin_y: float,
    ) -> Point2D:
        if len(point) != 2:
            raise HanziWriterDataError(f"Invalid median point: {point!r}")
        scale = self.config.char_size / SOURCE_BOX_SIZE
        return Point2D(
            origin_x + float(point[0]) * scale,
            origin_y + (SOURCE_TOP_Y - float(point[1])) * scale,
        )

    @staticmethod
    def _smooth_stroke(points: list[Point2D]) -> list[Point2D]:
        """Interpolate sparse medians without crossing stroke boundaries.

        Cardinal Hermite interpolation reduces visible polygon corners on long
        curves. Tangents are suppressed at sharp turns so hooks and folds keep
        their original corner and every source point remains on the path.
        """
        if len(points) < 3:
            return list(points)

        tangents: list[Point2D] = []
        for index, point in enumerate(points):
            if index == 0:
                tangent = Point2D(
                    (points[1].x - point.x) * 0.5,
                    (points[1].y - point.y) * 0.5,
                )
            elif index == len(points) - 1:
                tangent = Point2D(
                    (point.x - points[index - 1].x) * 0.5,
                    (point.y - points[index - 1].y) * 0.5,
                )
            elif SingleLineLayoutEngine._is_sharp_corner(
                points[index - 1], point, points[index + 1],
            ):
                tangent = Point2D(0.0, 0.0)
            else:
                tangent = Point2D(
                    (points[index + 1].x - points[index - 1].x) * 0.25,
                    (points[index + 1].y - points[index - 1].y) * 0.25,
                )
            tangents.append(tangent)

        result = [points[0]]
        for index in range(len(points) - 1):
            p0, p1 = points[index], points[index + 1]
            m0, m1 = tangents[index], tangents[index + 1]
            distance = math.hypot(p1.x - p0.x, p1.y - p0.y)
            sample_count = max(2, min(12, math.ceil(distance / 0.35)))
            for sample in range(1, sample_count + 1):
                t = sample / sample_count
                t2 = t * t
                t3 = t2 * t
                h00 = 2 * t3 - 3 * t2 + 1
                h10 = t3 - 2 * t2 + t
                h01 = -2 * t3 + 3 * t2
                h11 = t3 - t2
                result.append(Point2D(
                    h00 * p0.x + h10 * m0.x + h01 * p1.x + h11 * m1.x,
                    h00 * p0.y + h10 * m0.y + h01 * p1.y + h11 * m1.y,
                ))
        return result

    @staticmethod
    def _is_sharp_corner(before: Point2D, point: Point2D, after: Point2D) -> bool:
        ax, ay = point.x - before.x, point.y - before.y
        bx, by = after.x - point.x, after.y - point.y
        length_product = math.hypot(ax, ay) * math.hypot(bx, by)
        if length_product <= 1e-9:
            return True
        cosine = (ax * bx + ay * by) / length_product
        return cosine < 0.5
