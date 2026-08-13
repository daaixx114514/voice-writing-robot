"""G-code exporter — converts MotionCommand sequences to GRBL-compatible G-code.

This is a standalone exporter.  The core trajectory modules have no
knowledge of G-code; they only speak MotionCommand.
"""

from __future__ import annotations

from src.trajectory.models import CmdType, MotionCommand


def export_gcode(
    commands: list[MotionCommand],
    write_speed: float = 800,
    travel_speed: float = 2000,
    feed_rate_unit: str = "mm/min",
) -> str:
    """Convert a list of MotionCommand to GRBL-compatible G-code text.

    Args:
        commands: The output of ``trajectory_to_commands``.
        write_speed: Pen-down feed rate (mm/min, default 800 = ~13 mm/s).
        travel_speed: Pen-up feed rate (mm/min, default 2000 = ~33 mm/s).
        feed_rate_unit: Either ``"mm/min"`` or ``"mm/s"``.
          If ``"mm/s"``, the speeds are treated as mm/s and
          ``G21`` is emitted for mm units (GRBL default).

    Returns:
        A string containing one G-code instruction per line,
        suitable for saving as a ``.gcode`` / ``.nc`` file.

    G-code reference (GRBL 1.1):
        G21          — set units to millimetres
        G90          — absolute positioning
        G0 X… Y… F…  — rapid linear move (pen up)
        G1 X… Y… F…  — linear interpolation move (pen down)
        M3 S0        — spindle off → pen up  (GRBL laser mode)
        M5           — spindle off → pen up  (alternative)
    """
    if feed_rate_unit == "mm/s":
        g21 = "G21 ; mm"
        g_header_speed = f"/ Write speed {write_speed:.0f} mm/s, travel {travel_speed:.0f} mm/s"
    else:
        g21 = "G21 ; mm"
        g_header_speed = f"/ Write speed {write_speed:.0f} mm/min, travel {travel_speed:.0f} mm/min"

    lines = [
        f"G90 ; absolute positioning",
        f"{g21}",
        f"({g_header_speed})",
        "",
    ]

    #  GRBL laser mode: M3 S0 = pen up / laser off, M3 S1 = pen down / laser on.
    #  We use S0/S1 as pen-up/down signalling.  Some firmware uses M3/M5
    #  instead; both forms are emitted as comments for transparency.

    for cmd in commands:
        if cmd.type == CmdType.PEN_UP:
            lines.append("M5       ; pen up")
        elif cmd.type == CmdType.PEN_DOWN:
            lines.append("M3 S1    ; pen down")
        elif cmd.type == CmdType.MOVE:
            f = cmd.speed if cmd.speed > 0 else travel_speed
            lines.append(f"G0 X{cmd.x:.3f} Y{cmd.y:.3f} F{f:.0f}")
        elif cmd.type == CmdType.DRAW:
            f = cmd.speed if cmd.speed > 0 else write_speed
            lines.append(f"G1 X{cmd.x:.3f} Y{cmd.y:.3f} F{f:.0f}")

    # Always end with pen up.
    if commands and commands[-1].type != CmdType.PEN_UP:
        lines.append("M5       ; pen up")

    lines.append("")
    return "\n".join(lines)


def save_gcode(
    commands: list[MotionCommand],
    filepath: str,
    write_speed: float = 800,
    travel_speed: float = 2000,
) -> None:
    """Export and save G-code to a file."""
    gcode = export_gcode(commands, write_speed=write_speed, travel_speed=travel_speed)
    with open(filepath, "w", encoding="utf-8") as fh:
        fh.write(gcode)
