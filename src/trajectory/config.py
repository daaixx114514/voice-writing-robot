"""Motion control configuration parameters."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class MotionConfig:
    """Machine-agnostic motion parameters.

    All linear dimensions in **millimeters**, speeds in **mm/s**.
    """

    work_width_mm: float = 200.0
    work_height_mm: float = 280.0

    write_speed: float = 20.0       # pen-down drawing speed
    travel_speed: float = 50.0      # pen-up rapid move speed

    flip_x: bool = False            # reverse machine X direction when required
    flip_y: bool = True             # Y-down (page) -> Y-up (machine)
    origin: str = "bottom-left"     # machine coordinate origin

    scale_to_fit: bool = True       # auto-scale to fit work area
    keep_aspect_ratio: bool = True

    min_point_distance: float = 0.02   # mm, points closer than this are merged
    simplify_tolerance: float = 0.03   # mm, Douglas-Peucker tolerance
