"""Fail closed: no general downloader is permitted to make legacy URL requests."""
from fastapi import HTTPException

URL_DISABLED = ('Legacy URL ingestion is disabled: redirects, manifests and secondary downloader '
                'requests have no enforced network isolation. Upload a local video file instead.')


def reject_url(source_url):
    if source_url:
        raise HTTPException(status_code=503, detail=URL_DISABLED)
