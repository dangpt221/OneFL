"""Public Bilibili metadata fallback and durable URL download contracts."""
import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import yt_dlp
from yt_dlp.extractor.bilibili import BiliBiliIE
from yt_dlp.utils import DownloadError, ExtractorError

URL = 'https://www.bilibili.com/video/BV1MHh66uEFH/?p=2'
BVID = 'BV1MHh66uEFH'


def adapter(monkeypatch, *, page='<html>new page</html>', detail=None, final_url=URL):
    from app.services.bilibili_extractor import BilibiliInitialStateIE
    ydl = yt_dlp.YoutubeDL({'quiet': True, 'no_warnings': True})
    ie = BilibiliInitialStateIE(ydl)
    monkeypatch.setattr(BiliBiliIE, '_download_webpage_handle', lambda *a, **kw: (page, SimpleNamespace(url=final_url)))
    calls = []
    monkeypatch.setattr(ie, '_sign_wbi', lambda query, _: {**query, 'signature': 'fixture'})
    def api(url, video_id, **kwargs):
        calls.append((url, video_id, kwargs['query']))
        return detail if detail is not None else {
            'code': 0, 'data': {'View': {'bvid': BVID, 'aid': 123, 'cid': 1, 'title': 'Real metadata',
                'owner': {'name': 'Uploader', 'mid': 9}, 'duration': 6,
                'pages': [{'page': 1, 'cid': 1}, {'page': 2, 'cid': 2}]}, 'Tags': [{'tag_name': 'test'}]}}
    monkeypatch.setattr(ie, '_download_json', api)
    return ie, calls


def state(ie, page):
    return ie._search_json(r'window\.__INITIAL_STATE__\s*=', page, 'initial state', BVID, default=None)


def test_missing_html_state_uses_valid_signed_metadata(monkeypatch):
    ie, calls = adapter(monkeypatch)
    page, response = ie._download_webpage_handle(URL, BVID)
    data = state(ie, page)
    assert data['videoData']['bvid'] == BVID
    assert data['videoData']['pages'][1]['cid'] == 2
    assert data['upData']['name'] == 'Uploader' and data['tags'][0]['tag_name'] == 'test'
    assert calls[0][2] == {'bvid': BVID, 'platform': 'web', 'signature': 'fixture'}
    assert response.url == URL  # Upstream still selects the original multipart p=2.


@pytest.mark.parametrize('page', [
    '<script>window.__INITIAL_STATE__={"videoData":{"bvid":"existing"}}</script>',
    '<script>window._riskdata_={"v_voucher":"challenge"}</script>',
])
def test_existing_state_and_explicit_risk_stay_with_upstream(monkeypatch, page):
    ie, calls = adapter(monkeypatch, page=page)
    assert ie._download_webpage_handle(URL, BVID)[0] == page
    assert calls == []


@pytest.mark.parametrize('detail', [
    {'code': -403, 'message': 'Forbidden'},
    {'code': -404, 'message': 'Not available'},
    {'code': 0, 'data': {'View': {'bvid': 'BV1WRONG0000', 'cid': 1}}},
    {'code': 0, 'data': {'View': {'bvid': BVID}}},
])
def test_denied_or_incomplete_metadata_cannot_create_playable_state(monkeypatch, detail):
    ie, _ = adapter(monkeypatch, detail=detail)
    with pytest.raises(ExtractorError):
        ie._download_webpage_handle(URL, BVID)


def test_av_query_and_bangumi_redirect_remain_supported(monkeypatch):
    ie, calls = adapter(monkeypatch, final_url='https://www.bilibili.com/video/av123?p=2')
    assert state(ie, ie._download_webpage_handle('https://www.bilibili.com/video/av123?p=2', '123')[0])['videoData']['bvid'] == BVID
    assert calls[0][2]['aid'] == '123'
    detail = {'code': 0, 'data': {'View': {'redirect_url': 'https://www.bilibili.com/bangumi/play/ep123'}}}
    ie, _ = adapter(monkeypatch, detail=detail)
    assert ie._download_webpage_handle(URL, BVID)[0] == '<html>new page</html>'


def test_foreign_redirect_not_rewritten(monkeypatch):
    ie, calls = adapter(monkeypatch, final_url='https://www.bilibili.com/404')
    assert ie._download_webpage_handle(URL, BVID)[0] == '<html>new page</html>'
    assert not calls


def test_bilibili_adapter_replaces_only_its_extractor():
    from app.services.video_downloader import video_downloader
    from app.services.bilibili_extractor import BilibiliInitialStateIE
    with video_downloader._create_ydl({'quiet': True}, 'bilibili') as ydl:
        assert isinstance(ydl.get_info_extractor('BiliBili'), BilibiliInitialStateIE)
    with video_downloader._create_ydl({'quiet': True}, 'youtube') as ydl:
        assert not isinstance(ydl.get_info_extractor('BiliBili'), BilibiliInitialStateIE)


@pytest.mark.parametrize(('raw', 'code'), [
    ('ERROR: [BiliBili] id: Unable to extract initial state; please report this issue', 'BILIBILI_EXTRACTION_FAILED'),
    ('HTTP Error 412: Precondition Failed', 'BILIBILI_ACCESS_RESTRICTED'),
    ('Sign in to confirm; login required', 'BILIBILI_LOGIN_REQUIRED'),
])
@pytest.mark.asyncio
async def test_metadata_and_download_share_actionable_failures(monkeypatch, tmp_path, raw, code):
    from app.services import video_downloader as module
    from app.services import url_security
    monkeypatch.setattr(url_security, 'validate_video_url', AsyncMock())
    class FailingDL:
        def __init__(self, opts): pass
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def add_info_extractor(self, ie): pass
        def extract_info(self, *args, **kwargs): raise DownloadError(raw)
    monkeypatch.setattr(module.yt_dlp, 'YoutubeDL', FailingDL)
    result = await module.video_downloader.extract_info(URL)
    assert not result['success'] and result['error_code'] == code
    assert 'tải file' in result['error'].lower()
    assert 'please report this issue' not in result['error']
    with pytest.raises(RuntimeError) as failure:
        await module.video_downloader.download_video(URL, tmp_path)
    assert str(failure.value) == result['error']
    assert isinstance(failure.value.__cause__, DownloadError)


def test_platform_uses_hostname_not_query_string():
    from app.services.video_downloader import video_downloader
    assert video_downloader.detect_platform('https://youtube.com/watch?v=bilibili.com') == 'youtube'
    assert video_downloader.detect_platform('https://bilibili.com.example.org/video/123') == 'generic'


@pytest.mark.asyncio
@pytest.mark.parametrize(('local', 'stage', 'expected'), [
    (False, None, 'DOWNLOAD'), (False, 'INGESTING', 'DOWNLOAD'), (True, None, 'PIPELINE'),
])
async def test_retry_requeues_source_download_when_local_media_missing(monkeypatch, tmp_path, local, stage, expected):
    from app.api.v1.pipeline import trigger_pipeline
    from app.schemas.translation import PipelineTriggerRequest
    from app.services.job_service import job_service
    source = tmp_path / 'source.mp4'
    if local: source.write_bytes(b'fixture')
    project = SimpleNamespace(id='p', local_video_path=str(source), original_video_url=URL)
    db = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(scalar_one_or_none=lambda: project)))
    enqueue = AsyncMock(return_value=SimpleNamespace(id='job'))
    monkeypatch.setattr(job_service, 'enqueue', enqueue)
    await trigger_pipeline('p', PipelineTriggerRequest(stage=stage, force_reprocess=True), None, db)
    args = enqueue.call_args.args
    assert args[2] == expected
    if expected == 'DOWNLOAD':
        assert args[3] == {'url': URL, 'auto_start': True, 'force_reprocess': True}


@pytest.mark.asyncio
async def test_later_stage_cannot_skip_missing_url_source(monkeypatch):
    from app.api.v1.pipeline import trigger_pipeline
    from app.schemas.translation import PipelineTriggerRequest
    from app.services.job_service import job_service
    from fastapi import HTTPException
    project = SimpleNamespace(id='p', local_video_path=None, original_video_url=URL)
    db = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(scalar_one_or_none=lambda: project)))
    enqueue = AsyncMock(); monkeypatch.setattr(job_service, 'enqueue', enqueue)
    with pytest.raises(HTTPException) as error:
        await trigger_pipeline('p', PipelineTriggerRequest(stage='TRANSLATING'), None, db)
    assert error.value.status_code == 409 and not enqueue.called


@pytest.mark.asyncio
async def test_ingestion_preserves_force_reprocess(monkeypatch, tmp_path):
    from app.services import ingestion_service as module
    from app.services.workflow_engine import workflow_engine
    source = tmp_path / 'source.mp4'; source.write_bytes(b'fixture')
    project = SimpleNamespace(title='Bilibili Video')
    db = SimpleNamespace(get=AsyncMock(return_value=project), commit=AsyncMock())
    monkeypatch.setattr(module.video_downloader, 'download_video', AsyncMock(return_value={'file_path': source, 'title': 'Actual title'}))
    monkeypatch.setattr(module, 'probe_media', AsyncMock(return_value=3.))
    monkeypatch.setattr(module.storage_service, 'get_project_dir', lambda _: tmp_path)
    monkeypatch.setattr(module.storage_service, 'get_relative_url', lambda _: '/static/video.mp4')
    pipeline = AsyncMock(); monkeypatch.setattr(workflow_engine, 'run_pipeline', pipeline)
    await module.download_project(db, 'p', URL, force_reprocess=True)
    pipeline.assert_awaited_once_with(db, 'p', force_reprocess=True)
    assert project.local_video_path == str(source) and project.original_video_url == '/static/video.mp4'
