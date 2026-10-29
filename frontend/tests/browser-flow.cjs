/* Isolated browser/API/WebSocket/media checks. External AI/URL providers use tests/e2e_backend.py fixtures.
 * Set ONEFL_E2E=1. Install Playwright separately or supply NODE_PATH; see the feature verification report.
 */

const {chromium}=require('playwright'); const assert=require('node:assert/strict'); const fs=require('fs');
const BASE=process.env.ONEFL_TEST_URL||'http://127.0.0.1:3100';
const FIXTURE=process.env.ONEFL_FIXTURE_URL||'http://127.0.0.1:8100';
const path=require('node:path');
const OUT=process.env.ONEFL_TEST_ARTIFACTS||path.resolve(__dirname,'../../tmp/feature-audit');
if(process.env.ONEFL_E2E!=='1') throw new Error('Start the isolated fixture server and set ONEFL_E2E=1 before running browser tests'); const KEY='onefl-browser-fixture-access-2026';
const results=[], errors=[], networkErrors=[];let projectId,observer;
const write=()=>fs.writeFileSync(OUT+'/browser-results.json',JSON.stringify({results,projectId,errors,networkErrors},null,2));
async function scenario(name,work){try{await work();results.push({name,status:'passed'});console.log('PASS',name)}catch(e){results.push({name,status:'failed',error:e.message});throw e}finally{write()}}
(async()=>{
const browser=await chromium.launch({headless:true,executablePath:process.env.ONEFL_BROWSER||(process.env.LOCALAPPDATA&&fs.existsSync(process.env.LOCALAPPDATA+'/ms-playwright/chromium-1248/chrome-win64/chrome.exe')?process.env.LOCALAPPDATA+'/ms-playwright/chromium-1248/chrome-win64/chrome.exe':undefined)});
const context=await browser.newContext({viewport:{width:1440,height:1000}});await context.addInitScript(()=>{window.__oneflSockets=[];const Original=window.WebSocket;window.WebSocket=class extends Original{constructor(...args){super(...args);window.__oneflSockets.push(this)}}});await context.tracing.start({screenshots:true,snapshots:true});
const p=await context.newPage();p.setDefaultTimeout(15000);
function track(page){page.on('pageerror',e=>errors.push({message:e.message,stack:e.stack}));page.on('requestfailed',r=>{if(!r.failure()?.errorText.includes('ABORTED'))networkErrors.push({url:r.url(),error:r.failure()?.errorText})})};track(p);
const api=async(path,method='GET',data)=>{const r=await p.request.fetch(BASE+'/api/v1'+path,{method,data});assert.ok(r.ok(),method+' '+path+': '+r.status()+' '+await r.text());return r.json()};
const project=()=>api('/projects/'+projectId);const cues=()=>api('/projects/'+projectId+'/subtitles');
async function until(test,label){for(let i=0;i<400;i++){if(await test())return;await p.waitForTimeout(150)}throw new Error('Timed out: '+label)}
async function idle(){await until(async()=>{const x=await project();return !x.active_job_id&&!['QUEUED','PROCESSING','INGESTING','DUBBING','BURNING'].includes(x.status)},'idle project');const x=await project();assert.notEqual(x.status,'FAILED',x.error_message)}
async function clickAccepted(button,suffix){const [response]=await Promise.all([p.waitForResponse(r=>r.url().endsWith(suffix)&&r.request().method()==='POST'),button.click()]);assert.ok(response.ok(),'Job request: '+response.status())}
const dialog=()=>p.getByRole('dialog');
async function close(){await dialog().getByRole('button',{name:'Đóng',exact:true}).first().click();await dialog().waitFor({state:'hidden'})}
try{
 await scenario('authentication and session redirect',async()=>{
  await p.goto(BASE);await p.waitForURL('**/login');await p.locator('input[type=password]').fill('wrong-fixture-token');await p.locator('form button').click();await p.locator('form').getByRole('alert').waitFor();
  await p.locator('input[type=password]').fill(KEY);await p.locator('form button').click();await p.waitForURL(BASE+'/');await p.getByRole('button',{name:'Tải File Từ Máy',exact:true}).waitFor();
 });
 await scenario('create project and upload through actual UI',async()=>{
  await p.getByRole('button',{name:'Tải File Từ Máy',exact:true}).click();await dialog().getByRole('button',{name:/Tải File Từ Máy/}).click();
  await dialog().locator('input[type=file]').setInputFiles(OUT+'/runtime/source.mp4');await dialog().locator('input[placeholder^="e.g."]').fill('Full-stack browser verification');await dialog().locator('#autoStart').uncheck();
  await dialog().locator('select').first().selectOption('en');await dialog().getByRole('button',{name:'Bắt Đầu Dịch Thuật',exact:true}).click();await dialog().waitFor({state:'hidden'});
  const list=await api('/projects');const found=list.items.find(x=>x.title==='Full-stack browser verification');assert.ok(found);projectId=found.id;const data=await project();assert.equal(data.status,'CREATED');assert.equal(data.video_duration_seconds,3);
  await p.goto(BASE+'/projects/'+projectId);await p.getByTitle('Cấu hình xưng hô nhân vật').waitFor();await until(()=>p.locator('video').evaluate(v=>Number.isFinite(v.duration)&&v.duration>0),'video metadata');
 });
 await scenario('pipeline request, live progress and review state',async()=>{
  await clickAccepted(p.getByRole('button',{name:/Nhận diện & Dịch AI/}),'/pipeline/trigger');await idle();assert.equal((await project()).status,'WAITING_REVIEW');assert.equal((await cues()).items.length,2);await p.getByTitle('Bấm để chỉnh sửa bản dịch câu này').first().waitFor();
  await until(()=>p.getByRole('button',{name:/Dịch Lại Toàn Bộ/}).isEnabled(),'pipeline unlock');
 });
 await scenario('video playback advances, pauses and reaches ended state',async()=>{
  await p.getByRole('button',{name:'Phát video',exact:true}).click();await until(()=>p.locator('video').evaluate(v=>v.currentTime>0.25&&!v.paused),'video playing');
  await p.locator('video').screenshot({path:OUT+'/video-playing.png'});
  await p.getByRole('button',{name:'Tạm dừng',exact:true}).click();assert.equal(await p.locator('video').evaluate(v=>v.paused),true);
  await p.getByRole('button',{name:'Phát video',exact:true}).click();await until(()=>p.locator('video').evaluate(v=>v.ended),'video ended');assert.equal(await p.getByRole('button',{name:'Phát video',exact:true}).count(),1);
 });
 observer=await context.newPage();observer.setDefaultTimeout(15000);track(observer);await observer.goto(BASE+'/projects/'+projectId);await observer.getByTitle('Bấm để chỉnh sửa bản dịch câu này').first().waitFor();
 await scenario('subtitle edit persists and synchronizes second tab',async()=>{
  await p.getByTitle('Bấm để chỉnh sửa bản dịch câu này').first().click();await p.locator('textarea').fill('Ban sua thu cong');await p.getByRole('button',{name:'Lưu',exact:true}).click();
  await until(async()=>(await cues()).items[0].translated_text==='Ban sua thu cong','saved cue');await observer.getByText('Ban sua thu cong',{exact:true}).first().waitFor();assert.equal((await cues()).items[0].is_edited,true);
 });
 await scenario('failed edit shows error and preserves draft',async()=>{
  await p.route('**/api/v1/projects/*/subtitles/*',async r=>r.request().method()==='PATCH'?r.fulfill({status:409,contentType:'application/json',body:JSON.stringify({detail:'Fixture edit conflict'})}):r.continue());
  await p.getByTitle('Bấm để chỉnh sửa bản dịch câu này').first().click();await p.locator('textarea').fill('Draft after conflict');await p.getByLabel('Bắt đầu (giây)',{exact:true}).fill('0.2');await p.getByRole('button',{name:'Lưu',exact:true}).click();await p.getByRole('alert').filter({hasText:'Fixture edit conflict'}).first().waitFor();assert.equal(await p.locator('textarea').inputValue(),'Draft after conflict');assert.equal(await p.getByLabel('Bắt đầu (giây)',{exact:true}).inputValue(),'0.2');await p.getByRole('button',{name:'Hủy',exact:true}).click();await p.unroute('**/api/v1/projects/*/subtitles/*');
 });
 await scenario('timing validation, atomic save and two-tab persistence',async()=>{
  const first=(await cues()).items[0];await p.getByRole('button',{name:'Sửa thời gian',exact:true}).first().click();
  await p.getByLabel('Kết thúc (giây)',{exact:true}).fill('4');await p.getByRole('button',{name:'Lưu',exact:true}).click();
  await p.getByRole('alert').filter({hasText:'vượt độ dài video'}).waitFor();assert.equal((await cues()).items[0].end_time,first.end_time);
  await p.getByLabel('Bắt đầu (giây)',{exact:true}).fill('0.2');await p.getByLabel('Kết thúc (giây)',{exact:true}).fill('1.2');
  await p.getByRole('button',{name:'Lưu',exact:true}).click();await p.getByLabel('Kết thúc (giây)',{exact:true}).waitFor({state:'hidden'});
  assert.equal((await cues()).items[0].start_time,.2);assert.equal((await cues()).items[0].end_time,1.2);
  await observer.getByRole('button',{name:'Sửa thời gian',exact:true}).first().click();assert.equal(await observer.getByLabel('Kết thúc (giây)',{exact:true}).inputValue(),'1.2');await observer.getByRole('button',{name:'Hủy',exact:true}).click();
 });
 await scenario('remote timing changes preserve draft and prevent overwrite',async()=>{
  await p.getByRole('button',{name:'Sửa thời gian',exact:true}).first().click();await p.getByLabel('Bắt đầu (giây)',{exact:true}).fill('0.25');
  const first=(await cues()).items[0];await api('/projects/'+projectId+'/subtitles/'+first.id,'PATCH',{end_time:1.25});
  await p.getByText(/Câu đã thay đổi ở phiên khác/).waitFor();assert.equal(await p.getByLabel('Bắt đầu (giây)',{exact:true}).inputValue(),'0.25');
  assert.equal(await p.getByRole('button',{name:'Lưu',exact:true}).isDisabled(),true);await p.getByRole('button',{name:'Nạp bản mới',exact:true}).click();
  assert.equal(await p.getByLabel('Kết thúc (giây)',{exact:true}).inputValue(),'1.25');await p.getByRole('button',{name:'Hủy',exact:true}).click();
 });
 await scenario('overlapping subtitles remain visible together in preview',async()=>{
  const list=(await cues()).items;await api('/projects/'+projectId+'/subtitles/'+list[1].id,'PATCH',{start_time:1.,translated_text:'Overlapping second line'});
  await p.getByText('Chồng thời gian',{exact:true}).first().waitFor();
  await p.locator('video').evaluate(v=>{v.pause();v.currentTime=1.1;v.dispatchEvent(new Event('timeupdate'))});
  await p.getByText('Ban sua thu cong',{exact:true}).first().waitFor();
  await until(()=>p.locator('video').evaluate(v=>Math.abs(v.currentTime-1.1)<.01),'overlap seek');
  await until(()=>p.getByText('Overlapping second line',{exact:true}).count().then(n=>n>=2),'second preview line');
  assert.ok(await p.getByText('Ban sua thu cong',{exact:true}).count()>=2);
  await p.screenshot({path:OUT+'/overlapping-preview.png',fullPage:true});
  await api('/projects/'+projectId+'/subtitles/'+list[1].id,'PATCH',{start_time:1.5,translated_text:'Tam biet'});
 });
 await scenario('speaker changes synchronize and drafts reject remote overwrite',async()=>{
  await api('/projects/'+projectId+'/speakers','POST',{speaker_tag:'SPEAKER_00',display_name:'Remote name 1'});await until(()=>p.getByTitle('Cấu hình xưng hô nhân vật').textContent().then(x=>x.includes('(1)')),'speaker count');
  await p.getByTitle('Cấu hình xưng hô nhân vật').click();const field=dialog().getByPlaceholder('Tên tiếng Việt (VD: Mục Thần)');await field.fill('Unsaved speaker draft');
  await api('/projects/'+projectId+'/speakers/SPEAKER_00','PATCH',{display_name:'Remote name 2'});await p.getByText(/Bản nháp được giữ lại/).waitFor();assert.equal(await field.inputValue(),'Unsaved speaker draft');assert.equal(await dialog().getByRole('button',{name:'Lưu Hồ Sơ & Ma Trận'}).isDisabled(),true);
  await p.getByRole('button',{name:'Tải lại dữ liệu',exact:true}).click();assert.equal(await field.inputValue(),'Remote name 2');await field.fill('Saved speaker name');await dialog().getByLabel('Tốc độ SPEAKER_00',{exact:true}).fill('1.1');await dialog().getByRole('button',{name:'Lưu Hồ Sơ & Ma Trận'}).click();await dialog().waitFor({state:'hidden'});assert.equal((await api('/projects/'+projectId+'/speakers')).speakers[0].display_name,'Saved speaker name');
 });
 await scenario('glossary UI, CSV round trip and remote count',async()=>{
  await p.getByTitle('Từ điển thuật ngữ dịch').click();await dialog().getByPlaceholder('Từ gốc (VD: 机甲 / Mecha)').fill('Alpha');await dialog().getByPlaceholder('Bản dịch tiếng Việt chuẩn (VD: Cơ giáp)').fill('An pha');await dialog().locator('button[type=submit]').click();await dialog().getByText('Alpha',{exact:true}).waitFor();
  await dialog().locator('input[type=file]').setInputFiles({name:'terms.csv',mimeType:'text/csv',buffer:Buffer.from('source_term,target_term,category,context_note\r\n"A,B","C,D",PROPER_NAME,"line 1\nline 2"')});
  await dialog().getByText('A,B',{exact:true}).waitFor();const glossary=await api('/projects/'+projectId+'/glossary');assert.ok(glossary.items.some(x=>x.source_term==='A,B'&&x.context_note==='line 1\nline 2'));
  const exported=await p.request.get(BASE+'/api/v1/projects/'+projectId+'/glossary/export?format=csv');assert.ok((await exported.text()).includes('"A,B"'));await close();
  await observer.getByTitle('Từ điển thuật ngữ dịch').click();await observer.getByRole('dialog').getByText('A,B',{exact:true}).waitFor();await observer.getByRole('dialog').getByRole('button',{name:'Đóng',exact:true}).first().click();
 });
 await scenario('selected retranslation executes durable job',async()=>{
  await p.getByRole('button',{name:'Chọn tất cả',exact:true}).click();await p.getByRole('button',{name:'Dịch Lại (2)',exact:true}).click();await until(async()=>(await cues()).items[0].translated_text==='Xin chao','retranslation');await idle();await p.getByText('Xin chao',{exact:true}).first().waitFor();
 });
 await scenario('dubbing configuration, actual media mux and reopen settings',async()=>{
  await p.getByRole('button',{name:/Lồng Tiếng AI \(Nova\)/}).click();await dialog().getByText('Chọn Giọng Đọc AI',{exact:true}).waitFor();
  const speed=dialog().locator('input[type=range][min="0.8"]');await speed.fill('1.2');await dialog().locator('select').selectOption('tts-1-hd');await dialog().getByRole('checkbox').check();const previewResponse=p.waitForResponse(r=>r.url().endsWith('/tts/preview'));await dialog().getByRole('button',{name:/Nghe Thử/i}).first().click();assert.equal((await previewResponse).status(),200);
  await dialog().getByRole('button',{name:/Bắt Đầu Lồng Tiếng Ngay/}).click();await dialog().waitFor({state:'hidden'});await idle();const data=await project();assert.ok(data.dubbed_video_url&&data.dubbed_audio_url);assert.equal(data.last_dub_config.speed,1.2);assert.equal(data.last_dub_config.use_speaker_matrix,true);assert.equal(data.last_dub_config.model,'tts-1-hd');const calls=await(await p.request.post(FIXTURE+'/__e2e/control',{headers:{'x-e2e-key':KEY},data:{}})).json();assert.ok(calls.speech_calls.some(x=>x.speed===1.1&&x.model==='tts-1-hd')); 
  assert.ok((await p.request.get(BASE+data.dubbed_video_url)).ok());await p.getByRole('button',{name:/Lồng Tiếng AI \(Nova\)/}).click();assert.equal(await dialog().locator('input[type=range][min="0.8"]').inputValue(),'1.2');await close();
  const quality=await api('/tts/projects/'+projectId+'/timing');assert.equal(quality.cue_count,2);assert.ok(quality.cues.every(c=>c.audio_end<=c.end_time));
  await p.getByRole('region',{name:'Kiểm tra đồng bộ',exact:true}).getByText(/Đã kiểm tra 2 câu/).waitFor();
  await p.getByRole('region',{name:'Kiểm tra đồng bộ',exact:true}).screenshot({path:OUT+'/dubbing-quality.png'});
 });
 await scenario('burn settings, render and matching playback source',async()=>{
  await p.getByRole('button',{name:'Burn Video',exact:true}).click();await dialog().getByRole('button',{name:/Không Che/}).click();await clickAccepted(dialog().getByRole('button',{name:/Bắt Đầu Burn Video/}),'/pipeline/burn');await idle();const data=await project();assert.equal(data.status,'COMPLETED');assert.equal(data.settings_override.clean_chinese_mode,'none');assert.ok(data.burned_video_url);
  await dialog().getByText('Video đã được render và đóng gói hoàn chỉnh thành công!',{exact:true}).waitFor();await close();await until(()=>p.locator('video').getAttribute('src').then(x=>x===data.burned_video_url),'burned playback');assert.equal(await p.locator('audio').count(),0);
  await p.getByRole('button',{name:/Lồng Tiếng AI \(Có Giọng Đọc\)/}).click();await until(()=>p.locator('video').getAttribute('src').then(x=>x===data.dubbed_video_url),'dubbed playback');
 });
 await scenario('rerender completed project with another preset',async()=>{
  const old=(await project()).burned_video_url;await p.getByRole('button',{name:'Burn Video',exact:true}).click();await dialog().getByRole('button',{name:'Render lại với cấu hình khác'}).click();await dialog().getByRole('button',{name:/Bắt Đầu Burn Video/}).waitFor();
  await dialog().getByRole('button',{name:/Rạp Phim/}).click();await clickAccepted(dialog().getByRole('button',{name:/Bắt Đầu Burn Video/}),'/pipeline/burn');await idle();const data=await project();assert.notEqual(data.burned_video_url,old);await dialog().getByText('Video đã được render và đóng gói hoàn chỉnh thành công!',{exact:true}).waitFor();await close();
 });
 await scenario('subtitle export and stale outputs cleared in both tabs',async()=>{
  for(const format of ['srt','ass','vtt']){const r=await p.request.get(BASE+'/api/v1/projects/'+projectId+'/subtitles/export/'+format);assert.ok(r.ok());assert.ok((await r.text()).includes('Xin chao'))}
  await p.getByRole('button',{name:'Sửa thời gian',exact:true}).first().click();await p.locator('textarea').fill('Ban moi nhat');await p.getByLabel('Kết thúc (giây)',{exact:true}).fill('1.2');await p.getByRole('button',{name:'Lưu',exact:true}).click();await observer.getByText('Ban moi nhat',{exact:true}).first().waitFor();await until(async()=>!(await project()).burned_video_url,'invalidate render');await until(()=>p.getByRole('button',{name:/Video Gắn Sub Cứng/}).count().then(n=>n===0),'remove stale render tab');assert.equal((await project()).dubbed_audio_url,null);await p.getByRole('region',{name:'Kiểm tra đồng bộ',exact:true}).waitFor({state:'hidden'});
 });
 await scenario('mobile Studio and modal essential controls',async()=>{
  await p.setViewportSize({width:390,height:844});await p.screenshot({path:OUT+'/studio-mobile.png',fullPage:true});assert.ok(await p.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth));
  await p.getByRole('button',{name:'Sửa thời gian',exact:true}).first().click();
  for(const name of ['Bắt đầu (giây)','Kết thúc (giây)']){const box=await p.getByLabel(name,{exact:true}).boundingBox();assert.ok(box.x>=0&&box.x+box.width<=390)}
  assert.ok(await p.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth));await p.screenshot({path:OUT+'/timing-editor-mobile.png',fullPage:true});await p.getByRole('button',{name:'Hủy',exact:true}).click();
  await p.getByTitle('Cấu hình xưng hô nhân vật').click();await dialog().getByRole('button',{name:'Lưu Hồ Sơ & Ma Trận'}).scrollIntoViewIfNeeded();const box=await dialog().getByRole('button',{name:'Lưu Hồ Sơ & Ma Trận'}).boundingBox();assert.ok(box.x>=0&&box.x+box.width<=390);await p.screenshot({path:OUT+'/speaker-modal-mobile.png',fullPage:true});await close();
  await p.setViewportSize({width:1440,height:1000});await p.screenshot({path:OUT+'/studio-desktop.png',fullPage:true});
 });
 await scenario('queued project shown in processing dashboard filter',async()=>{
  await p.request.post(FIXTURE+'/__e2e/control',{headers:{'x-e2e-key':KEY},data:{delay:4}});const a=await api('/projects/from-url','POST',{url:'https://www.bilibili.com/video/BVqueued1',title:'Queued browser A',source_language:'en',target_language:'vi',auto_start_pipeline:false});const z=await api('/projects/from-url','POST',{url:'https://www.bilibili.com/video/BVqueued2',title:'Queued browser B',source_language:'en',target_language:'vi',auto_start_pipeline:false});
  await p.goto(BASE);await p.getByRole('button',{name:'PROCESSING',exact:true}).click();await p.getByRole('heading',{name:'Queued browser B',exact:true}).waitFor();await p.screenshot({path:OUT+'/dashboard-queued.png',fullPage:true});
  for(const x of [a,z])await api('/projects/'+x.id+'/reset-status','POST',{target_status:'CREATED'});
  await p.request.post(FIXTURE+'/__e2e/control',{headers:{'x-e2e-key':KEY},data:{delay:1}});
 });
 await scenario('settings loads actual backend configuration',async()=>{await p.goto(BASE+'/settings');await p.getByText('Gemini',{exact:false}).first().waitFor();assert.equal((await api('/settings/info')).storage_driver,'local')});
 await scenario('WebSocket reconnect resynchronizes missed subtitle change',async()=>{
  const before=await observer.evaluate(()=>window.__oneflSockets.filter(s=>s.url.includes('/api/v1/ws/')).length);
  await observer.evaluate(()=>window.__oneflSockets.filter(s=>s.url.includes('/api/v1/ws/')).forEach(s=>s.close()));
  const cue=(await cues()).items[0];await api('/projects/'+projectId+'/subtitles/'+cue.id,'PATCH',{translated_text:'Ban sau ket noi'});
  await observer.getByText('Ban sau ket noi',{exact:true}).first().waitFor();assert.ok(await observer.evaluate(()=>window.__oneflSockets.filter(s=>s.url.includes('/api/v1/ws/')).length)>before);
 });
 await scenario('provider failure is visible and reset synchronizes',async()=>{
  await p.goto(BASE+'/projects/'+projectId);await p.getByTitle('Bấm để chỉnh sửa bản dịch câu này').first().waitFor();
  await p.request.post(FIXTURE+'/__e2e/control',{headers:{'x-e2e-key':KEY},data:{fail_translation:true}});
  await p.getByRole('button',{name:'Chọn tất cả',exact:true}).click();await p.getByRole('button',{name:'Dịch Lại (2)',exact:true}).click();await until(async()=>(await project()).status==='FAILED','failed provider');await p.getByText(/Fixture provider unavailable/).first().waitFor();
  await api('/projects/'+projectId+'/reset-status','POST',{target_status:'WAITING_REVIEW'});await p.request.post(FIXTURE+'/__e2e/control',{headers:{'x-e2e-key':KEY},data:{fail_translation:false}});
  await until(()=>p.getByRole('button',{name:/Dịch Lại Toàn Bộ/}).isEnabled(),'reset unlock');
 });
 await scenario('deleting project exits stale Studio in another tab',async()=>{
  await api('/projects/'+projectId,'DELETE');await observer.waitForURL(BASE+'/');assert.equal((await p.request.get(BASE+'/api/v1/projects/'+projectId)).status(),404);
 });
 const tool=async(name,args)=>{const r=await api('/agent/execute-tool','POST',{tool_name:name,arguments:args});assert.equal(r.success,true,JSON.stringify(r));return r.result};
 await scenario('Agent ASR durable job synchronizes extraction-only Studio state',async()=>{
  const created=await api('/projects','POST',{title:'Agent browser chain',source_language:'en',target_language:'vi'});projectId=created.id;
  const upload=await p.request.post(BASE+'/api/v1/projects/'+projectId+'/upload',{multipart:{auto_start_pipeline:'false',file:{name:'agent-source.mp4',mimeType:'video/mp4',buffer:fs.readFileSync(OUT+'/runtime/source.mp4')}}});assert.ok(upload.ok(),await upload.text());
  await p.goto(BASE+'/projects/'+projectId);await p.getByTitle('Cấu hình xưng hô nhân vật').waitFor();
  const queued=await tool('extract_and_transcribe_audio',{project_id:projectId});assert.equal(queued.status,'QUEUED');await idle();
  const finished=await tool('get_job_status',{project_id:projectId,job_id:queued.job_id});assert.equal(finished.status,'SUCCEEDED');assert.equal(finished.result.total_cues,2);
  await p.getByText('Trích xuất & Nhận diện thoại',{exact:true}).waitFor();await p.getByText('Đã nhận diện 2 câu; chờ dịch phụ đề',{exact:true}).first().waitFor();
  const context=await tool('get_project_context',{project_id:projectId,offset:1,limit:1});assert.equal(context.total_cues,2);assert.equal(context.cues.length,1);assert.equal(context.cues[0].translated_text,null);
  await p.screenshot({path:OUT+'/agent-asr.png',fullPage:true});
 });
 await scenario('Agent pipeline export burn publishes job artifacts into Studio',async()=>{
  const translated=await tool('start_project_pipeline',{project_id:projectId,stage:'TRANSLATING'});assert.equal(translated.status,'QUEUED');await idle();
  await p.getByText('Xin chao',{exact:true}).first().waitFor();
  const exported=await tool('export_subtitles',{project_id:projectId,format:'ass',preset:'cinema',bilingual:true});
  const file=await p.request.get(BASE+exported.artifact_url);assert.ok(file.ok());assert.ok((await file.text()).includes('Xin chao'));
  const queued=await tool('burn_video_subtitles',{project_id:projectId,clean_chinese_mode:'none'});assert.equal(queued.status,'QUEUED');await idle();
  const finished=await tool('get_job_status',{project_id:projectId,job_id:queued.job_id});assert.equal(finished.status,'SUCCEEDED');assert.equal(finished.artifact_current,true);
  const data=await project();assert.equal(data.burned_video_url,finished.result.output_url);await until(()=>p.locator('video').getAttribute('src').then(x=>x===data.burned_video_url),'Agent burned playback source');
  await p.screenshot({path:OUT+'/agent-studio-completed.png',fullPage:true});await api('/projects/'+projectId,'DELETE');
 });
 await scenario('no browser runtime exception or external resource failure',async()=>{assert.deepEqual(errors,[]);assert.deepEqual(networkErrors,[])});
 console.log('BROWSER SCENARIOS',results.length);
}catch(e){await p.screenshot({path:OUT+'/failure.png',fullPage:true}).catch(()=>{});console.error(e);process.exitCode=1}
finally{await p.request.post(FIXTURE+'/__e2e/control',{headers:{'x-e2e-key':KEY},data:{fail_translation:false,fail_tts:false,delay:1}}).catch(()=>{});write();await context.tracing.stop({path:OUT+'/browser-trace.zip'});await browser.close()}
})().catch(e=>{console.error(e);process.exit(1)});
