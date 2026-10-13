"""Real process/HTTP smoke with temporary synthetic data; never a quality benchmark."""
import argparse
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import tempfile
import time

import httpx

from .ranking import artifact_dir
from .reporting import save


def unused_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def wait_ready(url, process):
    for _ in range(100):
        if process.poll() is not None:
            raise RuntimeError('Smoke server exited before becoming ready; check dependencies/build')
        try:
            response = httpx.get(url, timeout=2, trust_env=False)
            if response.status_code == 200:
                return response
        except httpx.HTTPError:
            pass
        time.sleep(.1)
    raise RuntimeError('Smoke server startup timed out')


def run(with_frontend=False):
    backend = Path(__file__).resolve().parents[1]
    root = artifact_dir().resolve()
    root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='synthetic-smoke-', dir=root) as directory:
        token = secrets.token_urlsafe(32)
        env = dict(os.environ, INVESTIGATION_DB=directory + '/synthetic.db', INVESTIGATION_ARTIFACTS=directory + '/artifacts',
                   INVESTIGATION_ADMIN_TOKEN=token, SERPAPI_API_KEY='', INVESTIGATION_DEPLOYMENT='local',
                   DEEPVERIFY_PYTHON=sys.executable, INVESTIGATION_ALLOWED_HOSTS='localhost,127.0.0.1,::1',
                   INVESTIGATION_SEARCH_UNIT_COST_USD='0', FRONTEND_URL='http://localhost:3000')
        api_port = unused_port()
        processes = []
        with open(directory + '/servers.log', 'w') as log:
            try:
                env.update(PORT=str(api_port), INVESTIGATION_HOST='127.0.0.1')
                api_command = ['bash', 'start.sh', 'api']
                api = subprocess.Popen(api_command,
                                       cwd=backend, env=env, stdout=log, stderr=log)
                processes.append(api)
                base = f'http://127.0.0.1:{api_port}'
                wait_ready(base + '/api/learning', api)
                with httpx.Client(base_url=base, timeout=10, trust_env=False) as client:
                    response = client.post('/api/investigations', json={'text': 'The fictional Aurora Observatory opened in Oslo in 2024.', 'provider': 'offline'})
                    response.raise_for_status()
                    identifier = response.json()['claim_id']
                    client.post(f'/api/investigations/{identifier}/run').raise_for_status()
                    # Restart the API while a job is queued; the separate process must recover it.
                    api.terminate(); api.wait(timeout=10)
                    api = subprocess.Popen(api_command, cwd=backend, env=env, stdout=log, stderr=log)
                    processes.append(api)
                    wait_ready(base + '/api/learning', api)
                    subprocess.run([sys.executable, '-m', 'investigation.worker', '--once'], cwd=backend, env=env, check=True, timeout=30, capture_output=True)
                    report = client.get(f'/api/investigations/{identifier}').json()
                    assert report['stage'] == 'complete'
                    evidence = report['assertions'][0]['evidence'][0]
                    assert evidence['fixture'] == 1 and evidence['source']['extraction_status'] == 'offline'
                    assert client.get('/api/admin/evaluations').status_code == 403
                    assert client.get('/api/admin/evaluations', headers={'Authorization': 'Bearer ' + token}).status_code == 200
                    assert client.get('/api/sources/' + evidence['source']['source_id']).status_code == 200
                frontend_status = 'not requested'
                if with_frontend:
                    ui_port = unused_port()
                    frontend = subprocess.Popen(['node', 'node_modules/next/dist/bin/next', 'start', '--hostname', '127.0.0.1', '--port', str(ui_port)],
                                                cwd=backend.parent / 'frontend', stdout=log, stderr=log)
                    processes.append(frontend)
                    origin = f'http://127.0.0.1:{ui_port}'
                    assert 'Inspect the evidence' in wait_ready(origin, frontend).text
                    for route in ('/review', '/evaluation', '/history'):
                        assert httpx.get(origin + route, timeout=5, trust_env=False).status_code == 200
                    frontend_status = 'production HTML routes passed; browser interactions not tested'
                log.flush()
                assert token not in Path(directory + '/servers.log').read_text()
                result = {'status': 'passed', 'kind': 'synthetic functionality only', 'api_http': 'passed',
                          'separate_worker_process': 'passed', 'queued_api_restart': 'passed', 'source_trace_api': 'passed',
                          'administrator_allow_deny': 'passed using temporary test token; does not configure the real environment',
                          'secret_log_check': 'passed', 'frontend': frontend_status,
                          'synthetic_cases': 1, 'real_benchmark_cases_added': 0, 'accuracy': 'not measured',
                          'temporary_data': 'cleaned on exit'}
            finally:
                for process in processes:
                    process.terminate()
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        process.kill(); process.wait()
    return save('synthetic-service-smoke', result)


if __name__ == '__main__':
    import json
    parser = argparse.ArgumentParser()
    parser.add_argument('--with-frontend', action='store_true', help='Requires npm run build first')
    args = parser.parse_args()
    print(json.dumps(run(args.with_frontend), indent=2))
