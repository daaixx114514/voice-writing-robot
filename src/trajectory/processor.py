"""Trajectory post-processing: deduplicate, simplify, and validate.

All operations preserve stroke order (critical for Chinese characters).
"""

from __future__ import annotations

import math

from src.glyph.trajectory import PenState, Point2D, StrokePoint
from src.trajectory.config import MotionConfig


class TrajectoryProcessor:
    """Post-process a StrokePoint list before motion command generation.

    Operations:
    1. Remove consecutive duplicate points (same coordinate).
    2. Merge points that are closer than ``min_point_distance``.
    3. Simplify dense paths (Douglas-Peucker).
    4. Warn if points exceed the work area.
    """

    def __init__(self, config: MotionConfig) -> None:
        self._cfg = config
        self._warnings: list[str] = []

    @property
    def warnings(self) -> list[str]:
        return list(self._warnings)

    def clear_warnings(self) -> None:
        self._warnings.clear()

    def process(
        self, points: list[StrokePoint],
        work_w: float | None = None,
        work_h: float | None = None,
    ) -> list[StrokePoint]:
        """Run the full post-processing pipeline and return cleaned points."""
        self._warnings.clear()

        if not points:
            return []

        ww = work_w or self._cfg.work_width_mm
        wh = work_h or self._cfg.work_height_mm

        result = self._remove_duplicates(points)
        result = self._merge_close_points(result)
        result = self._simplify(result)
        self._check_bounds(result, ww, wh)

        return result

    # ------------------------------------------------------------------
    # Step 1: remove exact duplicates
    # ------------------------------------------------------------------

    @staticmethod
    def _remove_duplicates(
        points: list[StrokePoint],
    ) -> list[StrokePoint]:
        """Remove consecutive points with identical coordinates AND same pen state.

        Points with the same position but different pen state are kept
        because they represent a semantically important transition
        (e.g. DOWN -> UP at stroke endpoint).
        """
        if len(points) < 2:
            return list(points)

        result = [points[0]]
        for sp in points[1:]:
            prev = result[-1]
            if (
                sp.point.x == prev.point.x
                and sp.point.y == prev.point.y
                and sp.state == prev.state
            ):
                continue
            result.append(sp)
        return result

    # ------------------------------------------------------------------
    # Step 2: merge close points
    # ------------------------------------------------------------------

    def _merge_close_points(self, points: list[StrokePoint]) -> list[StrokePoint]:
        """Drop points that are within ``min_point_distance`` of the previous."""
        threshold = self._cfg.min_point_distance
        if threshold <= 0 or len(points) < 2:
            return list(points)

        th2 = threshold * threshold
        result = [points[0]]
        for sp in points[1:]:
            prev = result[-1]
            if sp.state != prev.state:
                result.append(sp)
                continue
            dx = sp.point.x - prev.point.x
            dy = sp.point.y - prev.point.y
            if dx * dx + dy * dy < th2:
                continue
            result.append(sp)
        return result

    # ------------------------------------------------------------------
    # Step 3: Douglas-Peucker simplification (per-stroke)
    # ------------------------------------------------------------------

    def _simplify(self, points: list[StrokePoint]) -> list[StrokePoint]:
        """Simplify dense polylines while preserving stroke boundaries."""
        tol = self._cfg.simplify_tolerance
        if tol <= 0 or not points:
            return list(points)

        # Split into groups by pen state transitions (each DOWN run = one stroke).
        groups: list[list[StrokePoint]] = []
        current: list[StrokePoint] = []
        prev_state: PenState | None = None

        for sp in points:
            if sp.state == PenState.UP or (prev_state is not None and sp.state != prev_state):
                if current:
                    groups.append(current)
                current = []
            current.append(sp)
            prev_state = sp.state

        if current:
            groups.append(current)

        # Simplify each DOWN group with Douglas-Peucker.
        result: list[StrokePoint] = []
        for g in groups:
            if not g:
                continue
            if g[0].state == PenState.UP:
                # Don't simplify UP transitions; they're already sparse.
                result.extend(g)
            else:
                pts = [(sp.point.x, sp.point.y) for sp in g]
                keep = self._douglas_peucker(pts, tol)
                for idx in keep:
                    result.append(g[idx])

        return result

    @staticmethod
    def _douglas_peucker(
        pts: list[tuple[float, float]], tol: float,
    ) -> list[int]:
        """Return indices of points to keep (always includes first and last)."""
        if len(pts) < 3:
            return list(range(len(pts)))

        # Find point with max perpendicular distance.
        max_dist = 0.0
        max_idx = 0
        x0, y0 = pts[0]
        x1, y1 = pts[-1]
        dx = x1 - x0
        dy = y1 - y0
        line_len2 = dx * dx + dy * dy

        for i in range(1, len(pts) - 1):
            if line_len2 < 1e-12:
                d = math.hypot(pts[i][0] - x0, pts[i][1] - y0)
            else:
                t = ((pts[i][0] - x0) * dx + (pts[i][1] - y0) * dy) / line_len2
                t = max(0.0, min(1.0, t))
                px = x0 + t * dx
                py = y0 + t * dy
                d = math.hypot(pts[i][0] - px, pts[i][1] - py)
            if d > max_dist:
                max_dist = d
                max_idx = i

        if max_dist < tol:
            return [0, len(pts) - 1]

        left = TrajectoryProcessor._douglas_peucker(pts[:max_idx + 1], tol)
        right = TrajectoryProcessor._douglas_peucker(pts[max_idx:], tol)
        return left[:-1] + [idx + max_idx for idx in right]

    # ------------------------------------------------------------------
    # Step 4: bounds check
    # ------------------------------------------------------------------

    def _check_bounds(
        self, points: list[StrokePoint],
        work_w: float, work_h: float,
    ) -> None:
        """Warn if any DOWN point exceeds the work area."""
        min_x = min_y = float("inf")
        max_x = max_y = float("-inf")

        for sp in points:
            if sp.state != PenState.DOWN:
                continue
            min_x = min(min_x, sp.point.x)
            min_y = min(min_y, sp.point.y)
            max_x = max(max_x, sp.point.x)
            max_y = max(max_y, sp.point.y)

        if max_x > work_w + 0.01 or max_y > work_h + 0.01:
            self._warnings.append(
                f"Trajectory exceeds work area ({work_w:.1f}x{work_h:.1f} mm). "
                f"Max point: ({max_x:.1f}, {max_y:.1f})"
            )
        if min_x < -0.01 or min_y < -0.01:
            self._warnings.append(
                f"Trajectory contains negative coordinates. "
                f"Min point: ({min_x:.1f}, {min_y:.1f})"
            )
