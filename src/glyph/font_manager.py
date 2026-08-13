"""Font discovery and loading — finds system Chinese TTF/OTF fonts."""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass
from pathlib import Path

from fontTools.ttLib import TTFont

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FontInfo:
    """Lightweight descriptor for a discovered font."""

    name: str
    path: Path
    is_chinese: bool = False


def _find_windows_fonts() -> list[FontInfo]:
    """Scan standard Windows font directories for .ttf/.ttc/.otf files."""
    font_dirs = [
        Path("C:/Windows/Fonts"),
        Path.home() / "AppData/Local/Microsoft/Windows/Fonts",
    ]
    result: list[FontInfo] = []
    seen_names: set[str] = set()

    for font_dir in font_dirs:
        if not font_dir.is_dir():
            continue
        for ext in ("*.ttf", "*.ttc", "*.otf"):
            for fp in font_dir.glob(ext):
                try:
                    name = fp.stem.lower()
                except Exception:
                    continue
                if name in seen_names:
                    continue
                seen_names.add(name)

                is_cjk = _is_cjk_font(fp)

                result.append(FontInfo(
                    name=fp.stem,
                    path=fp,
                    is_chinese=is_cjk,
                ))

    return result


def _is_cjk_font(path: Path) -> bool:
    """Check whether a font contains CJK code points by inspecting cmap table."""
    try:
        font = TTFont(path, fontNumber=0)
        cmap = font.getBestCmap()
        font.close()
        if cmap is None:
            return False
        # Check for presence of common CJK codepoints (CJK Unified Ideographs).
        cjk_samples = [0x4E2D, 0x6587, 0x4EBA, 0x56FD]  # 中, 文, 人, 国
        return any(cp in cmap for cp in cjk_samples)
    except Exception:
        return False


def _find_linux_fonts() -> list[FontInfo]:
    """Scan standard Linux font directories."""
    font_dirs = [
        Path("/usr/share/fonts"),
        Path("/usr/local/share/fonts"),
        Path.home() / ".fonts",
    ]
    result: list[FontInfo] = []
    seen_names: set[str] = set()

    for font_dir in font_dirs:
        if not font_dir.is_dir():
            continue
        for fp in font_dir.rglob("*"):
            if fp.suffix.lower() not in (".ttf", ".ttc", ".otf"):
                continue
            name = fp.stem.lower()
            if name in seen_names:
                continue
            seen_names.add(name)
            is_cjk = _is_cjk_font(fp)
            result.append(FontInfo(
                name=fp.stem,
                path=fp,
                is_chinese=is_cjk,
            ))

    return result


def _find_macos_fonts() -> list[FontInfo]:
    """Scan standard macOS font directories."""
    font_dirs = [
        Path("/System/Library/Fonts"),
        Path("/Library/Fonts"),
        Path.home() / "Library/Fonts",
    ]
    result: list[FontInfo] = []
    seen_names: set[str] = set()

    for font_dir in font_dirs:
        if not font_dir.is_dir():
            continue
        for ext in ("*.ttf", "*.ttc", "*.otf"):
            for fp in font_dir.glob(ext):
                name = fp.stem.lower()
                if name in seen_names:
                    continue
                seen_names.add(name)
                is_cjk = _is_cjk_font(fp)
                result.append(FontInfo(
                    name=fp.stem,
                    path=fp,
                    is_chinese=is_cjk,
                ))

    return result


def discover_fonts() -> list[FontInfo]:
    """Discover all available system fonts, marking which support Chinese."""
    if sys.platform == "win32":
        fonts = _find_windows_fonts()
    elif sys.platform == "darwin":
        fonts = _find_macos_fonts()
    else:
        fonts = _find_linux_fonts()

    chinese_count = sum(1 for f in fonts if f.is_chinese)
    logger.info("Discovered %d fonts, %d with Chinese support.", len(fonts), chinese_count)
    return fonts


def get_chinese_fonts() -> list[FontInfo]:
    """Return only fonts that support Chinese characters."""
    return [f for f in discover_fonts() if f.is_chinese]


def load_font(path: Path | str, font_index: int = 0) -> TTFont:
    """Load a TTFont from path.

    Args:
        path: Path to .ttf or .ttc file.
        font_index: For .ttc collections, which font face to load.

    Returns:
        An opened TTFont instance. Caller is responsible for closing it
        (or using it as a context manager).
    """
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"Font file not found: {path}")
    return TTFont(path, fontNumber=font_index)
