// Speed regions: normalization and the edit-line round trip.
// The source-time mapping itself is covered by verify-playback.mjs.
// Runs without the app: node tools/verify-speed.mjs
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
  clip: { duration: 10 }, bake: { fps: 30 }, frame: 0,
};
const sandbox = {
  state,
  tc: (t) => t.toFixed(2),
  $: () => null,
  SPEED_MIN: 0.25,
  SPEED_MAX: 4,
  timeToX: () => 0,
};
vm.createContext(sandbox);
for (const [n, next] of [
  ['normalizeSpeeds', 'speedTotal'],
]) vm.runInContext(grab(n, next), sandbox);

// overlapping regions: the newcomer keeps only what lies past the older one
state.trims = [];
state.speeds = [{ a: 0, b: 5, speed: 2 }, { a: 3, b: 8, speed: 4 }];
sandbox.normalizeSpeeds();
assert.equal(state.speeds.length, 2);
assert.equal(state.speeds[1].a, 5);
assert.equal(state.speeds[1].b, 8);

// speed is clamped into the supported range
state.speeds = [{ a: 0, b: 2, speed: 99 }, { a: 3, b: 4, speed: 0.01 }];
sandbox.normalizeSpeeds();
assert.equal(state.speeds[0].speed, 4);
assert.equal(state.speeds[1].speed, 0.25);

// the speed line the UI writes is the one the engine parses
state.speeds = [{ a: 1, b: 3.5, speed: 2 }];
const lines = [`speed ${state.speeds[0].a.toFixed(3)} ${state.speeds[0].b.toFixed(3)} ${state.speeds[0].speed.toFixed(3)}`];
assert.equal(lines[0], 'speed 1.000 3.500 2.000');

console.log('PASS: speed regions — overlap, clamp and serialization');
