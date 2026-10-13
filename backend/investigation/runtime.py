"""Stable storage locations shared by API, workers and administrative CLIs."""
import os
from pathlib import Path
import tempfile

from dotenv import load_dotenv

BACKEND = Path(__file__).resolve().parents[1]
load_dotenv(BACKEND / '.env')


def storage_path(name, default):
    path = Path(os.getenv(name, default)).expanduser()
    return path if path.is_absolute() else BACKEND / path


def validate_storage():
    if os.getenv('INVESTIGATION_DEPLOYMENT', 'local') != 'local':
        for name in ('INVESTIGATION_DB', 'INVESTIGATION_ARTIFACTS'):
            if not os.getenv(name) or not Path(os.environ[name]).is_absolute():
                raise ValueError(f'{name} must be an explicit absolute path on shared durable storage for private deployment.')
    database = storage_path('INVESTIGATION_DB', 'deepfake.db')
    if not database.parent.is_dir() or database.is_dir():
        raise ValueError('INVESTIGATION_DB must name a SQLite file in an existing writable directory. Mount the intended data directory first.')
    artifacts = storage_path('INVESTIGATION_ARTIFACTS', 'investigation-data')
    try:
        artifacts.mkdir(parents=True, exist_ok=True)
        for directory in (database.parent, artifacts):
            with tempfile.TemporaryFile(dir=directory):
                pass
    except OSError:
        raise ValueError('Database/artifact storage is not writable. Check the shared mount and service user permissions.') from None
