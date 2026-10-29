const fs = require('node:fs'), path = require('node:path'), assert = require('node:assert/strict');
const ts = require('../node_modules/typescript');
const code = ts.transpileModule(fs.readFileSync(path.join(__dirname, '../src/components/CreateProjectModal.tsx'), 'utf8'), {
  compilerOptions: {module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, jsx: ts.JsxEmit.ReactJSX},
}).outputText;
function harness() {
  const slots = [], pending = []; let cursor = 0;
  const react = {
    useState(initial) {const i = cursor++; slots[i] ||= {value: initial}; return [slots[i].value, value => {slots[i].value = typeof value === 'function' ? value(slots[i].value) : value;}];},
    useRef(initial) {return slots[cursor++] ||= {current: initial};}, useEffect() {},
  };
  const jsx = (type, props) => ({type, props});
  const mod = {};
  new Function('require', 'exports', 'console', code)(name => {
    if (name === 'react') return react;
    if (name === 'react/jsx-runtime') return {jsx, jsxs: jsx};
    if (name === 'lucide-react') return new Proxy({}, {get: () => () => null});
    if (name === 'react-hot-toast') return {__esModule: true, default: {error() {}}};
    if (name === '@/lib/api') return {api: {inspectUrlInfo: url => new Promise((resolve, reject) => pending.push({url, resolve, reject}))}};
    throw new Error(name);
  }, mod, {warn() {}});
  function render() {cursor = 0; return mod.default({isOpen: true, onClose() {}, onSuccess() {}});}
  function all(node, predicate, result = []) {
    if (!node || typeof node !== 'object') return result;
    if (predicate(node)) result.push(node);
    for (const child of [node.props?.children].flat(Infinity)) all(child, predicate, result);
    return result;
  }
  const nodes = predicate => all(render(), predicate);
  const input = () => nodes(x => x.type === 'input' && x.props.type === 'url')[0];
  return {
    pending,
    change(url) {input().props.onChange({target: {value: url}});},
    inspect(url) {return input().props.onBlur({target: {value: url}});},
    alerts() {return nodes(x => x.props?.role === 'alert');},
    inspecting() {return nodes(x => x.type === 'button' && x.props.children === 'Đang đọc...').length > 0;},
    preview(title) {return nodes(x => x.type === 'p' && x.props.children === title).length > 0;},
    upload() {nodes(x => x.type === 'button' && JSON.stringify(x.props.children).includes('Tải File Từ Máy'))[0].props.onClick();},
  };
}
(async () => {
  const A = 'https://www.bilibili.com/video/BV1MHh66uEFH/', B = 'https://www.bilibili.com/video/BV1RvaM6AEhi/';
  const failed = harness(); failed.change(A); const first = failed.inspect(A);
  failed.pending[0].resolve({success: false, error: 'Bilibili từ chối truy cập; tải file video lên từ máy tính.'}); await first;
  assert.equal(failed.alerts().length, 1, 'HTTP 200 with success:false must be visible');
  const transport = harness(); transport.change(A); const request = transport.inspect(A);
  transport.pending[0].reject(new Error('Proxy unavailable')); await request;
  assert.equal(transport.alerts().length, 1, 'Transport errors must be visible');
  const edited = harness(); edited.change(A); const stale = edited.inspect(A); edited.change(B);
  edited.pending[0].resolve({success: true, title: 'Old title'}); await stale;
  assert.equal(edited.preview('Old title'), false, 'Editing URL invalidates in-flight metadata');
  const racing = harness(); racing.change(A); const older = racing.inspect(A); racing.change(B); const newer = racing.inspect(B);
  racing.pending[0].resolve({success: false, error: 'Old failure'}); await older;
  assert.equal(racing.inspecting(), true, 'Old finally cannot clear the current loading flag');
  assert.equal(racing.alerts().length, 0, 'Old failure cannot replace current state');
  racing.pending[1].resolve({success: true, title: 'Current title'}); await newer;
  assert.equal(racing.preview('Current title'), true); assert.equal(racing.inspecting(), false);
  const switched = harness(); switched.change(A); const link = switched.inspect(A); switched.upload();
  switched.pending[0].resolve({success: false, error: 'Stale URL failure'}); await link;
  assert.equal(switched.alerts().length, 0, 'Switching to file upload invalidates URL errors');
  console.log('URL inspection: failure visibility, transport error, stale response/loading and source switch passed');
})().catch(error => {console.error(error); process.exitCode = 1;});
