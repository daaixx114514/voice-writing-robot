"""Core data structures for the glyph trajectory module."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Iterator


class PenState(Enum):
    """Pen state: DOWN = writing on paper, UP = lifted (moving between strokes)."""

    DOWN = auto()
    UP = auto()


@dataclass(frozen=True)
class Point2D:
    """A 2D point in page coordinates (mm), origin at top-left, Y-down."""

    x: float
    y: float

    def __add__(self, other: Point2D) -> Point2D:
        return Point2D(self.x + other.x, self.y + other.y)

    def __sub__(self, other: Point2D) -> Point2D:
        return Point2D(self.x - other.x, self.y - other.y)

    def scaled(self, s: float) -> Point2D:
        return Point2D(self.x * s, self.y * s)


@dataclass(frozen=True)
class StrokePoint:
    """A single point in the writing trajectory with pen state."""

    point: Point2D
    state: PenState


@dataclass
class GlyphPath:
    """Writing path for a single character.

    Each contour is a list of polyline points (after Bezier flattening)
    that represent one continuous pen-down stroke.
    """

    char: str
    contours: list[list[Point2D]] = field(default_factory=list)
    advance_width_mm: float = 0.0
    origin: Point2D = Point2D(0, 0)  # top-left of the character box


@dataclass
class WritingTrajectory:
    """Complete writing trajectory for a text string.

    ``points`` is the flattened stroke-by-stroke list suitable for
    serial output (future: G-code generation).
    """

    text: str
    glyphs: list[GlyphPath] = field(default_factory=list)
    points: list[StrokePoint] = field(default_factory=list)
    page_width_mm: float = 210.0
    page_height_mm: float = 297.0


def iter_stroke_points(glyph: GlyphPath) -> Iterator[StrokePoint]:
    """Yield StrokePoints for one glyph — pen up between contours."""
    for i, contour in enumerate(glyph.contours):
        if not contour:
            continue
        # Pen up while moving to first point of this contour.
        if i > 0:
            yield StrokePoint(contour[0], PenState.UP)
        # Pen down on first point, then continue through the rest.
        for j, pt in enumerate(contour):
            yield StrokePoint(pt, PenState.DOWN if j == 0 else PenState.DOWN)


def build_trajectory_points(glyphs: list[GlyphPath]) -> list[StrokePoint]:
    """Build the flat StrokePoint list from positioned glyphs.

    Each contour is drawn as a DOWN sequence.  Between contours (and
    between glyphs), we insert an UP point at the end of the previous
    stroke, then an UP point at the start of the next stroke, so pen-up
    travel renders as one straight dashed line.
    """
    result: list[StrokePoint] = []
    prev_down: Point2D | None = None
    prev_up: Point2D | None = None

    for glyph in glyphs:
        for contour in glyph.contours:
            if not contour:
                continue
            if prev_down is not None:
                # End of last stroke: lift pen.
                result.append(StrokePoint(prev_down, PenState.UP))
                # Travel to start of next stroke: still up.
                result.append(StrokePoint(contour[0], PenState.UP))
            # Draw contour.
            for pt in contour:
                result.append(StrokePoint(pt, PenState.DOWN))
                prev_down = pt

    return result
