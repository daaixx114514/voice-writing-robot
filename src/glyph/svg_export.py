"""SVG vector export for writing trajectories.

Produces clean, viewable SVG files with proper stroke rendering
that can be opened in any browser or vector editor.
"""

from __future__ import annotations

import math
from xml.etree.ElementTree import Element, SubElement, tostring

from src.glyph.trajectory import GlyphPath, PenState, Point2D, StrokePoint, WritingTrajectory


def _fmt(value: float, decimals: int = 2) -> str:
    return f"{value:.{decimals}f}"


def glyph_path_to_svg(
    glyph: GlyphPath,
    stroke_color: str = "#333333",
    stroke_width: float = 0.5,
    show_origin: bool = False,
    char_size_mm: float | None = None,
) -> str:
    """Render a single GlyphPath as an SVG snippet.

    Returns SVG path data wrapped in a ``<svg>`` element, sized to the
    glyph's bounding box or *char_size_mm*.
    """
    if not glyph.contours:
        return ""

    # Compute bounding box.
    all_x = [pt.x for c in glyph.contours for pt in c]
    all_y = [pt.y for c in glyph.contours for pt in c]
    min_x, max_x = min(all_x), max(all_x)
    min_y, max_y = min(all_y), max(all_y)

    pad = 2.0
    width = (max_x - min_x) + 2 * pad
    height = (max_y - min_y) + 2 * pad

    svg = Element("svg", {
        "xmlns": "http://www.w3.org/2000/svg",
        "width": _fmt(width),
        "height": _fmt(height),
        "viewBox": f"{_fmt(min_x - pad)} {_fmt(min_y - pad)} {_fmt(width)} {_fmt(height)}",
    })

    # Draw all contours as filled paths.
    path_d = _contours_to_path_d(glyph.contours)

    if path_d:
        SubElement(svg, "path", {
            "d": path_d,
            "fill": "none",
            "stroke": stroke_color,
            "stroke-width": _fmt(stroke_width),
            "stroke-linecap": "round",
            "stroke-linejoin": "round",
        })

    if show_origin:
        SubElement(svg, "circle", {
            "cx": _fmt(glyph.origin.x),
            "cy": _fmt(glyph.origin.y),
            "r": "1.5",
            "fill": "#ff0000",
            "opacity": "0.5",
        })

    return tostring(svg, encoding="unicode")


def trajectory_to_svg(
    trajectory: WritingTrajectory,
    stroke_color: str = "#333333",
    stroke_width: float = 0.3,
    page_bg: str = "#ffffff",
) -> str:
    """Render a full WritingTrajectory to a page-sized SVG document.

    Args:
        trajectory: The writing trajectory to render.
        stroke_color: Color for pen strokes.
        stroke_width: Stroke width in mm.
        page_bg: Page background color.

    Returns:
        A complete SVG document as a string.
    """
    width = trajectory.page_width_mm
    height = trajectory.page_height_mm

    svg = Element("svg", {
        "xmlns": "http://www.w3.org/2000/svg",
        "width": f"{_fmt(width)}mm",
        "height": f"{_fmt(height)}mm",
        "viewBox": f"0 0 {_fmt(width)} {_fmt(height)}",
    })

    # Background.
    SubElement(svg, "rect", {
        "x": "0", "y": "0",
        "width": _fmt(width),
        "height": _fmt(height),
        "fill": page_bg,
    })

    # Draw each glyph.
    for glyph in trajectory.glyphs:
        path_d = _contours_to_path_d(glyph.contours)
        if path_d:
            SubElement(svg, "path", {
                "d": path_d,
                "fill": "none",
                "stroke": stroke_color,
                "stroke-width": _fmt(stroke_width),
                "stroke-linecap": "round",
                "stroke-linejoin": "round",
            })

    # Optional: draw pen-up travel lines (light gray, dashed).
    _add_pen_up_lines(svg, trajectory.points, width, height)

    return tostring(svg, encoding="unicode")


def save_trajectory_svg(
    trajectory: WritingTrajectory,
    filepath: str,
    stroke_color: str = "#333333",
    stroke_width: float = 0.3,
) -> None:
    """Save a WritingTrajectory as an SVG file."""
    svg_str = trajectory_to_svg(
        trajectory,
        stroke_color=stroke_color,
        stroke_width=stroke_width,
    )
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(svg_str)


def stroke_points_to_svg(
    points: list[StrokePoint],
    page_width_mm: float = 210,
    page_height_mm: float = 297,
    pen_down_color: str = "#333",
    pen_up_color: str = "#cccccc",
    stroke_width: float = 0.3,
) -> str:
    """Render a raw StrokePoint list as an SVG (for debugging / low-level view).

    Pen-down segments are rendered in *pen_down_color*; pen-up travel moves
    in a lighter dashed *pen_up_color*.
    """
    svg = Element("svg", {
        "xmlns": "http://www.w3.org/2000/svg",
        "width": f"{_fmt(page_width_mm)}mm",
        "height": f"{_fmt(page_height_mm)}mm",
        "viewBox": f"0 0 {_fmt(page_width_mm)} {_fmt(page_height_mm)}",
    })

    SubElement(svg, "rect", {
        "x": "0", "y": "0",
        "width": _fmt(page_width_mm),
        "height": _fmt(page_height_mm),
        "fill": "#ffffff",
    })

    if not points:
        return tostring(svg, encoding="unicode")

    # Build path data segments.
    pen_down_parts: list[str] = []
    pen_up_parts: list[str] = []

    state = points[0].state
    start_idx = 0
    for i in range(1, len(points)):
        if points[i].state != state:
            # End of segment — draw if it has ≥2 points.
            segment = points[start_idx:i + 1]
            if len(segment) >= 2:
                if state == PenState.DOWN:
                    pen_down_parts.append(_points_to_path_d(segment))
                else:
                    pen_up_parts.append(_points_to_path_d(segment))
            state = points[i].state
            start_idx = i

    # Last segment.
    segment = points[start_idx:]
    if len(segment) >= 2:
        if state == PenState.DOWN:
            pen_down_parts.append(_points_to_path_d(segment))
        else:
            pen_up_parts.append(_points_to_path_d(segment))

    for d in pen_down_parts:
        SubElement(svg, "path", {
            "d": d,
            "fill": "none",
            "stroke": pen_down_color,
            "stroke-width": _fmt(stroke_width * 2),
            "stroke-linecap": "round",
            "stroke-linejoin": "round",
        })

    for d in pen_up_parts:
        SubElement(svg, "path", {
            "d": d,
            "fill": "none",
            "stroke": pen_up_color,
            "stroke-width": _fmt(stroke_width * 0.5),
            "stroke-dasharray": "1,2",
            "stroke-linecap": "round",
        })

    return tostring(svg, encoding="unicode")


# ------------------------------------------------------------------ helpers

def _contours_to_path_d(contours: list[list[Point2D]]) -> str:
    """Build SVG path `d` attribute from contours."""
    parts: list[str] = []
    for contour in contours:
        if not contour:
            continue
        sub: list[str] = []
        sub.append(f"M {_fmt(contour[0].x)} {_fmt(contour[0].y)}")
        for pt in contour[1:]:
            sub.append(f"L {_fmt(pt.x)} {_fmt(pt.y)}")
        parts.append(" ".join(sub))
    return " ".join(parts)


def _points_to_path_d(points: list[StrokePoint]) -> str:
    """Build SVG path `d` from StrokePoint list."""
    if not points:
        return ""
    parts = [f"M {_fmt(points[0].point.x)} {_fmt(points[0].point.y)}"]
    for sp in points[1:]:
        parts.append(f"L {_fmt(sp.point.x)} {_fmt(sp.point.y)}")
    return " ".join(parts)


def _add_pen_up_lines(
    svg: Element,
    points: list[StrokePoint],
    width: float,
    height: float,
) -> None:
    """Add dashed pen-up travel lines (optional, for debugging)."""
    if not points:
        return
    # Collect pen-up segments.
    pen_up_segs: list[str] = []
    state = points[0].state
    start = points[0]
    for sp in points[1:]:
        if sp.state != state:
            if state.name == "UP":
                seg = f"M {_fmt(start.point.x)} {_fmt(start.point.y)} L {_fmt(sp.point.x)} {_fmt(sp.point.y)}"
                pen_up_segs.append(seg)
            state = sp.state
            start = sp

    for seg in pen_up_segs:
        SubElement(svg, "path", {
            "d": seg,
            "fill": "none",
            "stroke": "#cccccc",
            "stroke-width": "0.15",
            "stroke-dasharray": "1 2",
        })
