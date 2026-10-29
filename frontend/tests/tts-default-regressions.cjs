const assert = require('node:assert/strict');
const fs = require('node:fs'), path = require('node:path'), ts = require('typescript');
const helpers = {};
new Function('exports', ts.transpileModule(fs.readFileSync(path.resolve(__dirname, '../src/lib/ttsPresentation.ts'), 'utf8'), {
  compilerOptions: {module: ts.ModuleKind.CommonJS},
}).outputText)(helpers);
const {DEFAULT_TTS_VOICE, resolveDubbingVoice} = helpers;
assert.equal(DEFAULT_TTS_VOICE, 'vieneu-ngoc-huyen');
assert.equal(resolveDubbingVoice({}), DEFAULT_TTS_VOICE);
assert.equal(resolveDubbingVoice({default_voice: null, last_dub_config: null}), DEFAULT_TTS_VOICE);
assert.equal(resolveDubbingVoice({default_voice: 'vi-VN-NamMinhNeural'}), 'vi-VN-NamMinhNeural');
assert.equal(resolveDubbingVoice({default_voice: 'vieneu-ngoc-huyen', last_dub_config: {voice: 'nova'}}), 'nova');
assert.equal(resolveDubbingVoice({}, [{id: 'onyx', is_default: true}, {id: DEFAULT_TTS_VOICE}]), 'onyx');
assert.equal(resolveDubbingVoice({default_voice: 'vi-VN-HoaiMyNeural'}, [{id: DEFAULT_TTS_VOICE, is_default:true}]), 'vi-VN-HoaiMyNeural');
console.log('PASS TTS default: Ngoc Huyen, null metadata, configured catalog, saved project and dubbing voices');
