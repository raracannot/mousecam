// The preview clock must agree with what the export produces.
// Runs without the app: node tools/verify-playback.mjs
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

const source = fs.readFileSync(new URL('../rust/mc-app/ui/app.js', import.meta.url), 'utf8');
const grab = (name, next) => {
  const a = source.indexOf(`function ${name}(`);
  const b = source.indexOf(`function ${next}(`);
  assert.ok(a >= 0 && b > a, `${name} not found`);
  return source.slice(a, b);
};

const state = {
  trims: [], speeds: [], speedSel: -1,
  clip: { duration: 20 }, bake: { fps: 30 }, frame: 0,
  proxyReady: false, proxyStale: false,
};
const sandbox = {
  state, $: () => null, tc: (t) => t.toFixed(2),
  SPEED_MIN: 0.25, SPEED_MAX: 4, timeToX: () => 0, performance: { now: () => 0 },
};
vm.createContext(sandbox);
for (const [n, next] of [
  ['speedRate', 'keptSegs'],
  ['keptSegs', 'timelinePieces'],
  ['timelinePieces', 'speedDuration'],
  ['speedDuration', 'outToSrc'],
  ['outToSrc', 'srcToOut'],
  ['srcToOut', 'playingWithProxy'],
  ['playingWithProxy', 'syncSpeedControls'],
]) vm.runInContext(grab(n, next), sandbox);

// no edit: output seconds are source seconds
assert.equal(sandbox.speedDuration(), 20);
assert.equal(sandbox.outToSrc(7), 7);
assert.equal(sandbox.srcToOut(7), 7);

// one 4x region over 4..8: it plays in 1 s instead of 4
state.speeds = [{ a: 4, b: 8, speed: 4 }];
assert.equal(sandbox.speedDuration(), 17);
// output 4 s is still the start of the fast stretch
assert.equal(sandbox.outToSrc(4), 4);
// 0.5 s into the fast stretch is 2 source seconds in
assert.equal(sandbox.outToSrc(4.5), 6);
// the fast stretch occupies output 4..5, so half a second past it is source 8.5
assert.equal(sandbox.outToSrc(5.5), 8.5);
// the midpoint of the clip maps back where it came from
assert.equal(sandbox.srcToOut(6), 4.5);

// a slowed region: 0.25x over 4..8 turns 4 s into 16
state.speeds = [{ a: 4, b: 8, speed: 0.25 }];
assert.equal(sandbox.speedDuration(), 32);
assert.equal(sandbox.outToSrc(5), 4.25);

// trims compose: keep 2..12 (10 s), halve 4..8 (+4 s) => 14 s
state.speeds = [{ a: 4, b: 8, speed: 0.5 }];
state.trims = [{ a: 2, b: 12 }];
assert.equal(sandbox.speedDuration(), 14);
assert.equal(sandbox.outToSrc(0), 2);   // the trimmed range starts at source 2
assert.equal(sandbox.srcToOut(2), 0);
assert.equal(sandbox.srcToOut(10), 0 + 2 + 8 + 2); // 2 s normal, 8 s slow, 2 s normal

// round trip both ways across every boundary
state.speeds = [{ a: 3, b: 5, speed: 2 }, { a: 7, b: 9, speed: 0.5 }];
state.trims = [{ a: 1, b: 12 }];
for (const src of [1, 2.5, 3, 4, 5, 6, 7, 8, 9, 10, 11.5]) {
  const out = sandbox.srcToOut(src);
  const back = sandbox.outToSrc(out);
  assert.ok(Math.abs(back - src) < 1e-6, `round trip ${src} -> ${out} -> ${back}`);
}

// the rate the master should play at, per output second
state.speeds = [{ a: 4, b: 8, speed: 4 }];
state.trims = [];
const piece = sandbox.timelinePieces();
assert.equal(piece.length, 3);
assert.equal(piece[1].speed, 4);
assert.equal(piece[1].o, 4);
assert.equal(piece[1].b - piece[1].a, 4);

console.log('PASS: preview clock matches the export timeline (speed + trim mapping)');
