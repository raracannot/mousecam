// The still cache must file a render under the frame it actually rendered,
// evict by bytes, and refuse to file anything that finished after the cache was
// cleared. Runs without the app: node tools/verify-stillcache.mjs
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

const source = fs.readFileSync(new URL('../rust/mc-app/ui/app.js', import.meta.url), 'utf8');

// Slice from `function name(` up to whatever declaration comes next in the file.
function grab(name) {
  const a = source.indexOf(`function ${name}(`);
  assert.ok(a >= 0, `${name} not found`);
  const rest = source.slice(a + 10);
  const nextDecl = rest.search(/\n(?:function |const |let |var )/);
  return source.slice(a, nextDecl < 0 ? source.length : a + 10 + nextDecl);
}

function grabDecl(prefix) {
  const a = source.indexOf(prefix);
  assert.ok(a >= 0, `${prefix} not found`);
  return source.slice(a, source.indexOf('\n', a));
}

const state = {
  trims: [], speeds: [], speedSel: -1,
  clip: { dir: 'C:/rec/one', duration: 20 },
  bake: { fps: 30, frames: 600 },
  frame: 0,
  proxyReady: false, proxyStale: false,
  stillCache: new Map(), stillCacheBytes: 0, stillCacheKey: '',
  viewImg: null, cropImg: null, stillPending: false, stillInFlight: false,
  useVideo: false, playing: false, recording: false,
  edit: { zoom: 1 },
};

let editTextValue = 'zoom 1.0\n';
const stillCalls = [];
let gate = null;                       // when set, invoke resolves on this promise

const sandbox = {
  state,
  $: () => null,
  document: { hidden: false },
  invoke: (_cmd, args) => {
    stillCalls.push(args.frame);
    const value = Promise.resolve(`data:image/jpeg;base64,frame${args.frame}-${args.kind}`);
    return gate ? gate.then(() => value) : value;
  },
  loadImg: (src) => Promise.resolve({ src, naturalWidth: 900, naturalHeight: 506 }),
  editText: () => editTextValue,
  stillGen: 0,
};
vm.createContext(sandbox);
for (const n of ['stillCacheKey', 'clearStillCache', 'stillFrame', 'stillBytes',
                 'rememberStill', 'fetchStill', 'bakeStill']) {
  vm.runInContext(grab(n), sandbox);
}
vm.runInContext(grabDecl('const STILL_CACHE_BYTES'), sandbox);
vm.runInContext(grabDecl('const stillInflight'), sandbox);

// ---- the key is the source frame, clamped to the take ----
state.frame = 42;
assert.equal(sandbox.stillFrame(), 42);
state.frame = -5;
assert.equal(sandbox.stillFrame(), 0);
state.frame = 9999;
assert.equal(sandbox.stillFrame(), 599);

// ---- a bake renders THE FRAME IT WAS GIVEN, not the playhead ----
// This is the bug the first version had: it rendered state.frame and filed the
// result under the neighbour key the prefetcher asked for.
state.frame = 100;
stillCalls.length = 0;
const entry = await sandbox.bakeStill(12);
assert.deepEqual([...new Set(stillCalls)], [12], `invoke saw frames ${stillCalls}`);
assert.ok(state.stillCache.has(12), 'the entry is filed under its own frame');
assert.ok(!state.stillCache.has(100), 'nothing is filed under the playhead');
assert.equal(entry.view.src, 'data:image/jpeg;base64,frame12-view');

// A hit does not decode again.
stillCalls.length = 0;
await sandbox.bakeStill(12);
assert.equal(stillCalls.length, 0);

// Two callers asking for one frame share a single decode.
state.stillCache.clear();
state.stillCacheBytes = 0;
stillCalls.length = 0;
await Promise.all([sandbox.bakeStill(7), sandbox.bakeStill(7)]);
assert.equal(stillCalls.length, 2, 'expected one view + one crop, not four');

// ---- the budget is in bytes and evicts the oldest ----
state.stillCache.clear();
state.stillCacheBytes = 0;
const big = { view: { naturalWidth: 900, naturalHeight: 506 }, crop: { naturalWidth: 620, naturalHeight: 348 } };
const oneBytes = sandbox.stillBytes(big.view) + sandbox.stillBytes(big.crop);
// The budget lives in the app source; read it rather than repeating it here.
const budget = vm.runInContext('STILL_CACHE_BYTES', sandbox);
assert.ok(budget > 0, 'budget should be a positive byte count');
const fits = Math.floor(budget / oneBytes);
for (let i = 0; i < fits + 5; i++) sandbox.rememberStill(i, { ...big, bytes: oneBytes });
assert.ok(state.stillCache.size <= fits + 1, `kept ${state.stillCache.size} for a budget of ${fits}`);
assert.ok(state.stillCacheBytes <= budget, `bytes ${state.stillCacheBytes} > ${budget}`);
assert.ok(!state.stillCache.has(0), 'the oldest entry goes first');

// ---- a bake that lands after a clear must not be filed ----
state.stillCache.clear();
state.stillCacheBytes = 0;
let release;
gate = new Promise((r) => { release = r; });
const pending = sandbox.bakeStill(33);
sandbox.clearStillCache();
release();
gate = null;
await pending;
assert.equal(state.stillCache.size, 0, 'a stale bake leaked into the cleared cache');

// ---- the key follows the clip and the edit ----
const k0 = sandbox.stillCacheKey();
assert.ok(k0.includes('C:/rec/one'), 'key should name the clip');
editTextValue = 'zoom 1.2\n';
assert.notEqual(sandbox.stillCacheKey(), k0, 'an edit change must invalidate');
state.clip = { dir: 'C:/rec/two', duration: 20 };
assert.notEqual(sandbox.stillCacheKey(), k0, 'another clip must invalidate');

// ---- clearing empties the map, the byte count and the key ----
state.stillCache.set(1, {});
state.stillCacheBytes = 123;
state.stillCacheKey = 'stale';
sandbox.clearStillCache();
assert.equal(state.stillCache.size, 0);
assert.equal(state.stillCacheBytes, 0);
assert.equal(state.stillCacheKey, '');

console.log('PASS: still cache — source-frame keying, single decode, byte budget, stale-bake guard');
