const assert = require('node:assert/strict');
const fs = require('node:fs'), path = require('node:path'), ts = require('typescript');
const exports_ = {};
new Function('exports', ts.transpileModule(fs.readFileSync(path.resolve(__dirname, '../src/lib/burnPresentation.ts'), 'utf8'), {
  compilerOptions: {module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020},
}).outputText)(exports_);
const {resolveBurnPresentation, comicText, subtitlePreviewStyle} = exports_;
const defaults = resolveBurnPresentation();
assert.deepEqual(resolveBurnPresentation(null), defaults, 'API returns null for unconfigured projects');
assert.equal(defaults.clean_chinese_mode, 'white_bars'); assert.equal(defaults.subtitle_preset, 'comic');
assert.equal(defaults.top_mask_pct, 11); assert.equal(defaults.bottom_mask_pct, 15);
assert.equal(resolveBurnPresentation({mask_original_sub: false}).clean_chinese_mode, 'none');
const saved = resolveBurnPresentation({clean_chinese_mode: 'smart_blur', subtitle_preset: 'yellow_highlight', top_mask_pct: 0, bottom_mask_pct: 23});
assert.equal(saved.clean_chinese_mode, 'smart_blur'); assert.equal(saved.subtitle_preset, 'yellow_highlight');
assert.equal(saved.top_mask_pct, 0); assert.equal(saved.bottom_mask_pct, 23);
const clamped = resolveBurnPresentation({top_mask_pct: Infinity, bottom_mask_pct: -2});
assert.equal(clamped.top_mask_pct, 11); assert.equal(clamped.bottom_mask_pct, 0);
const text = 'Ta đã hỏi ở Túy Tiên Lầu rồi, mười hai bàn tiệc.';
assert.equal(comicText(text), 'TA ĐÃ HỎI Ở TÚY TIÊN LẦU RỒI, MƯỜI HAI BÀN TIỆC.');
assert.equal(text, 'Ta đã hỏi ở Túy Tiên Lầu rồi, mười hai bàn tiệc.');
const style = subtitlePreviewStyle('comic', 640, 360);
assert.equal(style.fontStyle, 'italic'); assert.equal(style.fontWeight, 700);
assert.equal(style.fontSize, 18); assert.equal(style.color, '#ffffff');
assert.ok(style.WebkitTextStroke.includes('black'));
assert.equal(style.transform, 'scaleX(0.8)'); assert.equal(style.backgroundColor, 'transparent');
assert.ok(Number.isFinite(subtitlePreviewStyle('comic', 0, 0).fontSize));
console.log('PASS presentation: white/comic defaults, saved/none/zero masks, finite clamping and Unicode/scaled style');
