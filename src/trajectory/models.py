"""Machine-agnostic motion command model.

These data structures sit between the glyph trajectory layer and any
specific hardware protocol (G-code, serial, etc).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto


class CmdType(Enum):
    """Motion command type."""

    PEN_UP = auto()     # lift pen (no movement)
    PEN_DOWN = auto()   # lower pen (no movement)
    MOVE = auto()       # rapid travel, pen must be UP
    DRAW = auto()       # linear move, pen must be DOWN


@dataclass(frozen=True)
class MotionCommand:
    """A single machine-agnostic motion instruction.

    For ``PEN_UP`` / ``PEN_DOWN``, ``x``, ``y``, and ``speed`` are
    ignored and should be 0.
    """

    type: CmdType
    x: float = 0.0
    y: float = 0.0
    speed: float = 0.0       # mm/s; 0 = use configured default


def pen_up() -> MotionCommand:
    return MotionCommand(CmdType.PEN_UP)


def pen_down() -> MotionCommand:
    return MotionCommand(CmdType.PEN_DOWN)


def move_to(x: float, y: float, speed: float = 0.0) -> MotionCommand:
    return MotionCommand(CmdType.MOVE, x, y, speed)


def draw_to(x: float, y: float, speed: float = 0.0) -> MotionCommand:
    return MotionCommand(CmdType.DRAW, x, y, speed)
