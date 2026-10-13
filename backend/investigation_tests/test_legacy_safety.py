import asyncio
import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from legacy_safety import reject_url


@pytest.mark.parametrize('url', [
    'http://127.0.0.1/', 'http://10.0.0.1/', 'http://169.254.169.254/latest/meta-data/',
    'http://[::1]/', 'http://192.0.2.1/', 'https://example.com/redirect-to-private',
    'https://example.com/public-video.mp4', 'https://example.com/manifest.m3u8',
])
def test_all_legacy_urls_fail_closed_without_network(url, monkeypatch):
    with pytest.raises(HTTPException) as failure:
        reject_url(url)
    assert failure.value.status_code == 503
    # Import the actual processor without the unrelated heavyweight pipeline package.
    monkeypatch.setitem(sys.modules, 'cv2', SimpleNamespace())
    monkeypatch.setitem(sys.modules, 'config', SimpleNamespace(get_settings=lambda: pytest.fail('No configuration/network needed')))
    name = 'isolated_video_processor'
    spec = importlib.util.spec_from_file_location(name, Path(__file__).resolve().parents[1] / 'pipeline/video_processor.py')
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, name, module)
    spec.loader.exec_module(module)
    result = asyncio.run(module.download_from_url('test-job', url))
    assert result.error_code == 'LEGACY_URL_INGESTION_DISABLED'
    assert result.video_path == ''


def test_file_only_submission_is_permitted():
    reject_url(None)
    reject_url('')
