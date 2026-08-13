---
name: glyph-module-implementation
description: 语音写作机器人 — 轨迹生成 + 运动控制 + G-code + 虚拟写字机 + GUI 全栈实现
metadata:
  type: project
---

## 架构总览

```
语音 → faster-whisper → "你好世界"
→ src/glyph/ (文字 → 矢量轨迹)
→ src/trajectory/ (轨迹 → 运动指令)
→ VirtualPlotter / G-code / (未来: Arduino)
```

## 模块清单

| 模块 | 文件数 | 职责 |
|---|---|---|
| `src/glyph/` | 8 | 字体加载 → 字形提取 → 贝塞尔展平 → 排版 → SVG/预览 |
| `src/trajectory/` | 8 | 坐标变换 → 路径处理 → MotionCommand → 模拟器 → G-code |
| `src/gui/` | 7 | PySide6 UI: 录音控制 + 文本显示 + 轨迹预览 + 虚拟写字机 |
| `tests/` | 6 | 51 个测试全部通过 |

## 数据流

```
GlyphPath.contours (字体单位, Y-up)
  → LayoutEngine → Point2D (页面 mm, Y-down)
  → build_trajectory_points → StrokePoint[] (含 PenState)
  → CoordinateTransformer → 机械坐标 (mm, Y-up, bottom-left)
  → TrajectoryProcessor → 去重 + 简化
  → trajectory_to_commands → MotionCommand[] (PEN_UP/DOWN/MOVE/DRAW)
  → VirtualPlotter.step(dt) → 实时渲染
  → export_gcode() → G21/G90/G0/G1/M3/M5
```

## 关键参数 (MotionConfig)

| 参数 | 值 |
|---|---|
| work area | 200 × 280 mm |
| write speed | 20 mm/s |
| travel speed | 50 mm/s |
| simplify tolerance | 0.1 mm (Douglas-Peucker) |
| min point distance | 0.05 mm |

## GUI 操作

```
Start 录音 → Preview 看轨迹 → Simulate 看虚拟笔写字
Play/Pause/Stop + 速度 1x-20x
字体: STXINGKA (华文行楷), 用小写 "stxingka" 匹配
```

## Bug 修复记录

1. 程序崩溃: `_on_status_message` emit_status → 信号死循环 → 改 pass
2. preview NoneType: RecordingPen 输出 (None,None) → 加空值检查
3. STXINGKA 不匹配: 大写 vs f.name.lower() → 用小写 "stxingka"
4. 多余 `)`: main_window.py:210 → 删除

**Why:** 语音写作机器人的核心实现，从语音到矢量轨迹到运动指令全链路打通。
**How to apply:** 下一步串口通信 → 消费 MotionCommand，通过协议适配器转为硬件指令。
# 2026-08-13 quality update

- GUI default `use_skeleton=False`: STXINGKA keeps its original vector outlines.
- `GlyphExtractor` now decomposes TrueType quadratic segments with fontTools implied midpoints and keeps qCurveTo command boundaries.
- Closed contours restore their final segment to the start point.
- Motion processing uses conservative defaults: 0.02 mm minimum point distance and 0.03 mm Douglas-Peucker tolerance.
- Preview supports fit-to-page, wheel zoom around cursor, bounded zoom, resize fitting, and middle-button pan.
- Simulator paints machine Y-up coordinates through a display-only Y flip and uses floating-point Qt drawing.
- `MotionConfig` supports independent `flip_x` and `flip_y`.
- Regression status: 56 tests passing.

# 2026-08-13 single-line integration

- Added offline Hanzi Writer Data 2.0.1 with 9,574 ordered stroke-median records.
- Added `src/glyph/hanzi_writer.py`: lazy data loader and `SingleLineLayoutEngine`.
- Official coordinates `(0, 900)` to `(1024, -124)` map into page-space millimeters before the existing machine transform.
- One median array equals one pen-down stroke; inter-stroke pen-up behavior continues through `build_trajectory_points()`.
- Added corner-aware Hermite sampling for smoother physical movement while preserving source points, endpoints, and stroke boundaries.
- GUI now defaults to `Single-line strokes` and retains `Font outlines` as an explicit alternate source.
- Unsupported characters are reported; no silent outline fallback is performed in single-line mode.
- Source archive, SHA-256, derivative notice, rebuild script, and `ARPHICPL.TXT` are included.
- Final regression status: 63 tests passing.

# 2026-08-13 plotter motion correction

- Corrected first-stroke command order to `PEN_UP -> MOVE -> PEN_DOWN`.
- Every consecutive `DRAW`/`MOVE` now begins at the previous command endpoint.
- Added regression tests that reject fan-shaped return-to-start segments.
- Pen-up motion remains animated but is no longer rendered as a written trace.
- Design follows the continuous-polyline model used by plotter tooling such as AxiDraw, vpype, and Makelangelo.

# 2026-08-13 canvas navigation

- Preview and Simulate now include horizontal and vertical scrollbars.
- Scroll ranges activate after zooming beyond the viewport and stay disabled in Fit mode.
- Scrollbar movement and middle-button panning update the same canvas offsets.
- Cursor-centered wheel zoom and window resizing refresh scrollbar values and page steps.
