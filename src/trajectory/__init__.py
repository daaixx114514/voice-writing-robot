"""Motion control layer -- machine-agnostic trajectory processing.

Converts glyph writing paths into unified MotionCommand objects
ready for simulators or hardware adapters.
"""

from src.trajectory.config import MotionConfig
from src.trajectory.coordinate import CoordinateTransformer
from src.trajectory.models import CmdType, MotionCommand
from src.trajectory.motion import trajectory_to_commands
from src.trajectory.processor import TrajectoryProcessor

__all__ = [
    "CmdType",
    "CoordinateTransformer",
    "MotionCommand",
    "MotionConfig",
    "TrajectoryProcessor",
    "trajectory_to_commands",
]
