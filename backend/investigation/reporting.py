"""Local report output with credential redaction; never dump environment values."""
import json
import os
import re
from .ranking import artifact_dir


def redact(value):
    secrets = [v for k, v in os.environ.items() if len(v) >= 8 and any(x in k.upper() for x in ('TOKEN', 'SECRET', 'API_KEY', 'PASSWORD'))]
    def clean(item):
        if isinstance(item, dict):
            return {k: '[redacted]' if k.lower() in {'api_key', 'token', 'password', 'authorization', 'access_token', 'secret'} else clean(v) for k, v in item.items()}
        if isinstance(item, list):
            return [clean(v) for v in item]
        if isinstance(item, str):
            for secret in secrets:
                item = item.replace(secret, '[redacted]')
            return re.sub(r'(?i)((?:api_key|access_token|token|password|secret)=)[^&\s"<>]+', r'\1[redacted]', item)
        return item
    return clean(value)


def save(name, report):
    if not re.fullmatch(r'[a-zA-Z0-9_.-]+', name):
        raise ValueError('Invalid report name')
    path = artifact_dir() / 'pilot-reports'
    path.mkdir(parents=True, exist_ok=True)
    safe = redact(report)
    text = json.dumps(safe, indent=2, sort_keys=True)
    (path / f'{name}.json').write_text(text)
    (path / f'{name}.md').write_text(f'# {name}\n\n```json\n{text}\n```\n')
    return safe
