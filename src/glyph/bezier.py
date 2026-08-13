"""Bezier curve flattening — convert quadratic/cubic Bezier curves to polylines.

Uses recursive de Casteljau subdivision until the maximum deviation falls
below the configured tolerance.
"""

from __future__ import annotations

import math

from src.glyph.trajectory import Point2D


def _mid_point(a: Point2D, b: Point2D) -> Point2D:
    return Point2D((a.x + b.x) * 0.5, (a.y + b.y) * 0.5)


def _point_dist(a: Point2D, b: Point2D) -> float:
    return math.hypot(a.x - b.x, a.y - b.y)


def _quad_to_cubic(
    p0: Point2D, p1: Point2D, p2: Point2D,
) -> tuple[Point2D, Point2D, Point2D, Point2D]:
    """Convert quadratic Bezier (p0, p1, p2) to cubic form."""
    cp1 = Point2D(
        p0.x + (2.0 / 3.0) * (p1.x - p0.x),
        p0.y + (2.0 / 3.0) * (p1.y - p0.y),
    )
    cp2 = Point2D(
        p2.x + (2.0 / 3.0) * (p1.x - p2.x),
        p2.y + (2.0 / 3.0) * (p1.y - p2.y),
    )
    return (p0, cp1, cp2, p2)


def _flatten_cubic(
    p0: Point2D,
    p1: Point2D,
    p2: Point2D,
    p3: Point2D,
    tolerance: float,
    depth: int = 0,
) -> list[Point2D]:
    """Recursively subdivide a cubic Bezier into polyline points.

    Stops when the chord-distance of control points <= tolerance,
    or max_depth is reached.
    """
    max_depth = 16
    if depth >= max_depth:
        return [p0, p3]

    # Check flatness: distance of control points from chord p0-p3.
    line_len = _point_dist(p0, p3)
    if line_len < 1e-9:
        # Degenerate curve — just use endpoints.
        d1 = _point_dist(p0, p1)
        d2 = _point_dist(p0, p2)
        if max(d1, d2) <= tolerance:
            return [p0, p3]
    else:
        # Perpendicular distance approximately = distance from control
        # point to line p0-p3. We use a fast cross-product approach.
        def _perp_dist(pt: Point2D) -> float:
            # area of parallelogram / base length => height
            cross = abs(
                (pt.x - p0.x) * (p3.y - p0.y) - (pt.y - p0.y) * (p3.x - p0.x)
            )
            return cross / line_len

        if _perp_dist(p1) <= tolerance and _perp_dist(p2) <= tolerance:
            return [p0, p3]

    # Subdivide at t=0.5 (de Casteljau).
    p01 = _mid_point(p0, p1)
    p12 = _mid_point(p1, p2)
    p23 = _mid_point(p2, p3)
    p012 = _mid_point(p01, p12)
    p123 = _mid_point(p12, p23)
    p0123 = _mid_point(p012, p123)

    left = _flatten_cubic(p0, p01, p012, p0123, tolerance, depth + 1)
    right = _flatten_cubic(p0123, p123, p23, p3, tolerance, depth + 1)

    # Merge — don't duplicate the split point.
    return left[:-1] + right


def flatten_quadratic(
    p0: Point2D, p1: Point2D, p2: Point2D, tolerance: float = 0.05,
) -> list[Point2D]:
    """Flatten a quadratic Bezier (p0, control, p2) into polyline points.

    Args:
        p0: Start point.
        p1: Control point.
        p2: End point.
        tolerance: Maximum deviation in mm (default 0.05mm).

    Returns:
        List of points forming the polyline. First point is p0, last is p2.
    """
    cubic = _quad_to_cubic(p0, p1, p2)
    pts = _flatten_cubic(*cubic, tolerance=tolerance)
    # Deduplicate consecutive coincident points.
    result = [pts[0]]
    for pt in pts[1:]:
        if _point_dist(result[-1], pt) > tolerance * 0.1:
            result.append(pt)
    if _point_dist(result[-1], p2) > 0.001:
        result.append(p2)
    return result


def flatten_bezier_points(
    points: list[tuple[str, float, float]],
    tolerance: float = 0.05,
) -> list[Point2D]:
    """Flatten a list of (cmd, x, y) items from RecordingPen into polylines.

    Supported commands:
        'M' (moveTo) — starts a new sub-path; no output point
        'L' (lineTo) — emits the point directly
        'Q' (qCurveTo) — quadratic Bezier, control + endpoint
        'Z' (closePath) — no-op here; caller handles

    Returns:
        List of Point2D polyline points.
    """
    result: list[Point2D] = []
    cmd_stack: list[tuple[str, float, float]] = []

    i = 0
    while i < len(points):
        cmd, x, y = points[i][0], points[i][1], points[i][2]

        if cmd == "M":
            if cmd_stack:
                cmd_stack = []
            result.append(Point2D(x, y))
            cmd_stack.append(("M", x, y))
            i += 1

        elif cmd == "L":
            result.append(Point2D(x, y))
            cmd_stack.append(("L", x, y))
            i += 1

        elif cmd == "Q":
            # Off-curve / on-curve pairs.
            # Collect all the Q commands until next non-Q.
            q_pts: list[tuple[float, float]] = []
            while i < len(points) and points[i][0] == "Q":
                q_pts.append((points[i][1], points[i][2]))
                i += 1

            # Process quadratic Beziers.
            # Starting point is the last point in result.
            for qi in range(0, len(q_pts), 2):
                if qi + 1 >= len(q_pts):
                    # Should not happen with fontTools output, but be safe.
                    break
                cx, cy = q_pts[qi]
                ex, ey = q_pts[qi + 1]
                p_start = result[-1]
                flat = flatten_quadratic(
                    p_start,
                    Point2D(cx, cy),
                    Point2D(ex, ey),
                    tolerance,
                )
                # Extend with points after p_start.
                result.extend(flat[1:])

        else:
            # Unknown command — skip.
            i += 1

    return result
