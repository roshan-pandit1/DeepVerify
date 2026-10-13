"""Private structural diagnostics: no exception messages, URLs, locals or source text."""
import json
import os
from pathlib import Path
import traceback

from .ranking import artifact_dir
from .store import now, uid


def record(exc, operation):
    incident = uid()
    directory = artifact_dir() / 'diagnostics'
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(directory, 0o700)
    entry = {'incident': incident, 'time': now(), 'operation': operation,
             'exception_type': type(exc).__name__,
             'sqlite_errorcode': getattr(exc, 'sqlite_errorcode', None),
             'frames': [{'file': Path(f.filename).name, 'line': f.lineno, 'function': f.name}
                        for f in traceback.extract_tb(exc.__traceback__)]}
    descriptor = os.open(directory / 'worker.jsonl', os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    with os.fdopen(descriptor, 'a') as output:
        os.fchmod(output.fileno(), 0o600)
        output.write(json.dumps(entry) + '\n')
    return incident
