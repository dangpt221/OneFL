const assert = require('node:assert/strict');
const fs = require('node:fs'), ts = require('typescript'), Module = require('node:module');
const file = require('node:path').resolve(__dirname, '../src/lib/videoCleanup.ts');
const compiled = ts.transpileModule(fs.readFileSync(file, 'utf8'), {compilerOptions: {module: ts.ModuleKind.CommonJS}}).outputText;
const target = new Module(file); target._compile(compiled, file);
const {regionFromDrag, validCleanupRegions} = target.exports;
const bounds = {left: 100, top: 50, width: 400, height: 200};
assert.deepEqual(regionFromDrag([300, 150], [200, 100], bounds, 1.5), {
  x: .25, y: .25, width: .25, height: .25, track: false, reference_time: 1.5});
assert.equal(regionFromDrag([100, 50], [101, 51], bounds, 0), null);
assert.equal(regionFromDrag([100, 50], [600, 300], bounds, 0), null);
assert.equal(validCleanupRegions([{x: .9, y: 0, width: .2, height: .1}]), false);
assert.equal(validCleanupRegions([{x: NaN, y: 0, width: .2, height: .1}]), false);
assert.equal(validCleanupRegions([{x: .1, y: 0, width: .2, height: .1}]), true);
assert.equal(validCleanupRegions(Array(13).fill({x: .1, y: 0, width: .2, height: .1})), false);
console.log('PASS cleanup geometry: reverse drag, tiny/large masks, finite bounds and region limit');
