/* Isolated modal acceptance; API error/race replies are deliberately controlled. */
const {chromium} = require('playwright');
const fs = require('node:fs'), path = require('node:path'), assert = require('node:assert/strict');
if (process.env.ONEFL_E2E !== '1') throw new Error('Requires isolated fixture');
const BASE = process.env.ONEFL_TEST_URL || 'http://127.0.0.1:3100';
const OUT = path.resolve(process.env.ONEFL_TEST_ARTIFACTS || 'tmp/bilibili-diagnostics');
const A = 'https://www.bilibili.com/video/BV1MHh66uEFH/', B = 'https://www.bilibili.com/video/BV1RvaM6AEhi/';
const results = [], errors = [];
const write = () => fs.writeFileSync(path.join(OUT, 'browser-results.json'), JSON.stringify({results, errors}, null, 2));
async function scenario(name, work) {
  try {await work(); results.push({name, status: 'passed'}); console.log('PASS', name);}
  catch (error) {results.push({name, status: 'failed', error: error.message}); throw error;}
  finally {write();}
}
(async () => {
  const browser = await chromium.launch({headless: true, executablePath: process.env.ONEFL_BROWSER ||
    path.join(process.env.LOCALAPPDATA, 'ms-playwright/chromium-1248/chrome-win64/chrome.exe')});
  const context = await browser.newContext({viewport: {width: 1280, height: 900}});
  await context.tracing.start({screenshots: true, snapshots: true});
  const page = await context.newPage(); page.setDefaultTimeout(15000); page.on('pageerror', error => errors.push(error.message));
  const login = await context.request.post(BASE + '/api/v1/auth/login', {data: {token: 'onefl-browser-fixture-access-2026'}});
  assert.ok(login.ok());
  const dialog = () => page.getByRole('dialog');
  const input = () => dialog().locator('input[type=url]');
  async function open() {
    await page.unroute('**/api/v1/projects/url-info'); await page.goto(BASE + '/');
    await page.getByRole('button', {name: 'Tải File Từ Máy', exact: true}).click(); await dialog().waitFor();
  }
  const reply = (route, data, status = 200) => route.fulfill({status, contentType: 'application/json', body: JSON.stringify(data)});
  const inspect = async url => {await input().fill(url); await input().evaluate(element => element.blur());};
  const waitRoutes = async (routes, count) => {for (let i = 0; i < 100; i++) {if (routes.length === count) return; await page.waitForTimeout(25);} throw new Error('No inspection request');};
  try {
    await scenario('HTTP 200 inspection failure is visible and actionable', async () => {
      await open(); await page.route('**/api/v1/projects/url-info', route => reply(route, {success: false, error_code: 'BILIBILI_ACCESS_RESTRICTED', error: 'Bilibili từ chối truy cập; tải file video lên từ máy tính.'}));
      await inspect(A); await dialog().getByRole('alert').filter({hasText: 'tải file video'}).waitFor();
      await page.screenshot({path: path.join(OUT, 'url-error.png'), fullPage: true});
    });
    await scenario('proxy failure is visible without closing the modal', async () => {
      await open(); await page.route('**/api/v1/projects/url-info', route => reply(route, {detail: 'Fixture proxy unavailable'}, 503));
      await inspect(A); await dialog().getByRole('alert').filter({hasText: 'Fixture proxy unavailable'}).waitFor();
    });
    await scenario('editing URL discards stale successful metadata', async () => {
      await open(); const routes = []; await page.route('**/api/v1/projects/url-info', route => {routes.push(route);});
      await inspect(A); await waitRoutes(routes, 1); await input().fill(B);
      await reply(routes[0], {success: true, title: 'Old preview', duration: 3});
      await page.waitForTimeout(150); assert.equal(await dialog().getByText('Old preview', {exact: true}).count(), 0);
      assert.equal(await dialog().locator('input[placeholder^="Tự động"]').inputValue(), '');
    });
    await scenario('older failure cannot replace newer request loading or result', async () => {
      await open(); const routes = []; await page.route('**/api/v1/projects/url-info', route => {routes.push(route);});
      await inspect(A); await waitRoutes(routes, 1); await inspect(B); await waitRoutes(routes, 2);
      await reply(routes[0], {success: false, error: 'Stale failure'}); await page.waitForTimeout(100);
      assert.equal(await dialog().getByRole('button', {name: 'Đang đọc...', exact: true}).count(), 1);
      assert.equal(await dialog().getByRole('alert').count(), 0);
      await reply(routes[1], {success: true, title: 'Current video preview', duration: 3});
      await dialog().getByText('Current video preview', {exact: true}).waitFor();
    });
    await scenario('switching to file upload discards pending link failure', async () => {
      await open(); const routes = []; await page.route('**/api/v1/projects/url-info', route => {routes.push(route);});
      await inspect(A); await waitRoutes(routes, 1); await dialog().getByRole('button', {name: /Tải File Từ Máy/}).click();
      await reply(routes[0], {success: false, error: 'Stale failure'}); await page.waitForTimeout(100);
      assert.equal(await dialog().getByRole('alert').count(), 0); await dialog().locator('input[type=file]').waitFor({state: 'attached'});
    });
    await scenario('closing modal invalidates pending metadata failure', async () => {
      await open(); const routes = []; await page.route('**/api/v1/projects/url-info', route => {routes.push(route);});
      await inspect(A); await waitRoutes(routes, 1); await dialog().getByRole('button', {name: 'Đóng', exact: true}).click();
      await dialog().waitFor({state: 'hidden'}); await reply(routes[0], {success: false, error: 'Closed request failure'});
      await page.getByRole('button', {name: 'Tải File Từ Máy', exact: true}).click(); await dialog().waitFor();
      assert.equal(await dialog().getByText('Closed request failure', {exact: true}).count(), 0);
    });
    assert.deepEqual(errors, []); console.log('BILIBILI UI SCENARIOS', results.length);
  } catch (error) {console.error(error); await page.screenshot({path: path.join(OUT, 'browser-failure.png')}); process.exitCode = 1;}
  finally {write(); await context.tracing.stop({path: path.join(OUT, 'browser-trace.zip')}); await browser.close();}
})().catch(error => {console.error(error); process.exitCode = 1;});
