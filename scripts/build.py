#!/usr/bin/env python3
"""Reproducible XPI build using only the Python standard library."""
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]
manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
catalog = json.loads((ROOT / "data/catalog.json").read_text(encoding="utf-8"))
assert len(catalog["venues"]) == 95
assert sum(v["type"] == "journal" for v in catalog["venues"]) == 37
version = manifest["version"]
out = ROOT / "dist"
out.mkdir(exist_ok=True)
xpi = out / f"ccfa-{version}.xpi"
files = {
    "manifest.json": (ROOT / "manifest.json").read_bytes(),
    "bootstrap.js": (ROOT / "src/bootstrap.js").read_bytes(),
    "matcher.js": (ROOT / "src/matcher.js").read_bytes(),
    "catalog.js": ("var CCFACatalog = " + json.dumps(catalog, ensure_ascii=False, separators=(",", ":")) + ";\n").encode("utf-8"),
}
with ZipFile(xpi, "w") as archive:
    for name, content in sorted(files.items()):
        info = ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
        info.compress_type = ZIP_DEFLATED
        info.external_attr = 0o100644 << 16
        archive.writestr(info, content, compresslevel=9)
digest = hashlib.sha256(xpi.read_bytes()).hexdigest()
(out / "SHA256SUMS.txt").write_text(f"{digest}  {xpi.name}\n", encoding="utf-8")
app = manifest["applications"]["zotero"]
update = {"addons": {app["id"]: {"updates": [{
    "version": version,
    "update_link": f"https://github.com/ThaneJoss/ccfa/releases/download/v{version}/{xpi.name}",
    "update_hash": "sha256:" + digest,
    "applications": {"zotero": {k: app[k] for k in ("strict_min_version", "strict_max_version")}}
}]}}}
(out / "updates.json").write_text(json.dumps(update, indent=2) + "\n", encoding="utf-8")
with ZipFile(xpi) as archive:
    assert archive.testzip() is None
    assert set(archive.namelist()) == set(files)
print(f"Built {xpi.name}: {xpi.stat().st_size} bytes; SHA-256 {digest}")
