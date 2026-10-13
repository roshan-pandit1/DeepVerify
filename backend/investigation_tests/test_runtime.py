from pathlib import Path
import os
import subprocess
import sys

import pytest
from investigation.runtime import BACKEND, storage_path, validate_storage


def test_paths_do_not_change_with_working_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv('INVESTIGATION_DB', 'existing.db')
    assert storage_path('INVESTIGATION_DB', 'deepfake.db') == BACKEND / 'existing.db'


def test_private_deployment_requires_explicit_shared_paths(monkeypatch):
    monkeypatch.setenv('INVESTIGATION_DEPLOYMENT', 'private')
    monkeypatch.setenv('INVESTIGATION_DB', 'relative.db')
    with pytest.raises(ValueError, match='absolute path'):
        validate_storage()


def test_actionable_startup_error(tmp_path):
    env = dict(os.environ, DEEPVERIFY_PYTHON=sys.executable, INVESTIGATION_DEPLOYMENT='local',
               INVESTIGATION_DB=str(tmp_path / 'missing' / 'db.sqlite'))
    result = subprocess.run(['bash', str(BACKEND / 'start.sh'), 'api'], env=env, capture_output=True, text=True)
    assert result.returncode != 0
    assert 'Mount the intended data directory' in result.stderr
    assert not (tmp_path / 'missing').exists()
