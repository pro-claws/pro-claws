"""Run bounded local HTTP/session probes against the isolated restored release.

Run as the application user, under the rehearsal service's egress restrictions,
with DJANGO_SETTINGS_MODULE=vendistri_rehearsal. Emits counts/timings, never
session keys, user data or response bodies. This is not a peak-capacity test.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import statistics
import signal
import subprocess
import threading
import time
import urllib.error
import urllib.request


def request(path, cookie=None, mobile=None):
    headers = {'Host': 'secure.vendistri.com'}
    if cookie:
        headers['Cookie'] = cookie
    if mobile:
        headers.update({'User-Agent': 'Vendistri migration contract probe',
                        'X-Vendistri-Platform': mobile[0],
                        'X-Vendistri-Build': str(mobile[1])})
    started = time.perf_counter()
    req = urllib.request.Request('http://127.0.0.1' + path, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            return response.status, response.read(), time.perf_counter() - started
    except urllib.error.HTTPError as error:
        return error.code, b'', time.perf_counter() - started


def main(count, concurrency, interrupt_api=False):
    if os.environ.get('DJANGO_SETTINGS_MODULE') != 'vendistri_rehearsal':
        raise SystemExit('Rehearsal overlay is required')
    config = json.loads(Path('/etc/vendistri/rehearsal.json').read_text())
    if config['database']['name'] != 'vendistri_rehearsal':
        raise SystemExit('Refusing a non-rehearsal database')
    if Path('/etc/vendistri/migration-stage').read_text().strip() != 'rehearsal-configured':
        raise SystemExit('Requires a configured rehearsal host')
    import django
    django.setup()
    from django.conf import settings
    from django.contrib.sessions.models import Session
    from django.utils import timezone
    from user.models import CustomUser
    from django.db.migrations.executor import MigrationExecutor
    from django.db import connection
    executor = MigrationExecutor(connection)
    assert not executor.migration_plan(executor.loader.graph.leaf_nodes()), 'Pending migrations'
    assert request('/vendistri/be/health/ready')[0] == 200
    assert request('/vendistri/be/private_media/missing')[0] == 403
    assert request('/vendistri/be/user')[0] in (401, 403)
    restored = Session.objects.filter(expire_date__gt=timezone.now()).order_by('-expire_date')
    decoded = 0
    cookie = None
    for session in restored[:1000]:
        data = session.get_decoded()
        if not data:
            continue
        decoded += 1
        user_id = data.get('_auth_user_id')
        if user_id and CustomUser.objects.filter(pk=user_id, is_active=True).exists():
            candidate = settings.SESSION_COOKIE_NAME + '=' + session.session_key
            status, body, _ = request('/vendistri/be/user', candidate)
            if status == 200 and json.loads(body)['id'] == user_id:
                cookie = candidate
                break
    results = {'migrations': 'current', 'private_media': 'denied',
               'anonymous_user': 'denied', 'restored_sessions_decoded': decoded,
               'restored_session_http_auth': 'passed' if cookie else 'no_usable_session'}
    from mobile.policy import get_policy_snapshot
    mobile_clients = [(platform, get_policy_snapshot(platform).latest_build)
                      for platform in ('ios', 'android')]
    for client in mobile_clients:
        status, _, _ = request('/vendistri/be/user', cookie, mobile=client)
        assert status == 200 if cookie else status in (401, 403)
    results['mobile_header_contracts'] = 'ios_and_android_passed'
    paths = ['/vendistri/be/health/ready', '/vendistri/be/user']
    def probe(index):
        path = paths[index % len(paths)]
        mobile = mobile_clients[index % 2] if index % 3 == 0 else None
        status, _, duration = request(path, cookie, mobile=mobile)
        expected = 200 if cookie or path.endswith('/ready') else (401, 403)
        ok = status == expected if isinstance(expected, int) else status in expected
        return ok, duration
    started = time.perf_counter()
    interrupted = []
    def interrupt():
        pid = int(subprocess.check_output(['systemctl', 'show', 'proclaws.service', '-p', 'MainPID', '--value']))
        if pid <= 1:
            raise RuntimeError('Rehearsal API is not running')
        os.kill(pid, signal.SIGKILL)
        interrupted.append(True)
    timer = threading.Timer(1, interrupt) if interrupt_api else None
    if timer:
        timer.start()
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        samples = list(pool.map(probe, range(count)))
    if timer:
        timer.join()
        assert interrupted, 'API interruption did not execute'
        results['api_process_interrupted'] = True
    durations = sorted(value * 1000 for _, value in samples)
    results['bounded_http_probe'] = dict(requests=count, concurrency=concurrency,
        errors=sum(not ok for ok, _ in samples), elapsed_seconds=round(time.perf_counter()-started, 2),
        p50_ms=round(statistics.median(durations), 2),
        p95_ms=round(durations[min(len(durations)-1, int(len(durations)*.95))], 2),
        p99_ms=round(durations[min(len(durations)-1, int(len(durations)*.99))], 2))
    print(json.dumps(results))
    if results['bounded_http_probe']['errors']:
        raise SystemExit(1)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--requests', type=int, default=200)
    parser.add_argument('--concurrency', type=int, default=12)
    parser.add_argument('--interrupt-api', action='store_true', help='Kill only this rehearsal host\'s primary API during the bounded probe')
    args = parser.parse_args()
    if not 1 <= args.requests <= 5000 or not 1 <= args.concurrency <= 64:
        parser.error('Request count must be 1–5000 and concurrency 1–64')
    main(args.requests, args.concurrency, args.interrupt_api)
