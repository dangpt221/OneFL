/* Run from root: node docs/reviews/reproduce_frontend_audit.cjs
 * Actual React SSR rerenders expose conditional hook counts without a browser.
 * Component modules are transpiled in memory; API/event handlers are not invoked.
 */
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.resolve(__dirname, '../..');
const deps = path.join(root, 'frontend/node_modules');
const ts = require(path.join(deps, 'typescript'));
const React = require(path.join(deps, 'react'));
const { renderToString } = require(path.join(deps, 'react-dom/server'));

function loadComponent(relativePath) {
  const source = fs.readFileSync(path.join(root, relativePath), 'utf8');
  const compiled = ts.transpileModule(source, {
    compilerOptions: {
      jsx: ts.JsxEmit.ReactJSX,
      module: ts.ModuleKind.CommonJS,
      target: ts.ScriptTarget.ES2020,
    },
  }).outputText;
  const exports = {};
  const sandbox = {
    exports,
    require(name) {
      if (name === 'react') return React;
      if (name === 'react/jsx-runtime') return require(path.join(deps, 'react/jsx-runtime'));
      if (name === 'lucide-react') return new Proxy({}, { get: () => () => null });
      if (name === '@/lib/api') return { api: {} };
      if (name === 'react-hot-toast') return { __esModule: true, default: {} };
      throw new Error(`Unexpected import ${name}`);
    },
  };
  vm.runInNewContext(compiled, sandbox, { filename: relativePath });
  return exports.default;
}

const results = [];
for (const [relativePath, props] of [
  ['frontend/src/components/CreateProjectModal.tsx', { onClose() {}, onSuccess() {} }],
  ['frontend/src/components/GlossaryModal.tsx', { terms: [], projectId: 'audit', onClose() {}, onUpdated() {} }],
]) {
  const Component = loadComponent(relativePath);
  function ClosedThenOpen() {
    const [isOpen, setIsOpen] = React.useState(false);
    if (!isOpen) setIsOpen(true);
    // Use the same React hook frame for both renders of the actual component.
    return Component({ ...props, isOpen });
  }
  let error;
  try {
    renderToString(React.createElement(ClosedThenOpen));
  } catch (caught) {
    error = caught.message;
  }
  if (!error || !error.includes('Rendered more hooks')) {
    throw new Error(`Expected conditional-hook failure for ${relativePath}; got ${error}`);
  }
  results.push({ component: relativePath, error });
}
console.log(JSON.stringify({ reproduced: results.length, results }, null, 2));
