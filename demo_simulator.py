from __future__ import annotations

from src.trajectory.config import MotionConfig
from src.trajectory.models import draw_to, move_to, pen_down, pen_up
from src.trajectory.simulator import VirtualPlotter


def main():
    # Build a simple "L" shape: pen down, draw horizontal, draw vertical, pen up.
    commands = [
        pen_down(),
        draw_to(50, 0, 20),
        draw_to(50, 80, 20),
        pen_up(),
        move_to(80, 30, 50),
        pen_down(),
        draw_to(120, 30, 20),
        draw_to(120, 70, 20),
        draw_to(80, 70, 20),
        draw_to(80, 30, 20),
        pen_up(),
    ]

    plotter = VirtualPlotter()
    plotter.load_commands(commands)

    print("Simulating pen plotter (L-shape + square)...")
    print("{:>8s} {:>6s} {:>8s} {:>6s} {:>6s} {:>6s}".format(
        "time(s)", "cmd#", "type", "x", "y", "pen"))
    print("-" * 52)

    t = 0.0
    while plotter.step(0.01):
        t += 0.01
        if int(t * 100) % 50 == 0:  # print every 0.5s
            cmd_idx = plotter.current_command_index
            cmd_type = commands[cmd_idx].type.name if cmd_idx < len(commands) else "DONE"
            print("{:8.2f} {:6d} {:>8s} {:6.1f} {:6.1f} {:>6s}".format(
                t, cmd_idx, cmd_type,
                plotter.pen.x, plotter.pen.y,
                "DOWN" if plotter.pen.is_down else "UP"))

    print("-" * 52)
    print("Simulation complete. {} segments drawn.".format(len(plotter.segments)))
    for i, seg in enumerate(plotter.segments):
        kind = "DRAW" if seg.is_draw else "TRAVEL"
        print("  {:5s} ({:6.1f},{:6.1f}) -> ({:6.1f},{:6.1f})".format(
            kind, seg.x1, seg.y1, seg.x2, seg.y2))


if __name__ == "__main__":
    main()
