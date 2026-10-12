const { test } = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
const bootstrap = fs.readFileSync(path.join(root, 'src/bootstrap.js'), 'utf8');

function harness(initializationPromise = Promise.resolve(), registerGate) {
  const registrations = [];
  const removals = [];
  const context = vm.createContext({
    Zotero: {
      initializationPromise,
      debug() {},
      ItemTreeManager: {
        async registerColumn(options) {
          registrations.push(options);
          if (registerGate) await registerGate;
          return 'ccfa@thanejoss.github.io-ccfa';
        },
        async unregisterColumn(key) { removals.push(key); }
      }
    },
    Services: { scriptloader: {
      loadSubScript(uri, scope) {
        const script = uri.endsWith('/catalog.js')
          ? 'var CCFACatalog = ' + fs.readFileSync(path.join(root, 'data/catalog.json'), 'utf8')
          : fs.readFileSync(path.join(root, 'src/matcher.js'), 'utf8');
        vm.runInNewContext(script, scope);
      }
    } }
  });
  vm.runInContext(bootstrap, context);
  return { context, registrations, removals };
}
const params = { id: 'ccfa@thanejoss.github.io', rootURI: 'jar:file:///ccfa.xpi!/' };

test('plugin loads isolated scripts, exposes CCFA data and unregisters the returned key', async () => {
  const h = harness();
  await h.context.startup(params);
  const col = h.registrations[0];
  assert.equal(col.label, 'CCFA');
  assert.equal(col.pluginID, params.id);
  assert.equal(col.width, '100');
  assert.equal(col.dataProvider({ isRegularItem: () => true, getField: f => f === 'publicationTitle' ? 'CVPR' : '' }), 'CVPR');
  await h.context.shutdown();
  await h.context.shutdown();
  assert.deepEqual(h.removals, ['ccfa@thanejoss.github.io-ccfa']);
  await h.context.startup(params);
  assert.equal(h.registrations.length, 2);
  await h.context.shutdown();
});

test('disable while Zotero initializes does not leave a ghost column', async () => {
  let finish;
  const h = harness(new Promise(resolve => { finish = resolve; }));
  const starting = h.context.startup(params);
  await h.context.shutdown();
  finish();
  await starting;
  assert.equal(h.registrations.length, 0);
});

test('disable while registration awaits removes the late column', async () => {
  let finish;
  const h = harness(Promise.resolve(), new Promise(resolve => { finish = resolve; }));
  const starting = h.context.startup(params);
  await new Promise(resolve => setImmediate(resolve));
  await h.context.shutdown();
  finish();
  await starting;
  assert.equal(h.removals.length, 1);
});
