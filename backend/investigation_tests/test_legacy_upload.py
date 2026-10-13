import asyncio
from pathlib import Path

import pytest
from fastapi import HTTPException
from legacy_upload import receive_upload, CHUNK_BYTES


class Upload:
    filename = '../../untrusted.mp4'

    def __init__(self, data, interrupt=None):
        self.data = data
        self.position = 0
        self.sizes = []
        self.closed = False
        self.interrupt = interrupt

    async def read(self, size):
        assert 0 < size <= CHUNK_BYTES
        self.sizes.append(size)
        if self.interrupt and self.position:
            raise self.interrupt
        result = self.data[self.position:self.position + size]
        self.position += len(result)
        return result

    async def close(self):
        self.closed = True


def test_accepted_exact_limit_and_server_filename(tmp_path):
    async def run():
        upload = Upload(b'a' * (CHUNK_BYTES + 9))
        async with receive_upload(upload, tmp_path / 'server-id', len(upload.data)) as (path, size):
            assert Path(path).name == 'video.mp4'
            assert Path(path).read_bytes() == upload.data
            assert size == len(upload.data)
        assert Path(path).exists() and upload.closed
    asyncio.run(run())


def test_oversize_stops_at_first_extra_byte_and_cleans(tmp_path):
    async def run():
        upload = Upload(b'a' * 1000000)
        with pytest.raises(HTTPException) as failure:
            async with receive_upload(upload, tmp_path / 'oversize', 100):
                pytest.fail('Oversized upload must never reach persistence')
        assert failure.value.status_code == 413
        assert upload.position == 101 and upload.closed
        assert not (tmp_path / 'oversize').exists()
    asyncio.run(run())


@pytest.mark.parametrize('failure', [OSError('interrupted read'), asyncio.CancelledError()])
def test_read_failure_and_cancellation_cleanup(tmp_path, failure):
    async def run():
        upload = Upload(b'a' * (CHUNK_BYTES * 2), failure)
        with pytest.raises(type(failure)):
            async with receive_upload(upload, tmp_path / 'interrupted', CHUNK_BYTES * 3):
                pytest.fail('Incomplete upload must not be accepted')
        assert not (tmp_path / 'interrupted').exists() and upload.closed
    asyncio.run(run())


def test_persistence_failure_after_upload_cleans_file(tmp_path):
    async def run():
        upload = Upload(b'video')
        with pytest.raises(RuntimeError, match='database'):
            async with receive_upload(upload, tmp_path / 'db-failure', 100):
                raise RuntimeError('database failure')
        assert not (tmp_path / 'db-failure').exists()
    asyncio.run(run())


def test_existing_directory_is_never_deleted(tmp_path):
    async def run():
        directory = tmp_path / 'existing'
        directory.mkdir()
        (directory / 'keep').write_text('keep')
        with pytest.raises(FileExistsError):
            async with receive_upload(Upload(b'video'), directory, 100):
                pass
        assert (directory / 'keep').read_text() == 'keep'
    asyncio.run(run())
