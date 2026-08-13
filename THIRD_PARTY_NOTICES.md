# Third-Party Notices

This project uses open-source software and data created by other people and
organizations. Their work remains subject to the respective upstream licenses.

This notice does not grant a license to this project's original source code.
No repository-wide project license has been selected yet; third-party material
remains available only under its respective upstream license.

## Data Distributed in This Repository

### Hanzi Writer Data 2.0.1

- Project: Hanzi Writer Data
- Upstream repository: https://github.com/chanind/hanzi-writer-data
- Copyright: the respective Hanzi Writer Data and underlying font-data authors
- License: Arphic Public License
- Local license copy: `data/hanzi_writer/ARPHICPL.TXT`

The following files are redistributed in this repository:

- `data/hanzi_writer/hanzi-writer-data-2.0.1.tgz`: unmodified upstream archive
- `data/hanzi_writer/medians-2.0.1.json.gz`: modified runtime derivative

The derivative retains only the ordered `medians` arrays required by the
single-line trajectory provider. Its embedded `_metadata.modified` field
describes this change. It can be rebuilt with
`scripts/build_hanzi_writer_index.py`. See `data/hanzi_writer/README.md` for the
archive checksum and additional provenance information.

## Runtime Dependencies

The project depends on the packages listed in `requirements.txt`. They are not
vendored in this repository and are installed separately under their own
licenses. Major direct dependencies include:

| Project | Purpose | Upstream | License |
| --- | --- | --- | --- |
| faster-whisper | Local speech recognition | https://github.com/SYSTRAN/faster-whisper | MIT |
| sounddevice | Microphone capture | https://github.com/spatialaudio/python-sounddevice | MIT |
| NumPy | Numeric and audio-buffer processing | https://github.com/numpy/numpy | BSD-3-Clause |
| PyTorch | Silero VAD runtime | https://github.com/pytorch/pytorch | BSD-style and bundled third-party licenses |
| torchaudio | PyTorch audio support | https://github.com/pytorch/audio | BSD-2-Clause |
| Silero VAD | Voice activity detection | https://github.com/snakers4/silero-vad | MIT |
| PyYAML | Configuration loading | https://github.com/yaml/pyyaml | MIT |
| zhconv | Traditional-to-simplified Chinese conversion | https://github.com/gumblex/zhconv | GPL-2.0-or-later |
| PySide6 / Qt for Python | Desktop user interface | https://code.qt.io/cgit/pyside/pyside-setup.git | LGPL-3.0-only or commercial/GPL options |
| fontTools | TrueType glyph processing | https://github.com/fonttools/fonttools | MIT |
| scikit-image | Optional glyph skeletonization | https://github.com/scikit-image/scikit-image | BSD-3-Clause |
| Pillow | Image processing support | https://github.com/python-pillow/Pillow | HPND |

This summary is provided for attribution and convenience. The authoritative
license terms are the license files and metadata distributed by each upstream
project and installed package.

## System Fonts

The application can read fonts already installed on the user's operating
system. Those font files are not included in this repository. Their use and
redistribution remain governed by the font owner's license.
