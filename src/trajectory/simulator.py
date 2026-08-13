"""Virtual pen plotter simulator.

Consumes ``MotionCommand`` objects and produces per-frame pen state
that can be rendered by a PySide6 widget.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.trajectory.config import MotionConfig
from src.trajectory.models import CmdType, MotionCommand


@dataclass
class PenState:
    """Snapshot of the virtual pen at one instant."""

    x: float = 0.0
    y: float = 0.0
    is_down: bool = False


@dataclass
class SimSegment:
    """A drawn or travelled line segment."""

    x1: float
    y1: float
    x2: float
    y2: float
    is_draw: bool  # True = pen-down trace, False = pen-up travel


class VirtualPlotter:
    """Step-driven pen-plotter simulator.

    Call ``load_commands()`` once, then repeatedly call ``step(dt)``
    to advance the simulation.  Read ``pen`` and ``segments`` after
    each step to drive the UI.
    """

    def __init__(self, config: MotionConfig | None = None) -> None:
        self._cfg = config or MotionConfig()
        self._commands: list[MotionCommand] = []
        self._cmd_idx: int = 0
        self._progress: float = 0.0  # 0..1 within current DRAW/MOVE command
        self._start_x: float = 0.0
        self._start_y: float = 0.0
        self._speed_override: float | None = None

        # Public read-only state.
        self.pen = PenState()
        self.segments: list[SimSegment] = []
        self.finished: bool = True

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_commands(self, commands: list[MotionCommand]) -> None:
        self._commands = list(commands)
        self.reset()

    def reset(self) -> None:
        self._cmd_idx = 0
        self._progress = 0.0
        self._start_x = 0.0
        self._start_y = 0.0
        self.pen = PenState()
        self.segments.clear()
        self.finished = len(self._commands) == 0

    @property
    def total_commands(self) -> int:
        return len(self._commands)

    @property
    def current_command_index(self) -> int:
        return self._cmd_idx

    def set_speed_override(self, mm_per_s: float | None) -> None:
        """Override movement speed for all moves (None = use config defaults)."""
        self._speed_override = mm_per_s

    def step(self, dt: float) -> bool:
        """Advance simulation by *dt* seconds.  Returns True if more steps remain.

        After each call, inspect ``self.pen`` and ``self.segments``.
        """
        if self.finished:
            return False

        remaining = dt
        max_iter = 50  # safety cap to avoid infinite loops on zero-time commands
        while remaining > 0 and self._cmd_idx < len(self._commands) and max_iter > 0:
            max_iter -= 1
            cmd = self._commands[self._cmd_idx]
            consumed = self._execute_command(cmd, remaining)
            remaining -= consumed
            if self._progress >= 1.0:
                self._cmd_idx += 1
                self._progress = 0.0

        if self._cmd_idx >= len(self._commands):
            self.finished = True

        return not self.finished

    # ------------------------------------------------------------------
    # Command execution
    # ------------------------------------------------------------------

    def _execute_command(self, cmd: MotionCommand, dt: float) -> float:
        """Execute up to *dt* seconds of *cmd* and return time consumed."""
        if cmd.type == CmdType.PEN_UP:
            self.pen.is_down = False
            self._progress = 1.0
            return 0.0

        if cmd.type == CmdType.PEN_DOWN:
            self.pen.is_down = True
            self._start_x = self.pen.x
            self._start_y = self.pen.y
            self._progress = 1.0
            return 0.0

        if cmd.type in (CmdType.DRAW, CmdType.MOVE):
            return self._execute_move(cmd, dt)

        return 0.0

    def _execute_move(self, cmd: MotionCommand, dt: float) -> float:
        speed = self._speed_override or cmd.speed
        if speed <= 0:
            speed = self._cfg.write_speed if cmd.type == CmdType.DRAW else self._cfg.travel_speed
        if speed <= 0:
            speed = 20.0

        # A MOVE/DRAW command always starts at the endpoint of the previous
        # command. Keep this fixed while partially executing this command.
        if self._progress <= 0.0:
            self._start_x = self.pen.x
            self._start_y = self.pen.y

        dx = cmd.x - self._start_x
        dy = cmd.y - self._start_y
        total_dist = (dx * dx + dy * dy) ** 0.5
        if total_dist < 1e-6:
            self._progress = 1.0
            return 0.0

        total_time = total_dist / speed
        if self._progress >= 1.0:
            self._progress = 0.0

        # How much of this command we complete in dt seconds.
        advance = dt / total_time
        new_progress = min(1.0, self._progress + advance)
        consumed = (new_progress - self._progress) * total_time

        x1 = self.pen.x
        y1 = self.pen.y
        self.pen.x = self._start_x + dx * new_progress
        self.pen.y = self._start_y + dy * new_progress
        self._progress = new_progress

        # Record segment if the pen actually moved.
        if consumed > 1e-9 and (x1 != self.pen.x or y1 != self.pen.y):
            self.segments.append(SimSegment(
                x1=x1, y1=y1,
                x2=self.pen.x, y2=self.pen.y,
                is_draw=(cmd.type == CmdType.DRAW),
            ))

        return consumed
