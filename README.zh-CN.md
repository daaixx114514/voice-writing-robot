# 智能语音写字机器人

[English](README.md) | [简体中文](README.zh-CN.md)

这是一个面向 Windows 桌面的中文语音写字项目。程序可以从麦克风录音，识别中文文本，把文字转换为按笔画排列的二维轨迹，再生成与具体设备无关的运动命令。目前已经实现虚拟绘图机和 GRBL G-code 导出，真实硬件与串口通信尚未接入。

```text
麦克风
  -> Silero VAD
  -> faster-whisper 中文识别
  -> 中文文本
  -> 单线笔画或字体轮廓
  -> WritingTrajectory
  -> MotionCommand
  -> 虚拟绘图机 / G-code
```

项目针对 Windows 11、Python 3.10/3.11 和无独立显卡的电脑开发。默认使用 CPU 与 int8 推理，不需要 CUDA。

## 已实现功能

- 使用 `sounddevice` 采集 16 kHz 单声道音频，不支持 16 kHz 的设备会自动使用默认采样率并重采样。
- 使用 Silero VAD 判断语音起止，保留短暂的预录音并在连续静音后停止。
- 使用 faster-whisper 在本地识别中文，支持热词和繁体转简体。
- PySide6 桌面界面，录音和识别在后台线程执行。
- 两种文字轨迹来源：Hanzi Writer Data 单线笔画、系统字体轮廓。
- 页面布局、坐标转换、轨迹去重和 Douglas-Peucker 简化。
- 与设备无关的 `MotionCommand`：抬笔、落笔、空移和书写。
- 虚拟绘图机，支持播放、暂停、停止、调速、缩放和平移。
- GRBL 兼容的 G-code 导出。
- 67 项自动化测试。

## 项目结构

```text
voice-writing-robot/
├── config/                    # 音频和语音识别配置
├── data/hanzi_writer/         # Hanzi Writer Data 及许可证
├── scripts/                   # 数据构建脚本
├── src/
│   ├── audio/                 # 麦克风采集与 VAD
│   ├── stt/                   # faster-whisper 中文识别
│   ├── glyph/                 # 字形、单线笔画与页面轨迹
│   ├── trajectory/            # 坐标、运动命令、模拟器、G-code
│   ├── gui/                   # PySide6 桌面界面
│   └── utils/                 # 配置加载
├── tests/
├── README.md
├── README.zh-CN.md
└── THIRD_PARTY_NOTICES.md
```

主要入口：

- `src/gui/main.py`：PySide6 桌面程序。
- `src/main.py`：命令行语音识别。
- `demo_glyph.py`：文字轨迹与 SVG 示例。
- `demo_trajectory.py`：运动命令示例。
- `demo_simulator.py`：虚拟绘图机示例。

## 安装

创建并激活虚拟环境：

```powershell
cd "D:\My Code\voice-writing-robot"
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
```

先安装 CPU 版本的 PyTorch：

```powershell
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu
```

再安装其余依赖：

```powershell
pip install -r requirements.txt
```

首次运行 faster-whisper 时可能会下载模型。模型缓存完成后，语音识别可以离线运行。

## 运行

启动 PySide6 桌面程序：

```powershell
python -m src.gui.main
```

也可以双击 `run.bat`。

查看可用麦克风：

```powershell
python -m src.main --list-devices
```

识别一段语音后退出：

```powershell
python -m src.main --once
```

连续识别：

```powershell
python -m src.main
```

运行测试：

```powershell
python -m pytest tests -q
```

## 配置

运行参数在 `config/stt.yaml` 中。当前推荐的 CPU 配置是：

```yaml
stt:
  model_size: small
  device: cpu
  compute_type: int8
  language: zh
```

`small` 的中文准确率通常好于 `base`，但首次下载更大、识别更慢。内存或响应时间紧张时可以改用 `base`。

音频配置包括设备编号、采样率、VAD 阈值、静音时长和最长录音时间。如果所选麦克风不支持 16 kHz，录音模块会读取设备默认采样率，再转换为 16 kHz 供 VAD 和识别器使用。

## 文字轨迹与运动命令

GUI 默认使用 Hanzi Writer Data 的有序 `medians` 数据。每个 median 对应一条连续笔画，笔画之间会抬笔，因此它比字体外轮廓更适合绘图机。

```python
from src.glyph import HanziWriterData, LayoutConfig, SingleLineLayoutEngine
from src.glyph import build_trajectory

engine = SingleLineLayoutEngine(
    HanziWriterData(),
    LayoutConfig(char_size=14.0, page_width=148, page_height=210),
)
trajectory = build_trajectory(engine, "你好")
```

轨迹经过清理和坐标变换后，会转换为四种运动命令：

```text
PEN_UP    抬笔
PEN_DOWN  落笔
MOVE      抬笔移动
DRAW      落笔书写
```

这层模型不包含 GRBL、Arduino 或串口细节，后续可以让模拟器和真实硬件共用同一组命令。

## 当前限制

- 尚未实现 Hardware Backend、串口协议和真实设备状态管理。
- 尚未连接 Arduino、GRBL 控制板或步进电机。
- G-code 导出器已经可用，但不同机器的抬笔命令、坐标方向和速度仍需实机校准。
- 字体轮廓描述的是字形边界，不等同于单线书写笔画；正常使用应优先选择单线笔画数据。
- `src/gui/app.py` 是保留的旧版 Tkinter 界面，当前桌面入口是 `src/gui/main.py`。

## 常见问题

### 找不到麦克风

先运行：

```powershell
python -m src.main --list-devices
```

然后把设备编号写入 `config/stt.yaml`：

```yaml
audio:
  device: 1
```

还要确认 Windows 已允许桌面应用使用麦克风，并关闭可能独占录音设备的软件。

### Silero VAD 下载或缓存错误

项目使用 PyPI 上的 `silero-vad`，不通过 `torch.hub` 加载。遇到旧缓存相关错误时，重新安装依赖即可：

```powershell
pip install silero-vad
```

### 识别速度较慢

先确认使用 `device: cpu` 和 `compute_type: int8`。需要更低延迟时，把 `model_size` 从 `small` 改为 `base`。

## 第三方软件与数据

本项目使用了其他作者和组织发布的开源软件与数据。

单线汉字轨迹来自 [Hanzi Writer Data](https://github.com/chanind/hanzi-writer-data) 2.0.1，按 Arphic Public License 分发。仓库中包含未经修改的上游压缩包，以及只保留有序 `medians` 字段的运行时派生文件。具体修改说明、校验值和许可证位于：

- `data/hanzi_writer/README.md`
- `data/hanzi_writer/ARPHICPL.TXT`
- `THIRD_PARTY_NOTICES.md`

语音识别、VAD、GUI、字体处理和数值计算依赖 faster-whisper、Silero VAD、PySide6、fontTools、NumPy、PyTorch 等项目。这些依赖没有复制到本仓库中，安装和使用仍受各自许可证约束。完整来源及许可证摘要见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。

程序运行时可以读取操作系统已经安装的字体，但仓库不包含这些字体文件。

本仓库目前没有为原创源代码选择统一的项目许可证。公开仓库允许查看代码，但第三方许可证和公开可见性不等于自动授予复制、修改或再发布原创代码的权利。
