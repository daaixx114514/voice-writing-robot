"""Glyph skeletonization — convert closed Outline contours to single-line strokes.

TrueType fonts store glyphs as closed outlines (for filling).
Handwriting requires single-line *strokes* (centerlines).
This module extracts the medial axis (skeleton) of each glyph using
scikit-image's ``skeletonize``, then traces it back to polylines.
"""

from __future__ import annotations

import numpy as np
from PIL import Image, ImageDraw
from skimage.morphology import skeletonize

from src.glyph.trajectory import Point2D


def contours_to_skeleton(
    contours: list[list[Point2D]],
    width_px: int = 140,
    height_px: int = 140,
    margin_px: int = 8,
) -> list[list[Point2D]]:
    """Convert closed outline contours to single-line skeleton strokes.

    Args:
        contours: Glyph contours (list of polylines) in the glyph's
                  local coordinate space (mm, Y-down, origin at char box top-left).
        width_px: Bitmap width in pixels.  Higher = finer detail.
        height_px: Bitmap height in pixels.
        margin_px: Padding around the glyph in pixels.

    Returns:
        A new list of contours where each is a single-line stroke
        (skeleton centerline), in the ORIGINAL coordinate space.
    """
    if not contours:
        return []

    # Scale contours to bitmap space.
    all_x = [pt.x for c in contours for pt in c]
    all_y = [pt.y for c in contours for pt in c]
    min_x, max_x = min(all_x), max(all_x)
    min_y, max_y = min(all_y), max(all_y)

    span_x = max_x - min_x or 1.0
    span_y = max_y - min_y or 1.0

    draw_w, draw_h = width_px - 2 * margin_px, height_px - 2 * margin_px
    scale = min(draw_w / span_x, draw_h / span_y)

    def to_px(pt: Point2D) -> tuple[float, float]:
        return (
            margin_px + (pt.x - min_x) * scale,
            margin_px + (pt.y - min_y) * scale,
        )

    # Render contours to a binary image.
    img = Image.new("L", (width_px, height_px), 0)
    draw = ImageDraw.Draw(img)
    for contour in contours:
        if len(contour) < 2:
            continue
        px_pts = [to_px(pt) for pt in contour]
        # Fill the closed contour so skeletonize sees a solid shape.
        draw.polygon(px_pts, fill=255, outline=255)

    # Skeletonize.
    binary = np.array(img) > 127
    skel = skeletonize(binary)
    skel_img = skel.astype(np.uint8) * 255

    # Trace the skeleton into polylines.
    traced = _trace_skeleton(skel_img)

    # Map back to original coordinate space.
    def from_px(px: float, py: float) -> Point2D:
        return Point2D(
            (px - margin_px) / scale + min_x,
            (py - margin_px) / scale + min_y,
        )

    result: list[list[Point2D]] = []
    for stroke in traced:
        pts = [from_px(px, py) for px, py in stroke]
        if len(pts) >= 2:
            result.append(pts)

    return result


def _trace_skeleton(skel: np.ndarray) -> list[list[tuple[int, int]]]:
    """Walk a binary skeleton image and return ordered polylines.

    Starts from endpoints (pixels with exactly 1 neighbor) and
    follows until a junction or another endpoint.
    """
    h, w = skel.shape
    visited = np.zeros_like(skel, dtype=bool)

    # 8-connected neighbor offsets.
    n8 = [(-1, -1), (0, -1), (1, -1),
          (-1,  0),          (1,  0),
          (-1,  1), (0,  1), (1,  1)]

    def neighbors(y: int, x: int) -> list[tuple[int, int]]:
        result = []
        for dy, dx in n8:
            ny, nx = y + dy, x + dx
            if 0 <= ny < h and 0 <= nx < w and skel[ny, nx]:
                result.append((ny, nx))
        return result

    def is_endpoint(y: int, x: int) -> bool:
        return len(neighbors(y, x)) == 1

    def is_junction(y: int, x: int) -> bool:
        return len(neighbors(y, x)) >= 3

    strokes: list[list[tuple[int, int]]] = []

    # First pass: trace from all endpoints.
    for y in range(h):
        for x in range(w):
            if skel[y, x] and not visited[y, x] and is_endpoint(y, x):
                stroke = _walk(y, x, skel, visited, n8, h, w, is_junction)
                if len(stroke) >= 2:
                    strokes.append(stroke)

    # Second pass: mop up any remaining skeleton pixels (isolated loops).
    for y in range(h):
        for x in range(w):
            if skel[y, x] and not visited[y, x]:
                stroke = _walk_loop(y, x, skel, visited, n8, h, w)
                if len(stroke) >= 2:
                    strokes.append(stroke)

    return strokes


def _walk(
    sy: int, sx: int,
    skel: np.ndarray,
    visited: np.ndarray,
    n8: list[tuple[int, int]],
    h: int, w: int,
    is_junction,
) -> list[tuple[int, int]]:
    """Walk from an endpoint, stopping at another endpoint or a junction."""
    stroke = [(sx, sy)]
    visited[sy, sx] = True

    cy, cx = sy, sx
    # Find starting neighbor.
    nbrs = [(ny, nx) for ny, nx in [
        (cy + dy, cx + dx) for dy, dx in n8
    ] if 0 <= ny < h and 0 <= nx < w and skel[ny, nx] and not visited[ny, nx]]
    if not nbrs:
        return stroke

    cy, cx = nbrs[0]
    stroke.append((cx, cy))
    visited[cy, cx] = True

    # Walk until dead end.
    while True:
        if is_junction(cy, cx):
            break
        nbrs = [(ny, nx) for ny, nx in [
            (cy + dy, cx + dx) for dy, dx in n8
        ] if 0 <= ny < h and 0 <= nx < w and skel[ny, nx] and not visited[ny, nx]]
        if not nbrs:
            break  # endpoint reached
        if len(nbrs) >= 2:
            break  # junction
        cy, cx = nbrs[0]
        stroke.append((cx, cy))
        visited[cy, cx] = True

    return stroke


def _walk_loop(
    sy: int, sx: int,
    skel: np.ndarray,
    visited: np.ndarray,
    n8: list[tuple[int, int]],
    h: int, w: int,
) -> list[tuple[int, int]]:
    """Walk a closed loop (no clear endpoint)."""
    stroke = [(sx, sy)]
    visited[sy, sx] = True

    # Find start direction.
    nbrs = [(ny, nx) for ny, nx in [
        (sy + dy, sx + dx) for dy, dx in n8
    ] if 0 <= ny < h and 0 <= nx < w and skel[ny, nx] and not visited[ny, nx]]
    if not nbrs:
        return stroke

    cy, cx = nbrs[0]
    visited[cy, cx] = True
    stroke.append((cx, cy))

    # Walk until back at start or stuck.
    max_len = 10000
    while len(stroke) < max_len:
        nbrs = [(ny, nx) for ny, nx in [
            (cy + dy, cx + dx) for dy, dx in n8
        ] if 0 <= ny < h and 0 <= nx < w and skel[ny, nx] and not visited[ny, nx]]
        if not nbrs:
            break
        cy, cx = nbrs[0]
        visited[cy, cx] = True
        stroke.append((cx, cy))

    return stroke
