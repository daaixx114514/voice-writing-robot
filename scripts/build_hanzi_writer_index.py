"""Build the compact runtime median index from the official NPM archive."""

from __future__ import annotations

import gzip
import json
import tarfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "hanzi_writer"
ARCHIVE = DATA_DIR / "hanzi-writer-data-2.0.1.tgz"
OUTPUT = DATA_DIR / "medians-2.0.1.json.gz"


def main() -> None:
    characters: dict[str, list[list[list[int]]]] = {}
    with tarfile.open(ARCHIVE, "r:gz") as archive:
        for member in archive.getmembers():
            name = Path(member.name)
            if name.parent.as_posix() != "package" or name.suffix != ".json":
                continue
            char = name.stem
            if len(char) != 1:
                continue
            file_obj = archive.extractfile(member)
            if file_obj is None:
                continue
            payload = json.load(file_obj)
            medians = payload.get("medians")
            if medians:
                characters[char] = medians

    output = {
        "_metadata": {
            "source": "hanzi-writer-data 2.0.1",
            "source_url": "https://github.com/chanind/hanzi-writer-data",
            "license": "Arphic Public License; see ARPHICPL.TXT",
            "modified": (
                "Runtime derivative created by voice-writing-robot: only the "
                "character-to-medians fields were retained from the source JSON."
            ),
        },
        "characters": characters,
    }
    with gzip.open(OUTPUT, "wt", encoding="utf-8", compresslevel=9) as file_obj:
        json.dump(output, file_obj, ensure_ascii=False, separators=(",", ":"))

    print(f"Wrote {len(characters)} characters to {OUTPUT}")


if __name__ == "__main__":
    main()
