/* Run from root: node frontend/tests/regressions.cjs
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

function loadComponent(relativePath, exported = 'default') {
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
      if (name === '@/lib/csv') return { parseCsv() { return []; } };
      if (name === '@/lib/api') return { api: { getGlossaryExportUrl: () => '/export' } };
      if (name === '@/lib/projectView') return projectView;
      if (name === '@/lib/videoCleanup') return cleanupHelpers;
      if (name === '@/lib/burnPresentation') return presentationHelpers;
      if (name === '@/lib/ttsPresentation') return ttsHelpers;
      if (name === './BurnStylePreview') return {default: () => null};
      if (name === './VideoCleanupEditor' || name === './CleanupQualitySummary') return {default: () => null};
      if (name === '@/components/PipelineProgressTracker') return { getFriendlyStageName: s => s };
      if (name === 'react-hot-toast') return { __esModule: true, default: {} };
      throw new Error(`Unexpected import ${name}`);
    },
  };
  vm.runInNewContext(compiled, sandbox, { filename: relativePath });
  return exports[exported];
}

const projectView = {};
new Function('exports', ts.transpileModule(fs.readFileSync(path.join(root, 'frontend/src/lib/projectView.ts'), 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS }
}).outputText)(projectView);
const results = [];
const cleanupHelpers = {};
new Function('exports', ts.transpileModule(fs.readFileSync(path.join(root, 'frontend/src/lib/videoCleanup.ts'), 'utf8'), {
  compilerOptions: {module: ts.ModuleKind.CommonJS}
}).outputText)(cleanupHelpers);
const presentationHelpers = {};
new Function('exports', ts.transpileModule(fs.readFileSync(path.join(root, 'frontend/src/lib/burnPresentation.ts'), 'utf8'), {
  compilerOptions: {module: ts.ModuleKind.CommonJS}
}).outputText)(presentationHelpers);
const ttsHelpers = {};
new Function('exports', ts.transpileModule(fs.readFileSync(path.join(root, 'frontend/src/lib/ttsPresentation.ts'), 'utf8'), {
  compilerOptions: {module: ts.ModuleKind.CommonJS}
}).outputText)(ttsHelpers);
for (const [relativePath, props] of [
  ['frontend/src/components/CreateProjectModal.tsx', { onClose() {}, onSuccess() {} }],
  ['frontend/src/components/GlossaryModal.tsx', { terms: [], projectId: 'audit', onClose() {}, onUpdated() {} }],
  ['frontend/src/components/DubbingModal.tsx', { project: {id:'test',status:'CREATED'}, onClose() {}, onDubbingStarted() {} }],
  ['frontend/src/components/BurnProgressModal.tsx', { project: {id:'test',status:'CREATED'}, onClose() {}, onBurnStarted() {} }],
  ['frontend/src/components/SpeakerMatrixModal.tsx', { projectId:'test',speakers:[],relationships:[],onClose() {},onUpdated() {} }],
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
  if (error) throw new Error(`Component rerender failed for ${relativePath}: ${error}`);
  results.push({ component: relativePath, passed: true });
}
console.log(JSON.stringify({ passedComponents: results.length, results }, null, 2));

const dashboard = fs.readFileSync(path.join(root, 'frontend/src/app/page.tsx'), 'utf8');
if (dashboard.includes('}, [projects]);')) throw new Error('Polling depends on the response array');

const assert = require('node:assert/strict');
const csvModule = { exports: {} };
const csvSource = ts.transpileModule(fs.readFileSync(path.join(root, 'frontend/src/lib/csv.ts'), 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS }
}).outputText;
new Function('exports', csvSource)(csvModule.exports);
assert.deepEqual(csvModule.exports.parseCsv('source,target,note\r\n"A,B","Say ""hello""","line 1\nline 2"'), [
  ['source','target','note'], ['A,B','Say "hello"','line 1\nline 2']
]);
console.log('CSV quoted/multiline regression: passed');

const timelineModule = {};
new Function('exports', ts.transpileModule(fs.readFileSync(path.join(root, 'frontend/src/lib/subtitleTimeline.ts'), 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS }
}).outputText)(timelineModule);
const at = timelineModule.indexSubtitleTimeline([
  {id: 'short', start_time: 2, end_time: 3},
  {id: 'long', start_time: 0, end_time: 100},
  {id: 'middle', start_time: 10, end_time: 11},
]);
assert.equal(at(2.5).id, 'short');
assert.equal(at(50).id, 'long');
assert.equal(at(100), undefined);
assert.equal(at(-1), undefined);
console.log('Overlapping and unordered subtitle timeline: passed');
const allAt = timelineModule.indexAllSubtitleTimeline([
  {id:'later',start_time:2,end_time:4}, {id:'earlier',start_time:1,end_time:3},
]);
assert.deepEqual(allAt(2.5).map(c => c.id), ['earlier','later']);
assert.deepEqual(allAt(3).map(c => c.id), ['later']);
assert.deepEqual(allAt(4), []);
assert.deepEqual(timelineModule.indexAllSubtitleTimeline([])(0), []);
console.log('All-active preview keeps simultaneous subtitle lines: passed');

const media = {status:'COMPLETED',original_video_url:'/source.mp4',burned_video_url:'/burned.mp4',dubbed_audio_url:'/speech.mp3'};
assert.equal(projectView.resolvePlayback(media,'auto').kind,'burned');
assert.equal(projectView.resolvePlayback(media,'auto').dubbedAudioUrl,undefined);
assert.equal(projectView.resolvePlayback(media,'dubbed').videoUrl,'/source.mp4');
assert.equal(projectView.resolvePlayback(media,'dubbed').isBurnedVideo,false);
assert.equal(projectView.resolvePlayback({...media,burned_video_url:null},'burned').kind,'dubbed');
for (const status of ['QUEUED','DUBBING','TRANSLATING']) assert.equal(projectView.isProjectBusy({status}),true);
assert.equal(projectView.isProjectBusy({status:'WAITING_REVIEW',active_job_id:'pending-ack'}),true);
console.log('Playback source and job state contracts: passed');

const workflow=loadComponent('frontend/src/components/PipelineProgressTracker.tsx','getWorkflowDetails');
assert.equal(workflow({status:'COMPLETED',current_stage:'COMPLETED',last_job_kind:'BURN',burned_video_url:'/burn.mp4',dubbed_video_url:'/dub.mp4'}).type,'BURNING');
assert.equal(workflow({status:'WAITING_REVIEW',current_stage:'WAITING_REVIEW',last_job_kind:'DUBBING',dubbed_video_url:'/dub.mp4'}).type,'DUBBING');
assert.equal(workflow({status:'FAILED',current_stage:'FAILED',last_job_kind:'DUBBING'}).type,'DUBBING');
assert.equal(workflow({status:'QUEUED',current_stage:'QUEUED',last_job_kind:'BURN'}).type,'QUEUED');
console.log('Queued/completed/failed workflow kind: passed');
const asrWorkflow=workflow({status:'WAITING_REVIEW',current_stage:'ASR_COMPLETE',last_job_kind:'TRANSCRIBE',progress_percentage:100},2,0);
assert.equal(asrWorkflow.type,'ASR');
assert.equal(asrWorkflow.steps.length,2);
assert.equal(asrWorkflow.steps[1].status,'completed');
assert.equal(workflow({status:'FAILED',current_stage:'FAILED',last_job_kind:'TRANSCRIBE',progress_percentage:10}).steps[0].status,'failed');
console.log('Agent ASR workflow preserves extraction-only semantics: passed');
const Tracker = loadComponent('frontend/src/components/PipelineProgressTracker.tsx');
const trackerBase = {id:'resume',title:'Recovery',status:'DUBBING',current_stage:'DUBBING_VOICE_SYNTHESIS',progress_percentage:30,last_job_kind:'DUBBING',last_dub_config:{voice:'nova'}};
const renderTracker = project => renderToString(React.createElement(Tracker,{project,onRetry() {},onRefresh() {}}));
for (const project of [
  {...trackerBase,active_job_id:'running'},
  {...trackerBase,status:'QUEUED',active_job_id:'queued'},
  {...trackerBase,status:'FAILED',active_job_id:'finishing'},
  {...trackerBase,status:'PROCESSING',last_job_kind:'PIPELINE',current_stage:'TRANSLATING',active_job_id:'translation'},
  {...trackerBase,status:'CREATED',last_dub_config:null,last_job_kind:null,current_stage:'CREATED'},
]) {
  const html = renderTracker(project);
  assert.ok(!html.includes('Tiếp tục chạy') && !html.includes('Tiếp tục từ điểm dừng'), 'Never offer another resume while a job owns this project');
}
const failedDub = renderTracker({...trackerBase,status:'FAILED',active_job_id:null});
assert.ok(failedDub.includes('Tiếp tục chạy'), 'Interrupted saved dubbing can resume');
assert.ok(!failedDub.includes('Thử lại</span>'), 'Dubbing failure must not retry the translation pipeline');
assert.ok(!renderTracker({...trackerBase,status:'FAILED',last_dub_config:null}).includes('Tiếp tục chạy'));
assert.ok(renderTracker({...trackerBase,status:'CANCELLED'}).includes('Tiếp tục chạy'));
assert.ok(renderTracker({...trackerBase,status:'FAILED',last_dub_config:null}).includes('Chưa có cấu hình lồng tiếng'));
console.log('Tracker recovery respects durable job ownership and saved dubbing config: passed');
