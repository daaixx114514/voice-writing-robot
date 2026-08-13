from __future__ import annotations

from src.glyph.trajectory import PenState, Point2D, StrokePoint
from src.trajectory.config import MotionConfig
from src.trajectory.coordinate import CoordinateTransformer
from src.trajectory.motion import trajectory_to_commands
from src.trajectory.processor import TrajectoryProcessor


def main():
    cfg = MotionConfig(work_width_mm=200, work_height_mm=280,
                       min_point_distance=0.01, simplify_tolerance=0.05)
    processor = TrajectoryProcessor(cfg)
    transformer = CoordinateTransformer(cfg)
    transformer.fit_bounds(210, 297)

    # Simulate "shi" (cross): two independent strokes with curved paths
    raw = [
        StrokePoint(Point2D(15, 50), PenState.DOWN),
        StrokePoint(Point2D(22, 48), PenState.DOWN),
        StrokePoint(Point2D(30, 47), PenState.DOWN),
        StrokePoint(Point2D(40, 47), PenState.DOWN),
        StrokePoint(Point2D(50, 48), PenState.DOWN),
        StrokePoint(Point2D(60, 49), PenState.DOWN),
        StrokePoint(Point2D(70, 50), PenState.DOWN),
        StrokePoint(Point2D(80, 52), PenState.DOWN),
        StrokePoint(Point2D(88, 55), PenState.DOWN),
        StrokePoint(Point2D(88, 55), PenState.UP),
        StrokePoint(Point2D(50, 35), PenState.UP),
        StrokePoint(Point2D(50, 35), PenState.DOWN),
        StrokePoint(Point2D(48, 42), PenState.DOWN),
        StrokePoint(Point2D(47, 50), PenState.DOWN),
        StrokePoint(Point2D(48, 58), PenState.DOWN),
        StrokePoint(Point2D(50, 65), PenState.DOWN),
        StrokePoint(Point2D(52, 72), PenState.DOWN),
        StrokePoint(Point2D(55, 78), PenState.DOWN),
        StrokePoint(Point2D(55, 78), PenState.UP),
    ]

    sep = "=" * 72
    print(sep)
    print("Phase 2 Pipeline Demo -- writing char 'shi' (cross)")
    print(sep)

    print()
    print("[Step 1] Raw input: {} StrokePoints (Page coords, Y-down, top-left)".format(len(raw)))
    print("-" * 50)
    for sp in raw:
        m = "*" if sp.state == PenState.DOWN else "-"
        print("  {:5s} ({:6.1f}, {:6.1f}) {}".format(sp.state.name, sp.point.x, sp.point.y, m))

    cleaned = processor.process(raw)
    removed = len(raw) - len(cleaned)
    print()
    print("[Step 2] Processor: {} -> {} points ({} removed)".format(len(raw), len(cleaned), removed))
    for w in processor.warnings:
        print("  WARNING:", w)

    transformed = transformer.transform(cleaned)
    print()
    print("[Step 3] Coordinate transform: page {:.0f}x{:.0f}mm -> work {:.0f}x{:.0f}mm".format(
        transformer._page_w, transformer._page_h, cfg.work_width_mm, cfg.work_height_mm))
    print("   Scale: {:.3f}, Flip Y: {}".format(transformer._scale_x, cfg.flip_y))
    print("-" * 50)
    for sp in transformed:
        m = "*" if sp.state == PenState.DOWN else "-"
        print("  {:5s} ({:6.1f}, {:6.1f}) {}".format(sp.state.name, sp.point.x, sp.point.y, m))

    commands = trajectory_to_commands(transformed, cfg)
    print()
    print("[Step 4] MotionCommands ({} total)".format(len(commands)))
    print("-" * 50)
    for cmd in commands:
        if cmd.type.name in ("PEN_UP", "PEN_DOWN"):
            print("  {:9s}".format(cmd.type.name))
        else:
            spd = cfg.write_speed if cmd.type.name == "DRAW" else cfg.travel_speed
            print("  {:9s} ({:6.1f}, {:6.1f})  {:.0f} mm/s".format(cmd.type.name, cmd.x, cmd.y, spd))

    print()
    print(sep)
    print("Summary: {} raw -> {} cleaned -> {} transformed -> {} commands".format(
        len(raw), len(cleaned), len(transformed), len(commands)))
    print(sep)


if __name__ == "__main__":
    main()
