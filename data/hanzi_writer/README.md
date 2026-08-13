# Hanzi Writer Data

This directory contains the offline stroke-order data used by the single-line
trajectory provider.

- Source: `hanzi-writer-data` 2.0.1
- Repository: https://github.com/chanind/hanzi-writer-data
- Upstream archive: `hanzi-writer-data-2.0.1.tgz`
- Archive SHA-256: `72baf3d82b114e60d6e40ea05f24d2262a05cd39d544e2f322ba2fceb7beff15`
- License: Arphic Public License, included as `ARPHICPL.TXT`

`medians-2.0.1.json.gz` is a modified runtime derivative. It retains only each
character's ordered `medians` arrays. Its embedded `_metadata.modified` field
records this modification. Rebuild it with:

```powershell
python scripts/build_hanzi_writer_index.py
```
