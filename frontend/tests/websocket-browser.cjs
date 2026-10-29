/* Isolated real-browser hook/Next proxy regressions. No live project is used. */
const {chromium} = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs'), path = require('node:path'), http = require('node:http');
const {Server: WebSocketServer} = require('../node_modules/next/dist/compiled/ws');
const ts = require('../node_modules/typescript');
if (process.env.ONEFL_E2E !== '1') throw new Error('Requires isolated fixture');
const BASE = process.env.ONEFL_TEST_URL || 'http://127.0.0.1:3100';
const PORT = Number(process.env.ONEFL_WS_PROBE_PORT || 3101);
const PROBE = `http://127.0.0.1:${PORT}`;
const OUT = path.resolve(process.env.ONEFL_TEST_ARTIFACTS || 'tmp/websocket-lifecycle');
const BASELINE = process.env.ONEFL_WS_BASELINE_SOURCE;
const KEY = 'onefl-browser-fixture-access-2026';
const results = [], errors = [], baselineWarnings = [], consoleErrors = [], baselineCloses = [], connections = new Map(), upgrades = [];
const transportSockets = new Set();
const write = () => fs.writeFileSync(path.join(OUT, 'browser-results.json'), JSON.stringify({results, errors, baselineWarnings, baselineCloses, consoleErrors}, null, 2));
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
async function until(test, label) {
  for (let i = 0; i < 200; i++) {if (await test()) return; await sleep(50);}
  throw new Error('Timeout: ' + label);
}
async function scenario(name, work) {
  try {await work(); results.push({name, status: 'passed'}); console.log('PASS', name);}
  catch (e) {results.push({name, status: 'failed', error: e.message}); throw e;}
  finally {write();}
}
const server = http.createServer((request, response) => {
  if (request.url === '/react.js' || request.url === '/react-dom.js') {
    const file = request.url === '/react.js' ? 'react/umd/react.development.js' : 'react-dom/umd/react-dom.development.js';
    response.setHeader('Content-Type', 'text/javascript'); response.end(fs.readFileSync(path.join(__dirname, '../node_modules', file))); return;
  }
  if (request.url.startsWith('/hook.js')) {
    const file = request.url.includes('baseline') ? BASELINE : path.join(__dirname, '../src/lib/useWebSocket.ts');
    const source = fs.readFileSync(file, 'utf8');
    response.setHeader('Content-Type', 'text/javascript');
    response.end(`var exports = {}; function require() {return React;}
      ${ts.transpileModule(source, {compilerOptions: {module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020}}).outputText}`);
    return;
  }
  response.setHeader('Content-Type', 'text/html');
  response.end(`<!doctype html><html><body><div id="root"></div>
    <script src="/react.js"></script><script src="/react-dom.js"></script>
    <script src="/hook.js${request.url.includes('baseline') ? '?baseline' : ''}"></script>
    <script>
      window.__sockets = []; window.__states = []; window.__closes = [];
      const Original = window.WebSocket;
      window.WebSocket = class extends Original {
        constructor(...args) {super(...args); __sockets.push(this);}
        close(...args) {__closes.push({url: this.url, state: this.readyState}); super.close(...args);}
      };
      function Probe({id}) {
        const state = exports.useProjectWebSocket(id);
        React.useEffect(() => {__states.push({id, ...state});}, [id, state.isConnected, state.lastMessage]);
        return React.createElement('pre', {id: 'state'}, JSON.stringify(state));
      }
      const root = ReactDOM.createRoot(document.getElementById('root'));
      window.__render = (id, strict = true) => root.render(React.createElement(strict ? React.StrictMode : React.Fragment, null, React.createElement(Probe, {id})));
      window.__hide = () => root.render(null);
    </script></body></html>`);
});
const ws = new WebSocketServer({noServer: true});
server.on('connection', socket => {transportSockets.add(socket); socket.on('close', () => transportSockets.delete(socket));});
server.on('upgrade', (request, socket, head) => {
  const id = request.url.split('/').at(-1); upgrades.push(id);
  setTimeout(() => {
    if (socket.destroyed) return;
    ws.handleUpgrade(request, socket, head, connection => {
      if (!connections.has(id)) connections.set(id, new Set());
      connections.get(id).add(connection);
      connection.on('close', () => connections.get(id).delete(connection));
      connection.on('message', value => {if (value.toString() === 'ping') connection.send('pong');});
      connection.send(JSON.stringify({type: 'STATUS_UPDATE', project_id: id, data: {message: id}}));
    });
  }, 400);
});

(async () => {
  await new Promise((resolve, reject) => {server.once('error', reject); server.listen(PORT, '127.0.0.1', resolve);});
  const browser = await chromium.launch({headless: true, executablePath: process.env.ONEFL_BROWSER ||
    path.join(process.env.LOCALAPPDATA, 'ms-playwright/chromium-1248/chrome-win64/chrome.exe')});
  const context = await browser.newContext();
  await context.tracing.start({screenshots: true, snapshots: true});
  const probe = await context.newPage(); probe.setDefaultTimeout(10000);
  const baseline = await context.newPage();
  baseline.on('console', message => {if (message.type() === 'error') baselineWarnings.push(message.text());});
  const baselineLog = await context.newCDPSession(baseline);
  await baselineLog.send('Log.enable'); await baselineLog.send('Network.enable');
  baselineLog.on('Log.entryAdded', ({entry}) => {if (entry.level === 'error') baselineWarnings.push(entry.text);});
  baselineLog.on('Network.webSocketFrameError', event => baselineWarnings.push(event.errorMessage));
  const track = async page => {
    page.on('pageerror', error => errors.push(error.message));
    page.on('console', message => {if (message.type() === 'error') consoleErrors.push(message.text());});
    const log = await context.newCDPSession(page); await log.send('Log.enable'); await log.send('Network.enable');
    log.on('Log.entryAdded', ({entry}) => {if (entry.level === 'error') consoleErrors.push(entry.text);});
    log.on('Network.webSocketFrameError', event => consoleErrors.push(event.errorMessage));
  };
  await track(probe);
  try {
    if (BASELINE) await scenario('baseline reproduces native close-before-established error', async () => {
      await baseline.goto(PROBE + '/?baseline'); await baseline.evaluate(() => __render('baseline', false));
      await baseline.waitForFunction(() => __sockets.length === 1 && __sockets[0].readyState === 0);
      await until(() => upgrades.includes('baseline'), 'baseline pending upgrade');
      await baseline.evaluate(() => __hide());
      await baseline.waitForFunction(() => __closes.length > 0);
      baselineCloses.push(...await baseline.evaluate(() => __closes));
      assert.equal(baselineCloses[0].state, 0);
      await until(() => baselineWarnings.some(value => value.includes('closed before the connection is established')), 'native baseline error');
      await baseline.close();
    });
    await probe.goto(PROBE);
    await scenario('React StrictMode discarded setup creates only one connection', async () => {
      await probe.evaluate(() => __render('strict'));
      await probe.waitForFunction(() => JSON.parse(document.querySelector('#state').textContent).isConnected);
      assert.equal(await probe.evaluate(() => __sockets.length), 1);
      assert.equal(upgrades.filter(id => id === 'strict').length, 1);
      await probe.evaluate(() => __hide()); await until(() => !connections.get('strict')?.size, 'open socket retired');
    });
    await scenario('unmount during delayed handshake closes only after open', async () => {
      await probe.evaluate(() => __render('pending'));
      await probe.waitForFunction(() => __sockets.at(-1).readyState === 0);
      await until(() => upgrades.includes('pending'), 'pending upgrade'); await probe.evaluate(() => __hide());
      await probe.waitForFunction(() => __sockets.at(-1).readyState === 3);
      assert.equal(connections.get('pending').size, 0);
      assert.ok(await probe.evaluate(() => __closes.every(event => event.state === 1)));
    });
    await scenario('project switch retires old handshake and ignores foreign events', async () => {
      await probe.evaluate(() => __render('old'));
      await until(() => upgrades.includes('old'), 'old upgrade'); await probe.evaluate(() => __render('new'));
      await probe.waitForFunction(() => JSON.parse(document.querySelector('#state').textContent).lastMessage?.project_id === 'new');
      for (const socket of connections.get('new')) socket.send(JSON.stringify({type: 'STATUS_UPDATE', project_id: 'old', data: {}}));
      await sleep(100);
      assert.equal(await probe.locator('#state').textContent().then(JSON.parse).then(x => x.lastMessage.project_id), 'new');
      assert.ok(await probe.evaluate(() => __states.filter(x => x.id === 'new').every(x => !x.lastMessage || x.lastMessage.project_id === 'new')));
      await until(() => !connections.get('old')?.size, 'old connection retired');
    });
    await scenario('interrupted connection reconnects and receives a fresh snapshot', async () => {
      for (const socket of connections.get('new')) socket.close(1012);
      await until(() => upgrades.filter(id => id === 'new').length === 2, 'reconnect upgrade');
      await probe.waitForFunction(() => __sockets.at(-1).readyState === 1);
      await probe.evaluate(() => __hide()); await until(() => !connections.get('new')?.size, 'reconnect cleanup');
    });

    await context.addInitScript(() => {
      window.__oneflSockets = []; const Original = window.WebSocket;
      window.WebSocket = class extends Original {constructor(...args) {super(...args); __oneflSockets.push(this);}};
    });
    const studio = await context.newPage(), observer = await context.newPage(); await track(studio); await track(observer);
    const api = async (route, method = 'GET', data) => {
      const response = await context.request.fetch(BASE + '/api/v1' + route, {method, data});
      assert.ok(response.ok(), `${method} ${route}: ${response.status()}`); return response.json();
    };
    let id, cue;
    await scenario('Next proxy authenticates and delivers cue updates to two Studio tabs', async () => {
      await api('/auth/login', 'POST', {token: KEY});
      id = (await api('/projects', 'POST', {title: 'WebSocket regression', source_language: 'en', target_language: 'vi'})).id;
      cue = await api(`/projects/${id}/subtitles`, 'POST', {cue_index: 1, start_time: 0, end_time: 1, original_text: 'Hello', translated_text: 'First line'});
      for (const page of [studio, observer]) {
        await page.goto(BASE + '/projects/' + id); await page.getByText('First line', {exact: true}).first().waitFor();
        await page.waitForFunction(() => __oneflSockets.some(socket => socket.readyState === 1));
      }
      await api(`/projects/${id}/subtitles/${cue.id}`, 'PATCH', {translated_text: 'Live synchronized'});
      for (const page of [studio, observer]) await page.getByText('Live synchronized', {exact: true}).first().waitFor();
    });
    await scenario('Studio reconnect resynchronizes an edit missed while disconnected', async () => {
      const count = await studio.evaluate(() => {const count = __oneflSockets.length; __oneflSockets.forEach(socket => socket.close()); return count;});
      await api(`/projects/${id}/subtitles/${cue.id}`, 'PATCH', {translated_text: 'Missed edit restored'});
      await studio.waitForFunction(count => __oneflSockets.length > count && __oneflSockets.at(-1).readyState === 1, count);
      await studio.getByText('Missed edit restored', {exact: true}).first().waitFor();
      await studio.screenshot({path: path.join(OUT, 'studio-reconnected.png'), fullPage: true});
    });
    await scenario('leaving Studio closes its socket without a lifecycle warning', async () => {
      await studio.locator('a[href="/"]').first().click(); await studio.waitForURL(BASE + '/');
      await studio.waitForFunction(() => __oneflSockets.every(socket => socket.readyState === 3));
      await observer.close();
    });
    assert.ok(await probe.evaluate(() => __closes.every(event => event.state === 1)));
    assert.deepEqual(errors, []); assert.deepEqual(consoleErrors, []);
    console.log('WEBSOCKET BROWSER SCENARIOS', results.length);
  } catch (e) {console.error(e); process.exitCode = 1;}
  finally {
    write(); await context.tracing.stop({path: path.join(OUT, 'browser-trace.zip')}); await browser.close();
    for (const socket of ws.clients) socket.terminate();
    for (const socket of transportSockets) socket.destroy();
    await new Promise(resolve => server.close(resolve)); ws.close();
  }
})().catch(error => {console.error(error); process.exitCode = 1; server.close();});
