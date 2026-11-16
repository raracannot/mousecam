// Run without the app: node tools/verify-cursor.mjs
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

const source = fs.readFileSync(new URL('../rust/mc-app/ui/app.js', import.meta.url), 'utf8');
const helper = source.slice(source.indexOf('function drawReplayCursor('), source.indexOf('function viewMapping('));
const state = {
  frame: 15, bake: { fps: 30 }, kfs: [],
  track: [[0, 1100, 700], [1, 1300, 900]],
  clip: { pointer_in_master: false },
};
let position, scale, draws;
const ctx = new Proxy({}, { get: (_, name) => (...args) => {
  if (name === 'translate') position = args;
  if (name === 'scale') scale = args;
  if (name === 'fill') draws++;
}, set: () => true });
const sandbox = { state };
vm.createContext(sandbox);
vm.runInContext(helper, sandbox);
const draw = (edited = false) => {
  position = scale = undefined;
  draws = 0;
  sandbox.drawReplayCursor(ctx, { x: 10, y: 20, w: 540, h: 304 }, [660, 496, 1080, 608], 1.2, edited);
};

draw();
assert.deepEqual(position, [280, 172]); // midpoint of trace, cropped + letterboxed
assert.deepEqual(scale, [0.6, 0.6]);
assert.equal(draws, 1);
state.frame = -30;
draw();
assert.deepEqual(position, [230, 122]); // clamp before first point
state.frame = 60;
draw();
assert.deepEqual(position, [330, 222]); // clamp after last point
state.frame = 15;
state.kfs = [{ t: 0, x: 1200, y: 800 }, { t: 1, x: 1400, y: 1000 }];
draw(true);
assert.deepEqual(position, [330, 222]); // edited follow point
draw();
assert.deepEqual(position, [280, 172]); // original view keeps recorded position
state.track = [];
draw();
assert.equal(draws, 0);
state.track = [[0, 1100, 700]];
draw();
assert.deepEqual(position, [230, 122]);
state.clip.pointer_in_master = true;
state.track = [[0, 1100, 700], [1, 1300, 900]];
draw();
assert.equal(draws, 0); // 0.2+ master already contains the pointer

assert.match(source, /drawReplayCursor\(ctx, box, mon\)/);
assert.match(source, /drawReplayCursor\(ctx, box, source, growth, true\)/);
console.log('PASS: replay cursor interpolation, bounds, keyframes, mapping and scale');
