"""Convert StrokePoint lists into machine-agnostic MotionCommand sequences.

StrokePoint (PenState.DOWN / UP per-point)
      |
      v
MotionCommand (PEN_UP / PEN_DOWN / MOVE / DRAW)
"""

from __future__ import annotations

from src.glyph.trajectory import PenState, StrokePoint
from src.trajectory.config import MotionConfig
from src.trajectory.models import CmdType, MotionCommand, draw_to, move_to, pen_down, pen_up


def trajectory_to_commands(
    points: list[StrokePoint],
    config: MotionConfig | None = None,
    write_speed: float | None = None,
    travel_speed: float | None = None,
) -> list[MotionCommand]:
    """Convert stroke-point list to motion commands.

    Rules:
    - Consecutive DOWN points become DRAW commands.
    - Transitions between DOWN runs insert PEN_UP, MOVE, PEN_DOWN.
    - UP points between runs are converted to MOVE commands.
    - Redundant state transitions are suppressed.

    Args:
        points: Processed StrokePoint list (after coordinate transform + simplify).
        config: MotionConfig for default speeds.
        write_speed: Override pen-down speed (mm/s).
        travel_speed: Override pen-up speed (mm/s).

    Returns:
        List of MotionCommand ready for simulators or exporters.
    """
    ws = write_speed or (config.write_speed if config else 20.0)
    ts = travel_speed or (config.travel_speed if config else 50.0)

    if not points:
        return []

    commands: list[MotionCommand] = []
    current_position: tuple[float, float] | None = None
    is_pen_down = False

    for sp in points:
        target = (sp.point.x, sp.point.y)

        if sp.state == PenState.DOWN:
            if not is_pen_down:
                # Plotter convention: travel to a stroke start with the pen
                # raised, then lower it. Never draw from an unknown position.
                if not commands:
                    commands.append(pen_up())
                if current_position is None or not _same_position(current_position, target):
                    commands.append(move_to(*target, ts))
                    current_position = target
                commands.append(pen_down())
                is_pen_down = True
            elif current_position is None or not _same_position(current_position, target):
                commands.append(draw_to(*target, ws))
                current_position = target
        else:
            if is_pen_down:
                commands.append(pen_up())
                is_pen_down = False
            elif not commands:
                commands.append(pen_up())
            if current_position is None or not _same_position(current_position, target):
                commands.append(move_to(*target, ts))
                current_position = target

    if is_pen_down:
        commands.append(pen_up())

    return _deduplicate_states(commands)


def _same_position(
    first: tuple[float, float],
    second: tuple[float, float],
    tolerance: float = 1e-9,
) -> bool:
    return (
        abs(first[0] - second[0]) <= tolerance
        and abs(first[1] - second[1]) <= tolerance
    )


def _deduplicate_states(commands: list[MotionCommand]) -> list[MotionCommand]:
    """Remove consecutive PEN_UP/PEN_DOWN that don't change state."""
    if len(commands) < 2:
        return commands

    result = [commands[0]]
    for cmd in commands[1:]:
        prev = result[-1]
        # Remove consecutive PEN_UP if no move between them.
        if cmd.type == CmdType.PEN_UP and prev.type == CmdType.PEN_UP:
            continue
        if cmd.type == CmdType.PEN_DOWN and prev.type == CmdType.PEN_DOWN:
            continue
        # If we just did PEN_UP -> MOVE, and then another PEN_UP, skip the second PEN_UP.
        if cmd.type == CmdType.PEN_UP and prev.type == CmdType.MOVE:
            if len(result) >= 2 and result[-2].type == CmdType.PEN_UP:
                continue
        result.append(cmd)
    return result
