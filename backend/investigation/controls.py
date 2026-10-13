"""Shared SQLite admission and cost reservations. No process-local budget counters."""
import argparse
from decimal import Decimal, InvalidOperation, ROUND_CEILING
import hmac
import ipaddress
import json
import os
import time
from urllib.parse import urlsplit

from .retrieval import Unavailable
from .store import connect, uid

DEFAULTS = {
    'requests_per_minute': 300, 'submissions_per_hour': 60, 'queue': 100,
    'workers': 2, 'active_requests': 8, 'request_bytes': 65536,
    'claim_chars': 12000, 'assertions': 20, 'assertion_chars': 1500,
    'searches_per_day': 100, 'sources_per_day': 1000,
}


class LimitExceeded(Unavailable):
    def __init__(self, message, status=429):
        super().__init__(message)
        self.status = status


def money(value):
    try:
        amount = Decimal(str(value))
        if not amount.is_finite() or amount < 0 or amount > 100000:
            raise ValueError
        return int((amount * 1000000).to_integral_value(rounding=ROUND_CEILING))
    except (ValueError, InvalidOperation):
        raise ValueError('Cost bounds must be finite nonnegative USD amounts up to 100000.') from None


def environment_policy():
    values = {}
    for key, default in DEFAULTS.items():
        try:
            value = int(os.getenv('INVESTIGATION_LIMIT_' + key.upper(), str(default)))
        except ValueError:
            raise ValueError(f'INVESTIGATION_LIMIT_{key.upper()} must be a positive integer.') from None
        if not 1 <= value <= 1000000:
            raise ValueError(f'INVESTIGATION_LIMIT_{key.upper()} must be between 1 and 1000000.')
        values[key] = value
    # These are ceilings from the public schema; deployment policy can lower them.
    for key, ceiling in [('request_bytes', 1048576), ('claim_chars', 12000), ('assertions', 20), ('assertion_chars', 1500)]:
        if values[key] > ceiling:
            raise ValueError(f'INVESTIGATION_LIMIT_{key.upper()} exceeds the supported ceiling {ceiling}.')
    values['search_cost_microusd'] = money(os.getenv('INVESTIGATION_SEARCH_UNIT_COST_USD', '0'))
    values['daily_cost_microusd'] = money(os.getenv('INVESTIGATION_DAILY_COST_USD', '1'))
    return values


def policy(db):
    row = db.execute('SELECT policy_json FROM workspace_policy WHERE singleton=1').fetchone()
    if not row:
        raise ValueError('Initialize the investigation database before accepting requests.')
    return json.loads(row['policy_json'])


def initialize():
    desired = environment_policy()
    with connect() as db:
        if policy(db) != desired:
            raise ValueError('Workspace limits differ from the stored policy. Use the same environment for API/worker, or explicitly run python -m investigation.controls configure. Counters are never reset by configuration.')


def configure():
    desired = environment_policy()
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        db.execute('UPDATE workspace_policy SET policy_json=? WHERE singleton=1', (json.dumps(desired, sort_keys=True),))
    return desired


def token_equal(received, expected):
    return hmac.compare_digest(received.encode('utf-8'), expected.encode('utf-8'))


def validate_boundary():
    mode = os.getenv('INVESTIGATION_DEPLOYMENT', 'local')
    if mode not in ('local', 'private'):
        raise ValueError('INVESTIGATION_DEPLOYMENT must be local or private. Public multi-user hosting is not supported.')
    origin = urlsplit(os.getenv('FRONTEND_URL', 'http://localhost:3000'))
    if (origin.scheme not in ('http', 'https') or not origin.hostname or origin.username or origin.password
            or origin.path or origin.query or origin.fragment or '*' in origin.netloc):
        raise ValueError('FRONTEND_URL must be one exact HTTP(S) origin without a path, credentials or wildcard.')
    if mode == 'private':
        token = os.getenv('INVESTIGATION_WORKSPACE_TOKEN', '')
        if len(token) < 32 or token_equal(token, os.getenv('INVESTIGATION_ADMIN_TOKEN', '')):
            raise ValueError('Private deployment requires a distinct INVESTIGATION_WORKSPACE_TOKEN of at least 32 characters, held only by the trusted gateway.')
        if len(os.getenv('INVESTIGATION_ADMIN_TOKEN', '')) < 24:
            raise ValueError('Private deployment requires an administrator token of at least 24 characters.')
        if not os.getenv('INVESTIGATION_TRUSTED_PROXY_CIDRS') or not os.getenv('INVESTIGATION_ALLOWED_HOSTS'):
            raise ValueError('Set explicit INVESTIGATION_TRUSTED_PROXY_CIDRS and INVESTIGATION_ALLOWED_HOSTS for the private gateway.')
        for value in os.environ['INVESTIGATION_TRUSTED_PROXY_CIDRS'].split(','):
            network = ipaddress.ip_network(value.strip())
            if not network.is_private or network.prefixlen == 0:
                raise ValueError('Trusted proxies must be explicit private/loopback CIDRs.')
    hosts = os.getenv('INVESTIGATION_ALLOWED_HOSTS', 'localhost,127.0.0.1,::1').split(',')
    if any(not x.strip() or '*' in x or '/' in x for x in hosts):
        raise ValueError('Allowed hosts must be exact hostnames, never wildcards or paths.')


def authorize_scope(scope):
    headers = {k.lower(): v.decode('latin1') for k, v in scope.get('headers', [])}
    try:
        host = urlsplit('http://' + headers.get(b'host', ''))
        if host.username or host.password or host.hostname not in [x.strip() for x in os.getenv('INVESTIGATION_ALLOWED_HOSTS', 'localhost,127.0.0.1,::1').split(',')]:
            raise ValueError
        address = ipaddress.ip_address((scope.get('client') or ('', 0))[0])
    except ValueError:
        raise LimitExceeded('This endpoint is restricted to the configured local/private workspace.', 403) from None
    origin = headers.get(b'origin')
    if origin and origin != os.getenv('FRONTEND_URL', 'http://localhost:3000'):
        raise LimitExceeded('Origin is not permitted for this workspace.', 403)
    if os.getenv('INVESTIGATION_DEPLOYMENT', 'local') == 'local':
        if not address.is_loopback:
            raise LimitExceeded('Local workspace accepts loopback clients only. Configure a trusted private gateway for remote access.', 403)
    else:
        networks = [ipaddress.ip_network(x.strip()) for x in os.getenv('INVESTIGATION_TRUSTED_PROXY_CIDRS', '').split(',') if x.strip()]
        expected = os.getenv('INVESTIGATION_WORKSPACE_TOKEN', '')
        if (not any(address in network for network in networks) or len(expected) < 32
                or not token_equal(headers.get(b'x-workspace-token', ''), expected)):
            raise LimitExceeded('Private workspace gateway authorization required.', 403)


def count(db, kind, since):
    return db.execute('SELECT COUNT(*) FROM workspace_events WHERE kind=? AND occurred>?', (kind, since)).fetchone()[0]


def event(db, kind, cost=0):
    db.execute('INSERT INTO workspace_events VALUES (?,?,?,?,?)', (uid(), kind, time.time(), cost, ''))


def admit_request():
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        limits = policy(db)
        current = time.time()
        if count(db, 'request', current - 60) >= limits['requests_per_minute']:
            raise LimitExceeded('Workspace request rate limit reached. Retry later.')
        db.execute('DELETE FROM workspace_request_leases WHERE expires<?', (current,))
        if db.execute('SELECT COUNT(*) FROM workspace_request_leases').fetchone()[0] >= limits['active_requests']:
            raise LimitExceeded('Workspace concurrent request limit reached. Retry later.')
        identifier = uid()
        db.execute('INSERT INTO workspace_request_leases VALUES (?,?)', (identifier, current + 120))
        event(db, 'request')
        # Retain paid reservations; trim only expired request/submission rate events.
        db.execute("DELETE FROM workspace_events WHERE kind IN ('request','submission') AND occurred<?", (current - 3600,))
        return identifier, limits


def release_request(identifier):
    with connect() as db:
        db.execute('DELETE FROM workspace_request_leases WHERE id=?', (identifier,))


def admit_submission():
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        limits = policy(db)
        if count(db, 'submission', time.time() - 3600) >= limits['submissions_per_hour']:
            raise LimitExceeded('Workspace submission limit reached. Retry later.')
        event(db, 'submission')
        return limits


def queue_capacity(db, added=1):
    pending = db.execute("SELECT COUNT(*) FROM investigation_jobs WHERE state IN ('queued','running')").fetchone()[0]
    if pending + added > policy(db)['queue']:
        raise LimitExceeded('Workspace queue is full. Wait for existing investigations to finish.')


def search_cost(db, claim_id=None):
    value = policy(db)['search_cost_microusd']
    if claim_id:
        pilot = db.execute('SELECT r.unit_cost FROM pilot_runs r JOIN pilot_jobs j ON r.id=j.run_id WHERE j.claim_id=?', (claim_id,)).fetchone()
        if pilot:
            value = max(value, money(pilot[0]))
    if value <= 0:
        raise LimitExceeded('Live search is disabled until an administrator configures a per-search upper cost bound.', 503)
    return value


def check_external(db, kind, cost=0):
    limits = policy(db)
    since = time.time() - 86400
    if count(db, kind, since) >= limits['searches_per_day' if kind == 'search' else 'sources_per_day']:
        raise LimitExceeded('Workspace daily external-request budget reached. No request was issued.')
    if kind == 'search':
        spent = db.execute("SELECT COALESCE(SUM(cost_microusd),0) FROM workspace_events WHERE kind='search' AND occurred>?", (since,)).fetchone()[0]
        if spent + cost > limits['daily_cost_microusd']:
            raise LimitExceeded('Workspace daily provider-cost budget reached. No request was issued.')


def reserve_external(kind, claim_id=None, owner=None):
    if kind not in ('search', 'source'):
        raise ValueError('Unknown reservation kind')
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        if owner and not db.execute("SELECT 1 FROM investigation_jobs WHERE claim_id=? AND owner=? AND state='running' AND lease_until>?", (claim_id, owner, time.time())).fetchone():
            raise LimitExceeded('Worker lease lost before external request. No request was issued.')
        cost = search_cost(db, claim_id) if kind == 'search' else 0
        check_external(db, kind, cost)
        event(db, kind, cost)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Local filesystem administrator: update shared limits without resetting usage.')
    parser.add_argument('command', choices=['configure'])
    parser.parse_args()
    from .store import migrate
    migrate()
    configure()
    print('Shared workspace limits configured; existing usage reservations preserved.')
