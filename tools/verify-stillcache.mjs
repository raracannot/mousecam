// The still cache must key on output time and drop when the edit changes.
// Runs without the app: node tools/verify-stillcache.mjs
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

function grabConst(name) {
  const a = source.indexOf(`const ${name} =`);
  assert.ok(a >= 0, `${name} not found`);
  return source.slice(a, source.indexOf('\n', a));
}

const state = {
  trims: [], speeds: [], speedSel: -1, clip: { dir: 'C:/rec/one', duration: 20 },
  bake: { fps: 30, frames: 600 }, frame: 0,
  proxyReady: false, proxyStale: false,
  stillCache: new Map(), stillCacheKey: '',
  viewImg: null, cropImg: null, stillPending: false, stillInFlight: false,
  useVideo: false, playing: false, edit: { zoom: 1 },
};

let editTextValue = 'zoom 1.0\n';
const sandbox = {
  state,
  $: () => null,
  invoke: () => {},
  SPEED_MIN: 0.25,
  SPEED_MAX: 4,
  timeToX: (_g, t) => t * 100,
  editText: () => editTextValue,
  // the same mapping the app uses, simplified to one 4x region
  srcToOut: (t) => {
    const sp = state.speeds[0];
    if (!sp) return t;
    if (t < sp.a) return t;
    if (t < sp.b) return sp.a + (t - sp.a) / sp.speed;
    return sp.a + (sp.b - sp.a) / sp.speed + (t - sp.b);
  },
};
vm.createContext(sandbox);
for (const n of ['stillCacheKey', 'clearStillCache', 'stillBucket']) {
  vm.runInContext(grab(n), sandbox);
}
vm.runInContext(grabConst('STILL_CACHE_MAX') + ';', sandbox);

// The bucket is an OUTPUT frame, so a sped-up stretch lines up with what the
// user sees rather than with the source frame under it.
state.frame = 0;
assert.equal(sandbox.stillBucket(), 0);
state.frame = 30;                       // source 1 s, no regions: output 1 s
assert.equal(sandbox.stillBucket(), 30);
state.speeds = [{ a: 2, b: 6, speed: 4 }];
state.frame = 60;                       // source 2 s is output 2 s
assert.equal(sandbox.stillBucket(), 60);
state.frame = 90;                       // source 3 s is 0.25 s into the 4x piece
assert.equal(sandbox.stillBucket(), 68); // 2 s + 0.25 s => output 2.25 s

// The key follows the clip, the edit text and the bake.
const k0 = sandbox.stillCacheKey();
assert.ok(k0.includes('C:/rec/one'), 'key should name the clip');
assert.equal(sandbox.stillCacheKey(), k0, 'same edit means the same key');
editTextValue = 'zoom 1.2\n';
assert.notEqual(sandbox.stillCacheKey(), k0, 'an edit change must invalidate');

state.speeds = [];
const k1 = sandbox.stillCacheKey();
state.clip = { dir: 'C:/rec/two', duration: 20 };
assert.notEqual(sandbox.stillCacheKey(), k1, 'another clip must invalidate');

// Clearing empties the map and forgets the key.
state.stillCache.set(1, {});
state.stillCacheKey = 'stale';
sandbox.clearStillCache();
assert.equal(state.stillCache.size, 0);
assert.equal(state.stillCacheKey, '');

console.log('PASS: still cache — output-time buckets, edit/clip keying and invalidation');
