/* Real isolated UI → durable BURN → FFmpeg/download acceptance; no external providers. */
const {chromium} = require('playwright');
const fs = require('node:fs'), path = require('node:path'), assert = require('node:assert/strict');
if (process.env.ONEFL_E2E !== '1') throw new Error('Requires isolated fixture');
const BASE = process.env.ONEFL_TEST_URL || 'http://127.0.0.1:3100';
const FIXTURE = process.env.ONEFL_FIXTURE_URL || 'http://127.0.0.1:8100';
const OUT = path.resolve(process.env.ONEFL_TEST_ARTIFACTS || 'tmp/presentation');
const CAPTION = 'Ta đã hỏi ở Túy Tiên Lầu rồi, mười hai bàn tiệc.';
const results = [], errors = []; let projectId;
fs.mkdirSync(OUT, {recursive: true});
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
  const page = await context.newPage(); page.setDefaultTimeout(20000);
  page.on('pageerror', error => errors.push(error.message));
  const dialog = () => page.getByRole('dialog', {name: 'Burn Video'});
  const whiteChoice = () => dialog().getByRole('button', {name: /Dải trắng trên và dưới/});
  const comicChoice = () => dialog().getByRole('button', {name: /Chữ theo mẫu/});
  async function api(url, method = 'GET', data) {
    const response = await context.request.fetch(BASE + '/api/v1' + url, {method, data});
    assert.ok(response.ok(), `${url}: ${response.status()} ${await response.text()}`);
    return response.json();
  }
  async function idle(id = projectId) {
    for (let i = 0; i < 300; i++) {
      const project = await api('/projects/' + id);
      if (!project.active_job_id) return project;
      await page.waitForTimeout(100);
    }
    throw new Error('Fixture job timed out');
  }
  async function newProject(settings) {
    const project = await api('/projects/from-url', 'POST', {
      url: 'https://www.bilibili.com/video/BV1MHh66uEFH/', auto_start_pipeline: false,
    });
    await idle(project.id);
    if (settings) await api('/projects/' + project.id, 'PATCH', {settings_override: settings});
    const seeded = await context.request.post(FIXTURE + '/__e2e/control', {
      headers: {'x-e2e-key': 'onefl-browser-fixture-access-2026'}, data: {seed_project_id: project.id, seed_count: 1},
    }); assert.ok(seeded.ok());
    const cues = await api('/projects/' + project.id + '/subtitles');
    await api('/projects/' + project.id + '/subtitles/' + cues.items[0].id, 'PATCH', {translated_text: CAPTION});
    return project.id;
  }
  async function setRange(label, value) {
    const range = dialog().getByLabel(label);
    await range.focus(); await range.press('Home');
    for (let i = 0; i < value; i++) await range.press('ArrowRight');
    assert.equal(Number(await range.inputValue()), value);
  }
  async function metadata(video) {
    await video.evaluate(video => video.readyState >= 1 ? Promise.resolve() : new Promise((resolve, reject) => {
      const timer = setTimeout(() => reject(new Error('Video metadata timed out')), 10000);
      video.addEventListener('loadedmetadata', () => {clearTimeout(timer); resolve();}, {once: true});
    }));
  }
  try {
    await api('/auth/login', 'POST', {token: 'onefl-browser-fixture-access-2026'});
    projectId = await newProject();
    await page.goto(BASE + '/projects/' + projectId);
    await page.getByRole('button', {name: 'Burn Video', exact: true}).click();
    await scenario('unconfigured project defaults to white covers and reference text on true video aspect', async () => {
      assert.equal(await whiteChoice().getAttribute('aria-pressed'), 'true');
      assert.equal(await comicChoice().getAttribute('aria-pressed'), 'true');
      const video = dialog().getByLabel('Video xem trước kiểu xuất'); await metadata(video);
      assert.equal(await video.evaluate(video => video.videoWidth), 320);
      await page.waitForFunction(() => {
        const box = document.querySelector('[data-testid="burn-style-preview"]').getBoundingClientRect();
        return Math.abs(box.width / box.height - 4 / 3) < .01;
      });
      const top = dialog().getByTestId('preview-top-band');
      assert.equal(await top.evaluate(el => getComputedStyle(el).backgroundColor), 'rgb(255, 255, 255)');
      assert.equal(await top.evaluate(el => el.style.height), '11%');
      assert.equal(await dialog().getByTestId('preview-bottom-band').evaluate(el => el.style.height), '15%');
      const text = dialog().getByTestId('preview-styled-subtitle');
      assert.equal(await text.textContent(), CAPTION.toLocaleUpperCase('vi-VN'));
      assert.equal(await text.evaluate(el => getComputedStyle(el).fontStyle), 'italic');
      assert.equal(await text.evaluate(el => getComputedStyle(el).color), 'rgb(255, 255, 255)');
      assert.ok(await text.evaluate(el => parseFloat(getComputedStyle(el).webkitTextStrokeWidth) > 0));
      await dialog().getByRole('button', {name: 'Phát video xem trước', exact: true}).click();
      await dialog().getByRole('button', {name: 'Tạm dừng xem trước', exact: true}).waitFor();
      await page.waitForFunction(() => document.querySelector('video[aria-label="Video xem trước kiểu xuất"]').currentTime > .1);
      await dialog().getByRole('button', {name: 'Tạm dừng xem trước', exact: true}).click();
      const seek = dialog().getByLabel('Thời gian video xem trước (giây)');
      const frame = await dialog().getByTestId('burn-style-preview').boundingBox();
      const play = await dialog().getByRole('button', {name: 'Phát video xem trước', exact: true}).boundingBox();
      assert.ok(play.y >= frame.y + frame.height, 'controls must stay outside the covered frame');
      await seek.focus(); await seek.press('Home');
      assert.equal(await video.evaluate(video => video.currentTime), 0);
      await page.screenshot({path: path.join(OUT, 'style-desktop.png'), fullPage: true});
    });
    await scenario('sample action and zero/nonzero cover heights update preview without losing caption', async () => {
      await dialog().getByRole('button', {name: 'Áp dụng kiểu mẫu'}).click();
      await setRange('Chiều cao dải trên (%)', 0); await setRange('Chiều cao dải dưới (%)', 0);
      assert.equal(await dialog().getByTestId('preview-top-band').count(), 0);
      assert.equal(await dialog().getByTestId('preview-bottom-band').count(), 0);
      assert.equal(await dialog().getByTestId('preview-styled-subtitle').isVisible(), true);
      await setRange('Chiều cao dải trên (%)', 8); await setRange('Chiều cao dải dưới (%)', 20);
      assert.equal(await dialog().getByTestId('preview-top-band').evaluate(el => el.style.height), '8%');
      assert.equal(await dialog().getByTestId('preview-bottom-band').evaluate(el => el.style.height), '20%');
    });
    for (const status of [409, 422]) await scenario(`HTTP ${status} preserves style draft and exposes error`, async () => {
      await page.route('**/pipeline/burn', route => route.fulfill({status, contentType: 'application/json',
        body: JSON.stringify({detail: `Fixture ${status}: render unavailable`})}));
      await dialog().getByRole('button', {name: /Bắt Đầu Burn Video/}).click();
      await dialog().getByRole('alert').filter({hasText: `Fixture ${status}`}).waitFor();
      assert.equal(await whiteChoice().getAttribute('aria-pressed'), 'true');
      assert.equal(await comicChoice().getAttribute('aria-pressed'), 'true');
      assert.equal(await dialog().getByLabel('Chiều cao dải dưới (%)').inputValue(), '20');
      await page.unroute('**/pipeline/burn');
    });
    await scenario('real BURN persists UI choices and provides styled ASS/MP4 without changing source case', async () => {
      const [response] = await Promise.all([
        page.waitForResponse(r => r.url().endsWith('/pipeline/burn') && r.request().method() === 'POST'),
        dialog().getByRole('button', {name: /Bắt Đầu Burn Video/}).click(),
      ]);
      assert.equal(response.status(), 200);
      const payload = response.request().postDataJSON();
      assert.equal(payload.subtitle_preset, 'comic'); assert.equal(payload.clean_chinese_mode, 'white_bars');
      assert.equal(payload.top_mask_pct, 8); assert.equal(payload.bottom_mask_pct, 20);
      const project = await idle(); assert.equal(project.status, 'COMPLETED', project.error_message);
      assert.equal(project.settings_override.subtitle_preset, 'comic');
      assert.equal(project.settings_override.clean_chinese_mode, 'white_bars');
      assert.equal(project.settings_override.top_mask_pct, 8); assert.equal(project.settings_override.bottom_mask_pct, 20);
      const assLink = dialog().getByRole('link', {name: 'Tải Phụ Đề .ASS'}); await assLink.waitFor();
      assert.match(await assLink.getAttribute('href'), /preset=comic/);
      const ass = await context.request.get(BASE + await assLink.getAttribute('href')); assert.ok(ass.ok());
      const assText = await ass.text(); assert.ok(assText.includes(CAPTION.toLocaleUpperCase('vi-VN')));
      assert.match(assText, /Style: Default,Arial,36,[^\r\n]+,1,1,0,0,80,100/);
      const download = await context.request.get(BASE + project.burned_video_url); assert.ok(download.ok());
      fs.writeFileSync(path.join(OUT, 'browser-output.mp4'), await download.body());
      fs.writeFileSync(path.join(OUT, 'browser-output.ass'), assText);
      const cues = await api('/projects/' + projectId + '/subtitles'); assert.equal(cues.items[0].translated_text, CAPTION);
      fs.writeFileSync(path.join(OUT, 'browser-output.json'), JSON.stringify({project, payload}, null, 2));
      await dialog().getByRole('button', {name: 'Đóng', exact: true}).click();
      assert.match(await page.locator('a').filter({hasText: 'Phụ đề theo kiểu đã chọn (.ass)'}).getAttribute('href'), /preset=comic/);
    });
    await scenario('saved style reopens unchanged and preview fits 390px mobile viewport', async () => {
      await page.getByRole('button', {name: 'Burn Video', exact: true}).click();
      await dialog().getByRole('button', {name: 'Render lại với cấu hình khác'}).click();
      assert.equal(await whiteChoice().getAttribute('aria-pressed'), 'true');
      assert.equal(await comicChoice().getAttribute('aria-pressed'), 'true');
      if (!await dialog().getByLabel('Chiều cao dải trên (%)').count())
        await dialog().getByRole('button', {name: /Tùy chỉnh độ cao dải che/}).click();
      assert.equal(await dialog().getByLabel('Chiều cao dải trên (%)').inputValue(), '8');
      assert.equal(await dialog().getByLabel('Chiều cao dải dưới (%)').inputValue(), '20');
      await page.setViewportSize({width: 390, height: 844});
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
      const preview = dialog().getByTestId('burn-style-preview'); await preview.scrollIntoViewIfNeeded();
      const bounds = await preview.boundingBox(); assert.ok(bounds.width <= 358);
      const textBounds = await dialog().getByTestId('preview-styled-subtitle').boundingBox();
      assert.ok(textBounds.x >= bounds.x && textBounds.x + textBounds.width <= bounds.x + bounds.width + 1);
      await page.screenshot({path: path.join(OUT, 'style-mobile.png'), fullPage: true});
      await dialog().getByRole('button', {name: 'Đóng', exact: true}).click();
    });
    await scenario('explicit legacy style is preserved and zero-height covers keep Studio subtitles visible', async () => {
      const oldId = await newProject({subtitle_preset: 'yellow_highlight', clean_chinese_mode: 'cinema_bars',
        mask_original_sub: true, top_mask_pct: 0, bottom_mask_pct: 0});
      await page.setViewportSize({width: 1280, height: 1000});
      await page.goto(BASE + '/projects/' + oldId);
      await page.getByTestId('studio-styled-subtitle').waitFor();
      assert.equal(await page.getByTestId('studio-styled-subtitle').textContent(), CAPTION);
      await page.getByRole('button', {name: 'Burn Video', exact: true}).click();
      assert.equal(await whiteChoice().getAttribute('aria-pressed'), 'false');
      assert.equal(await comicChoice().getAttribute('aria-pressed'), 'false');
      assert.equal(await dialog().getByTestId('preview-top-band').count(), 0);
      assert.equal(await dialog().getByTestId('preview-bottom-band').count(), 0);
      assert.equal(await dialog().getByTestId('preview-styled-subtitle').textContent(), CAPTION);
      assert.equal(await dialog().getByTestId('preview-styled-subtitle').evaluate(el => getComputedStyle(el).color), 'rgb(255, 255, 0)');
    });
    assert.deepEqual(errors, []);
  } finally {
    await context.tracing.stop({path: path.join(OUT, 'presentation-trace.zip')}); await browser.close();
  }
})().catch(error => {console.error(error); process.exitCode = 1;});
