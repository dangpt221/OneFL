const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('../node_modules/typescript');
const exportsBox = {};
new Function('exports', ts.transpileModule(fs.readFileSync(path.join(__dirname, '../src/lib/cueTiming.ts'), 'utf8'), {
  compilerOptions: {module: ts.ModuleKind.CommonJS},
}).outputText)(exportsBox);
const validate = exportsBox.validateCueTiming;
assert.equal(validate('0', '1.234', 3), '');
for (const [start, end] of [['', '1'], ['0', ''], ['NaN', '1'], ['Infinity', '2'], ['-1', '2'], ['2', '1'], ['1', '1'], ['1', '4']]) {
  assert.ok(validate(start, end, 3), `Must reject ${start},${end}`);
}
assert.equal(validate('35999', '36000', 36000), '');
assert.equal(exportsBox.formatCueTimestamp(1.25), '00:01.250');
assert.equal(exportsBox.formatCueTimestamp(2.8), '00:02.800');
assert.equal(exportsBox.formatCueTimestamp(35999.9996), '10:00:00.000');
console.log('Timing inputs: finite, ordered, video-bound, zero and long-media boundaries passed');
