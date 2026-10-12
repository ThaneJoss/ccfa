#!/usr/bin/env python3
"""Install the built XPI in a disposable, real Zotero 10 Linux profile.

Requires xvfb-run and the standard Zotero system libraries. No user profile is
used. The probe extension and all test data live under a temporary directory.
"""
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import tarfile
import tempfile
import time
from urllib.request import urlopen
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]
VERSION = "10.0.6"
manifest = json.loads((ROOT / "manifest.json").read_text())
addon_id = manifest["applications"]["zotero"]["id"]
xpi = ROOT / "dist" / f"ccfa-{manifest['version']}.xpi"
if not shutil.which("xvfb-run"):
    raise SystemExit("xvfb-run is required for the Zotero installation smoke test")


def download(url, destination):
    with urlopen(url, timeout=60) as source, destination.open("wb") as target:
        shutil.copyfileobj(source, target)


PROBE = r'''
function install() {}
function uninstall() {}
function shutdown() {}
function startup() { setTimeout(runProbe, 0); }

async function runProbe() {
  const config = __CONFIG__;
  const results = { zoteroVersion: Zotero.version, phase: config.phase, checks: [] };
  function check(condition, message) {
    if (!condition) throw new Error(message);
    results.checks.push(message);
  }
  async function columnExists(expected) {
    for (let attempt = 0; attempt < 100; attempt++) {
      const column = Zotero.ItemTreeManager.getCustomColumns()
        .find(c => c.pluginID === config.addonID);
      if (Boolean(column) === expected) return column;
      await new Promise(resolve => setTimeout(resolve, 100));
    }
    throw new Error('Column presence did not become ' + expected);
  }
  try {
    await Zotero.initializationPromise;
    const { AddonManager } = ChromeUtils.importESModule('resource://gre/modules/AddonManager.sys.mjs');
    if (config.phase === 'install') {
      const oldInstall = await AddonManager.getInstallForFile(Zotero.File.pathToFile(config.oldXPI));
      check(!oldInstall.addon.isCompatible, '1.0.0 reproduces the compatibility rejection on Zotero 10');
      oldInstall.cancel();
      const install = await AddonManager.getInstallForFile(Zotero.File.pathToFile(config.xpi));
      check(install.addon.isCompatible, 'New XPI passes the real addon compatibility check');
      await install.install();
    }
    const addon = await AddonManager.getAddonByID(config.addonID);
    check(addon && addon.version === config.version && addon.isActive, 'Installed version is active');
    let column = await columnExists(true);
    check(column.label === 'CCFA', 'Real item-tree column is named CCFA');
    const cases = [
      ['journalArticle', 'publicationTitle', 'IEEE Transactions on Pattern Analysis and Machine Intelligence', 'TPAMI'],
      ['journalArticle', 'publicationTitle', 'Proceedings of the AAAI Conference on Artificial Intelligence', 'AAAI'],
      ['conferencePaper', 'proceedingsTitle', '2025 IEEE/CVF Conference on Computer Vision and Pattern Recognition (CVPR)', 'CVPR'],
      ['conferencePaper', 'proceedingsTitle', 'International Conference on Learning Representations', 'ICLR'],
      ['conferencePaper', 'proceedingsTitle', 'CVPR Workshops', ''],
      ['journalArticle', 'publicationTitle', 'Machine Learning', '']
    ];
    for (const [type, field, value, expected] of cases) {
      const item = new Zotero.Item(type);
      item.setField(field, value);
      const actual = Zotero.ItemTreeManager.getCustomCellData(item, column.dataKey);
      check(actual === expected, 'Real Zotero item: ' + value + ' -> ' + expected);
    }
    if (config.phase === 'install') {
      await addon.disable();
      await columnExists(false);
      check(true, 'Disabling unregisters CCFA');
      await addon.enable();
      await columnExists(true);
      check(true, 'Re-enabling registers CCFA');
    }
    results.ok = true;
  } catch (error) {
    results.ok = false;
    results.error = String(error) + '\n' + (error.stack || '');
  }
  await IOUtils.writeUTF8(config.result, JSON.stringify(results, null, 2));
  Services.startup.quit(0x02); // nsIAppStartup.eForceQuit; flushes the disposable profile.
}
'''


with tempfile.TemporaryDirectory(prefix="ccfa-zotero-smoke-") as temporary:
    work = Path(temporary)
    archive = work / "zotero.tar.xz"
    download(f"https://download.zotero.org/client/release/{VERSION}/Zotero-{VERSION}_linux-x86_64.tar.xz", archive)
    with tarfile.open(archive) as package:
        package.extractall(work, filter="data")
    runtime = work / "Zotero_linux-x86_64" / "zotero"
    profile = work / "profile"
    extensions = profile / "extensions"
    extensions.mkdir(parents=True)
    data_dir = work / "data"
    data_dir.mkdir()
    old_xpi = work / "ccfa-1.0.0.xpi"
    download("https://github.com/ThaneJoss/ccfa/releases/download/v1.0.0/ccfa-1.0.0.xpi", old_xpi)
    preferences = {
        "extensions.zotero.dataDir": str(data_dir),
        "extensions.zotero.useDataDir": True,
        "extensions.zotero.firstRun": False,
        "extensions.zotero.firstRun2": False,
        "extensions.zotero.sync.autoSync": False,
        "extensions.zotero.automaticScraperUpdates": False,
        "extensions.autoDisableScopes": 0,
        "extensions.enabledScopes": 15,
        "extensions.update.enabled": False,
        "app.update.auto": False,
        "app.update.enabled": False,
        "browser.shell.checkDefaultBrowser": False,
    }
    (profile / "user.js").write_text("\n".join(
        f"user_pref({json.dumps(key)}, {json.dumps(value)});"
        for key, value in preferences.items()
    ))
    probe_id = "ccfa-smoke@local.test"
    probe_manifest = {
        "manifest_version": 2, "name": "CCFA Installation Test Probe", "version": "1.0.0",
        "applications": {"zotero": {"id": probe_id, "strict_min_version": "10.0", "strict_max_version": "10.0.*",
                                    "update_url": "https://example.invalid/updates.json"}}
    }
    # Read the config at runtime so the same probe can verify a second startup.
    config_path = work / "config.json"
    probe_source = PROBE.replace("const config = __CONFIG__;", f"const config = JSON.parse(await IOUtils.readUTF8({json.dumps(str(config_path))}));")
    with ZipFile(extensions / (probe_id + ".xpi"), "w", compression=ZIP_DEFLATED) as probe:
        probe.writestr("manifest.json", json.dumps(probe_manifest))
        probe.writestr("bootstrap.js", probe_source)

    reports = []
    for phase in ["install", "restart"]:
        result = work / f"{phase}.json"
        config_path.write_text(json.dumps({
            "phase": phase, "addonID": addon_id, "version": manifest["version"],
            "xpi": str(xpi), "oldXPI": str(old_xpi), "result": str(result)
        }))
        log = work / f"{phase}.log"
        with log.open("w") as output:
            process = subprocess.Popen(
                ["xvfb-run", "-a", str(runtime), "-no-remote", "-profile", str(profile), "-ZoteroDebugText"],
                stdout=output, stderr=subprocess.STDOUT, start_new_session=True,
                env={**os.environ, "MOZ_CRASHREPORTER_DISABLE": "1"}
            )
            try:
                deadline = time.monotonic() + 120
                while not result.exists() and process.poll() is None and time.monotonic() < deadline:
                    time.sleep(0.25)
                if not result.exists():
                    raise RuntimeError("Zotero probe did not complete:\n" + log.read_text(errors="replace")[-18000:])
                report = json.loads(result.read_text())
                print(json.dumps(report, indent=2), flush=True)
                if not report.get("ok"):
                    raise RuntimeError("Zotero test failed:\n" + log.read_text(errors="replace")[-18000:])
                reports.append(report)
            finally:
                if process.poll() is None:
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        os.killpg(process.pid, signal.SIGTERM)
                        try:
                            process.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            os.killpg(process.pid, signal.SIGKILL)
                            process.wait()
    (ROOT / "dist" / "zotero-smoke.json").write_text(json.dumps(reports, indent=2) + "\n")
    print("Real Zotero installation and restart checks passed.")
