/* Real local UI/API/job/FFmpeg acceptance. URL download only uses the isolated fixture. */
const {chromium} = require('playwright');
const fs = require('node:fs'), path = require('node:path'), assert = require('node:assert/strict');
if (process.env.ONEFL_E2E !== '1') throw new Error('Requires isolated fixture');
const BASE = process.env.ONEFL_TEST_URL || 'http://127.0.0.1:3100';
const FIXTURE = process.env.ONEFL_FIXTURE_URL || 'http://127.0.0.1:8100';
const OUT = path.resolve(process.env.ONEFL_TEST_ARTIFACTS || 'tmp/video-cleanup');
const results = [], errors = []; let projectId;
async function scenario(name, work) {
  try {await work(); results.push({name, status: 'passed'}); console.log('PASS', name);}
  catch (error) {results.push({name, status: 'failed', error: error.message}); throw error;}
  finally {fs.writeFileSync(path.join(OUT, 'browser-results.json'), JSON.stringify({projectId, results, errors}, null, 2));}
}
(async () => {
  const browser = await chromium.launch({headless: true, executablePath: process.env.ONEFL_BROWSER ||
    path.join(process.env.LOCALAPPDATA, 'ms-playwright/chromium-1248/chrome-win64/chrome.exe')});
  const context = await browser.newContext({viewport: {width: 1280, height: 1000}});
  await context.tracing.start({screenshots: true, snapshots: true});
  const page = await context.newPage(); page.setDefaultTimeout(20000); page.on('pageerror', e => errors.push(e.message));
  const dialog = () => page.getByRole('dialog', {name: 'Burn Video'});
  async function api(url, method = 'GET', data) {
    const response = await context.request.fetch(BASE + '/api/v1' + url, {method, data});
    assert.ok(response.ok(), `${url}: ${response.status()} ${await response.text()}`); return response.json();
  }
  async function idle() {
    for (let i = 0; i < 200; i++) {
      const project = await api('/projects/' + projectId); if (!project.active_job_id) return project;
      await page.waitForTimeout(100);
    }
    throw new Error('Fixture job timed out');
  }
  try {
    await api('/auth/login', 'POST', {token: 'onefl-browser-fixture-access-2026'});
    const created = await api('/projects/from-url', 'POST', {
      url: 'https://www.bilibili.com/video/BV1MHh66uEFH/', auto_start_pipeline: false,
    });
    projectId = created.id; await idle();
    const seeded = await context.request.post(FIXTURE + '/__e2e/control', {
      headers: {'x-e2e-key': 'onefl-browser-fixture-access-2026'}, data: {seed_project_id: projectId, seed_count: 1},
    }); assert.ok(seeded.ok());
    await page.goto(BASE + '/projects/' + projectId);
    await page.getByRole('button', {name: 'Burn Video', exact: true}).click();
    await dialog().getByRole('button', {name: /Xóa chữ\/logo — phục hồi nền/}).click();
    await scenario('source selection, pointer geometry and accessible numeric/track controls', async () => {
      const video = dialog().getByLabel('Video chọn vùng xóa');
      await video.evaluate(v => v.readyState >= 1 ? Promise.resolve() : new Promise(r => v.addEventListener('loadedmetadata', r, {once: true})));
      assert.equal(await video.evaluate(v => v.videoWidth), 320);
      await dialog().getByRole('button', {name: 'Khoanh vùng trên video'}).click();
      const bounds = await dialog().getByTestId('cleanup-canvas').boundingBox(); assert.ok(bounds);
      await page.mouse.move(bounds.x + bounds.width * .125, bounds.y + bounds.height / 6);
      await page.mouse.down();
      await page.mouse.move(bounds.x + bounds.width * .3125, bounds.y + bounds.height * (40 + 24) / 240, {steps: 5});
      await page.mouse.up();
      assert.ok(Math.abs(Number(await dialog().getByLabel('Vùng 1 x', {exact: true}).inputValue()) - 12.5) < .1);
      await dialog().getByLabel('Bám theo logo di chuyển').check(); await dialog().getByLabel('Bám theo logo di chuyển').uncheck();
      await dialog().getByLabel('Tự dò và xóa chữ Trung').uncheck();
      await page.screenshot({path: path.join(OUT, 'cleanup-selection.png'), fullPage: true});
    });
    for (const status of [422, 409]) await scenario(`HTTP ${status} preserves cleanup draft and reports error`, async () => {
      await page.route('**/pipeline/burn', route => route.fulfill({status, contentType: 'application/json', body: JSON.stringify({detail: `Fixture ${status}: cleanup unavailable`})}));
      await dialog().getByRole('button', {name: /Bắt Đầu Burn Video/}).click();
      await dialog().getByRole('alert').filter({hasText: `Fixture ${status}`}).waitFor();
      assert.equal(await dialog().getByLabel('Tự dò và xóa chữ Trung').isChecked(), false);
      assert.ok(Number(await dialog().getByLabel('Vùng 1 width', {exact: true}).inputValue()) > 18);
      await page.unroute('**/pipeline/burn');
    });
    await scenario('real cleanup BURN persists nested options, report and playable downloadable output', async () => {
      const [response] = await Promise.all([
        page.waitForResponse(r => r.url().endsWith('/pipeline/burn') && r.request().method() === 'POST'),
        dialog().getByRole('button', {name: /Bắt Đầu Burn Video/}).click(),
      ]);
      assert.equal(response.status(), 200);
      const payload = response.request().postDataJSON(); assert.equal(payload.cleanup_options.auto_detect_chinese, false);
      assert.equal(payload.clean_chinese_mode, 'inpaint'); assert.equal(payload.cleanup_options.regions.length, 1);
      const project = await idle(); assert.equal(project.status, 'COMPLETED', project.error_message);
      assert.equal(project.settings_override.cleanup_options.regions.length, 1);
      const report = await api('/projects/' + projectId + '/pipeline/cleanup-report');
      assert.equal(report.processed_frames, 45); assert.equal(report.masked_frames, 45); assert.equal(report.chunks, 1);
      await dialog().getByText('Kết quả xóa chữ/logo', {exact: true}).waitFor();
      const download = await context.request.get(BASE + project.burned_video_url); assert.ok(download.ok());
      assert.ok((await download.body()).length > 1000);
      fs.writeFileSync(path.join(OUT, 'browser-output.json'), JSON.stringify({project, report, payload}, null, 2));
      await page.screenshot({path: path.join(OUT, 'cleanup-completed.png'), fullPage: true});
    });
    await scenario('saved options reopen and editor fits a 390px viewport', async () => {
      await dialog().getByRole('button', {name: 'Đóng', exact: true}).click();
      await page.getByRole('button', {name: 'Burn Video', exact: true}).click();
      await dialog().getByRole('button', {name: 'Render lại với cấu hình khác'}).click();
      assert.equal(await dialog().getByLabel('Tự dò và xóa chữ Trung').isChecked(), false);
      assert.ok(Number(await dialog().getByLabel('Vùng 1 width', {exact: true}).inputValue()) > 18);
      await page.setViewportSize({width: 390, height: 844});
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
      const box = await dialog().getByTestId('cleanup-editor').boundingBox(); assert.ok(box.width <= 358);
      await dialog().getByTestId('cleanup-editor').scrollIntoViewIfNeeded();
      await page.screenshot({path: path.join(OUT, 'cleanup-mobile.png'), fullPage: true});
    });
    assert.deepEqual(errors, []);
  } finally {
    await context.tracing.stop({path: path.join(OUT, 'cleanup-trace.zip')});
    await browser.close();
  }
})().catch(error => {console.error(error); process.exitCode = 1;});
