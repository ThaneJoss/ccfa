"""Exercise the release artifacts offline in an isolated project copy."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parents[1]


class BuildTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="ccfa-build-test-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        for name in ("src", "data", "scripts"):
            shutil.copytree(ROOT / name, self.root / name)
        for name in ("manifest.json", "package.json"):
            shutil.copyfile(ROOT / name, self.root / name)
        self.manifest = json.loads((self.root / "manifest.json").read_text(encoding="utf-8"))
        self.xpi_name = f"ccfa-{self.manifest['version']}.xpi"

    def build(self):
        # Running outside the project also checks that the builder resolves its root.
        result = subprocess.run(
            [sys.executable, str(self.root / "scripts/build.py")],
            cwd=self.root.parent, capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_reproducible_archive_and_update_metadata(self):
        self.build()
        out = self.root / "dist"
        artifacts = {path.name: path.read_bytes() for path in out.iterdir()}
        self.assertEqual(set(artifacts), {self.xpi_name, "updates.json", "SHA256SUMS.txt"})
        digest = hashlib.sha256(artifacts[self.xpi_name]).hexdigest()
        self.assertEqual(artifacts["SHA256SUMS.txt"].decode(), f"{digest}  {self.xpi_name}\n")
        app = self.manifest["applications"]["zotero"]
        updates = json.loads(artifacts["updates.json"])["addons"]
        self.assertEqual(set(updates), {app["id"]})
        self.assertEqual(updates[app["id"]]["updates"], [{
            "version": self.manifest["version"],
            "update_link": f"https://github.com/ThaneJoss/ccfa/releases/download/v{self.manifest['version']}/{self.xpi_name}",
            "update_hash": "sha256:" + digest,
            "applications": {"zotero": {key: app[key] for key in ("strict_min_version", "strict_max_version")}},
        }])
        with ZipFile(out / self.xpi_name) as archive:
            self.assertIsNone(archive.testzip())
            self.assertEqual(set(archive.namelist()), {"manifest.json", "bootstrap.js", "matcher.js", "catalog.js"})
            self.assertEqual(json.loads(archive.read("manifest.json")), self.manifest)
            for name in ("bootstrap.js", "matcher.js"):
                self.assertEqual(archive.read(name), (self.root / "src" / name).read_bytes())

        # Changed input mtimes must not change any artifact bytes.
        for path in self.root.rglob("*"):
            if path.is_file() and out not in path.parents:
                os.utime(path, (946684800, 946684800))
        self.build()
        self.assertEqual({path.name: path.read_bytes() for path in out.iterdir()}, artifacts)

    def test_packaged_scripts_register_and_remove_a_working_column(self):
        self.build()
        unpacked = self.root / "unpacked"
        with ZipFile(self.root / "dist" / self.xpi_name) as archive:
            archive.extractall(unpacked)
        result = subprocess.run(["node", "-e", r'''
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const { pathToFileURL, fileURLToPath } = require('node:url');
const manifest = JSON.parse(fs.readFileSync('manifest.json', 'utf8'));
const catalog = JSON.parse(fs.readFileSync('../data/catalog.json', 'utf8'));
const id = manifest.applications.zotero.id;
const key = id + '-ccfa';
let column;
const removed = [];
const context = vm.createContext({
  Zotero: {
    initializationPromise: Promise.resolve(), debug() {},
    ItemTreeManager: {
      async registerColumn(options) { column = options; return key; },
      async unregisterColumn(value) { removed.push(value); }
    }
  },
  Services: { scriptloader: {
    loadSubScript(uri, scope) {
      vm.runInNewContext(fs.readFileSync(fileURLToPath(uri), 'utf8'), scope);
      if (uri.endsWith('/catalog.js')) {
        assert.deepEqual(JSON.parse(JSON.stringify(scope.CCFACatalog)), catalog);
      }
    }
  } }
});
vm.runInContext(fs.readFileSync('bootstrap.js', 'utf8'), context);
(async () => {
  await context.startup({ id, rootURI: pathToFileURL(process.cwd() + '/').href });
  assert.equal(column.label, 'CCFA');
  assert.equal(column.pluginID, id);
  for (const [venue, expected] of [['CVPR', 'CVPR'], ['CVPR Workshops', ''], ['IEEE Access', '']]) {
    assert.equal(column.dataProvider({
      isRegularItem: () => true,
      getField: field => field === 'publicationTitle' ? venue : '',
      setField() { throw new Error('Must not edit metadata'); },
      save() { throw new Error('Must not save items'); }
    }), expected);
  }
  await context.shutdown();
  assert.deepEqual(removed, [key]);
})().catch(error => { console.error(error); process.exitCode = 1; });
'''], cwd=unpacked, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_version_mismatch_fails_before_writing_artifacts(self):
        package_path = self.root / "package.json"
        package = json.loads(package_path.read_text(encoding="utf-8"))
        package["version"] = "0.0.0"
        package_path.write_text(json.dumps(package), encoding="utf-8")
        result = subprocess.run(
            [sys.executable, str(self.root / "scripts/build.py")],
            capture_output=True, text=True, timeout=30,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("version", result.stderr)
        self.assertFalse((self.root / "dist").exists())


if __name__ == "__main__":
    unittest.main()
