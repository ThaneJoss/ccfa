/* global Zotero, Services */
"use strict";

var ccfaColumnKey = null;
var ccfaGeneration = 0;

function install() {}
function uninstall() {}

async function startup({ id, rootURI }) {
  const generation = ++ccfaGeneration;
  await Zotero.initializationPromise;
  if (generation !== ccfaGeneration) return;

  const scope = {};
  Services.scriptloader.loadSubScript(rootURI + "catalog.js", scope, "UTF-8");
  Services.scriptloader.loadSubScript(rootURI + "matcher.js", scope, "UTF-8");
  const matcher = scope.CCFAMatcher.create(scope.CCFACatalog);

  const key = await Zotero.ItemTreeManager.registerColumn({
    dataKey: "ccfa",
    label: "CCFA",
    pluginID: id,
    enabledTreeIDs: ["main"],
    width: "100",
    minWidth: 60,
    staticWidth: true,
    showInColumnPicker: true,
    zoteroPersist: ["width", "hidden", "ordinal", "sortDirection"],
    dataProvider(item) {
      return matcher.forItem(item);
    }
  });
  if (!key) throw new Error("CCFA: failed to register the item-list column");
  if (generation !== ccfaGeneration) {
    await Zotero.ItemTreeManager.unregisterColumn(key);
    return;
  }
  ccfaColumnKey = key;
  Zotero.debug("CCFA: loaded 2026 catalog (37 journals, 58 conferences)");
}

async function shutdown() {
  ++ccfaGeneration;
  const key = ccfaColumnKey;
  ccfaColumnKey = null;
  if (key) await Zotero.ItemTreeManager.unregisterColumn(key);
}
