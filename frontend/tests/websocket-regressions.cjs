/* Exercise the actual hook with controlled effect lifetimes, timers and sockets. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('../node_modules/typescript');
const code = ts.transpileModule(fs.readFileSync(path.join(__dirname, '../src/lib/useWebSocket.ts'), 'utf8'), {
  compilerOptions: {module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020},
}).outputText;

function harness(protocol = 'http:') {
  const slots = [], effects = [], timers = new Map(), sockets = [], redirects = [], parseErrors = [];
  let cursor = 0, timerId = 0, now = 0, projectId;
  const schedule = (fn, delay = 0, interval = false) => {
    const id = ++timerId; timers.set(id, {fn, due: now + delay, interval, delay}); return id;
  };
  const react = {
    useState(initial) {
      const i = cursor++;
      if (!slots[i]) slots[i] = {value: initial};
      return [slots[i].value, next => {slots[i].value = typeof next === 'function' ? next(slots[i].value) : next;}];
    },
    useRef(initial) {const i = cursor++; return slots[i] ||= {current: initial};},
    useEffect(fn, deps) {
      const i = cursor++, old = slots[i];
      if (!old || deps.some((value, index) => value !== old.deps[index])) {
        const next = {deps, cleanup: undefined}; slots[i] = next;
        effects.push(() => {old?.cleanup?.(); next.cleanup = fn();});
      }
    },
  };
  class Socket {
    static CONNECTING = 0; static OPEN = 1; static CLOSING = 2; static CLOSED = 3;
    readyState = 0; onopen = null; onmessage = null; onclose = null; onerror = null;
    closes = 0; prematureCloses = 0; sent = [];
    constructor(url) {this.url = url; sockets.push(this);}
    open() {this.readyState = 1; this.onopen?.({});}
    close() {this.closes++; if (this.readyState === 0) this.prematureCloses++; this.readyState = 2;}
    closed(code = 1006) {this.readyState = 3; this.onclose?.({code});}
    message(project_id, data = {message: 'update'}) {this.onmessage?.({data: JSON.stringify({type: 'STATUS_UPDATE', project_id, data})});}
    send(data) {assert.equal(this.readyState, 1); this.sent.push(data);}
  }
  const mod = {};
  new Function('require', 'exports', 'WebSocket', 'window', 'setTimeout', 'clearTimeout', 'setInterval', 'clearInterval', 'console', code)(
    name => {assert.equal(name, 'react'); return react;}, mod, Socket,
    {location: {protocol, host: 'localhost:3000', assign: url => redirects.push(url)}},
    (fn, delay) => schedule(fn, delay), id => timers.delete(id),
    (fn, delay) => schedule(fn, delay, true), id => timers.delete(id),
    {error: (...args) => parseErrors.push(args)},
  );
  const render = () => {cursor = 0; return mod.useProjectWebSocket(projectId);};
  const flush = () => {while (effects.length) effects.shift()();};
  return {
    sockets, redirects, timers, parseErrors,
    render(id) {projectId = id; const result = render(); flush(); return result;},
    value() {const result = render(); flush(); return result;},
    dispose() {for (const slot of slots) slot?.cleanup?.();},
    tick(ms = 0) {
      const end = now + ms;
      while (true) {
        const next = [...timers].filter(([, t]) => t.due <= end).sort((a, b) => a[1].due - b[1].due)[0];
        if (!next) break;
        const [id, timer] = next; now = timer.due;
        if (timer.interval) timer.due += timer.delay; else timers.delete(id);
        timer.fn();
      }
      now = end;
    },
  };
}

const cases = {
  'discarded effect opens no socket': () => {
    const h = harness(); h.render('A'); h.dispose(); h.tick(30000);
    assert.equal(h.sockets.length, 0); assert.equal(h.timers.size, 0);
  },
  'cleanup retires pending handshake without aborting it': () => {
    const h = harness(); h.render('A'); h.tick(); const s = h.sockets[0];
    h.dispose(); assert.equal(s.prematureCloses, 0); s.open();
    assert.equal(s.closes, 1); assert.equal(h.value().isConnected, false);
    s.closed(); h.tick(60000); assert.equal(h.sockets.length, 1); assert.equal(h.timers.size, 0);
  },
  'project switch immediately masks previous state and ignores late events': () => {
    const h = harness(); h.render('A'); h.tick(); const a = h.sockets[0];
    a.open(); a.message('A'); assert.equal(h.value().isConnected, true);
    const lateMessage = a.onmessage, lateClose = a.onclose;
    assert.deepEqual(h.render('B'), {isConnected: false, lastMessage: null});
    lateMessage({data: JSON.stringify({type: 'STATUS_UPDATE', project_id: 'A', data: {}})}); lateClose({code: 1006});
    h.tick(); const b = h.sockets[1]; b.open(); b.message('B'); a.closed();
    assert.equal(h.value().isConnected, true); assert.equal(h.value().lastMessage.project_id, 'B');
    assert.equal(a.closes, 1); h.dispose(); assert.equal(b.closes, 1); assert.equal(h.timers.size, 0);
  },
  'retired connecting socket cannot close replacement or emit messages': () => {
    const h = harness(); h.render('A'); h.tick(); const a = h.sockets[0];
    h.render('B'); h.tick(); const b = h.sockets[1]; b.open(); a.open(); a.message('A'); a.closed();
    assert.equal(a.prematureCloses, 0); assert.equal(a.closes, 1); assert.equal(b.closes, 0);
    assert.equal(h.value().isConnected, true); assert.equal(h.value().lastMessage, null); h.dispose();
  },
  'disabled project masks state and clears every timer': () => {
    const h = harness(); h.render('A'); h.tick(); h.sockets[0].open(); h.sockets[0].message('A');
    assert.deepEqual(h.render(undefined), {isConnected: false, lastMessage: null});
    assert.equal(h.timers.size, 0); h.tick(60000); assert.equal(h.sockets.length, 1);
  },
  'only owned valid messages pass; heartbeat uses open socket': () => {
    const h = harness('https:'); h.render('A'); h.tick(); const s = h.sockets[0];
    assert.equal(s.url, 'wss://localhost:3000/api/v1/ws/A'); h.tick(15000); assert.deepEqual(s.sent, []);
    s.open(); s.onmessage({data: 'pong'}); s.message('B'); assert.equal(h.value().lastMessage, null);
    s.onmessage({data: 'null'}); s.onmessage({data: '{}'}); assert.equal(h.value().lastMessage, null);
    s.onmessage({data: 'invalid'}); assert.equal(h.parseErrors.length, 1);
    s.message('A'); assert.equal(h.value().lastMessage.project_id, 'A');
    h.tick(15000); assert.deepEqual(s.sent, ['ping']); h.dispose(); assert.equal(h.timers.size, 0);
  },
  'native error closes drive one bounded reconnect timer': () => {
    const h = harness(); h.render('A'); h.tick();
    let s = h.sockets[0]; s.onerror?.({}); assert.equal(s.prematureCloses, 0); s.closed();
    for (const delay of [1000, 2000, 4000, 8000, 16000, 30000, 30000]) {
      const count = h.sockets.length; h.tick(delay - 1); assert.equal(h.sockets.length, count);
      h.tick(1); assert.equal(h.sockets.length, count + 1); s = h.sockets.at(-1); s.closed();
    }
    h.dispose(); h.tick(60000); assert.equal(h.timers.size, 0);
  },
  'successful reconnect resets backoff': () => {
    const h = harness(); h.render('A'); h.tick(); h.sockets[0].closed(); h.tick(1000);
    const s = h.sockets[1]; s.open(); s.closed(); h.tick(999); assert.equal(h.sockets.length, 2);
    h.tick(1); assert.equal(h.sockets.length, 3); h.dispose();
  },
  'terminal close codes route once without retry': () => {
    for (const [code, destination] of [[4401, '/login'], [4404, '/'], [4403, undefined]]) {
      const h = harness(); h.render('A'); h.tick(); h.sockets[0].open(); h.sockets[0].closed(code); h.tick(60000);
      assert.equal(h.value().isConnected, false); assert.deepEqual(h.redirects, destination ? [destination] : []);
      assert.equal(h.sockets.length, 1); h.dispose(); assert.equal(h.timers.size, 0);
    }
  },
};
let failed = 0;
for (const [name, test] of Object.entries(cases)) {
  try {test(); console.log('PASS', name);} catch (error) {failed++; console.error('FAIL', name, error.message);}
}
console.log(`WebSocket lifecycle: ${Object.keys(cases).length - failed}/${Object.keys(cases).length} passed`);
if (failed) process.exitCode = 1;
