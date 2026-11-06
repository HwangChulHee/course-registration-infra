#!/usr/bin/env python3
"""Real Compose HTTP + SQL verification; adds uniquely named test users, never resets DB."""
import concurrent.futures
import json
import os
import secrets
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = os.environ.get('VALIDATION_URL', 'http://127.0.0.1:8080')

def api(method, path, token=None, payload=None):
    headers = {'Content-Type': 'application/json'}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    request = urllib.request.Request(BASE + '/api/v1' + path, headers=headers, method=method,
                                    data=None if payload is None else json.dumps(payload).encode())
    try:
        response = urllib.request.urlopen(request, timeout=30)
    except urllib.error.HTTPError as error:
        response = error
    with response:
        content = response.read()
        return response.code, json.loads(content) if content else None


def sql(query):
    return subprocess.check_output(['docker', 'compose', 'exec', '-T', 'db', 'sh', '-c',
        'exec psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tA -v ON_ERROR_STOP=1 -c "$1"', 'sh', query], cwd=ROOT, text=True).strip()


def check_invariants():
    assert sql('SELECT count(*) FROM courses c WHERE enrolled_count <> reserved_count + (SELECT count(*) FROM enrollments e WHERE e.course_id=c.id) OR enrolled_count>capacity') == '0'
    assert sql('SELECT count(*) FROM (SELECT user_id,course_id FROM enrollments GROUP BY user_id,course_id HAVING count(*)>1) x') == '0'


def signup():
    email = 'validation-' + secrets.token_hex(8) + '@example.test'
    password = secrets.token_urlsafe(18)
    assert api('POST', '/auth/signup', payload={'name': '통합검증', 'email': email, 'password': password})[0] == 201
    status, data = api('POST', '/auth/login', payload={'email': email, 'password': password})
    assert status == 200
    return email, password, data['token']


def main():
    results = {}
    with urllib.request.urlopen(BASE, timeout=20) as response:
        assert response.code == 200 and '한국대학교' in response.read().decode()
    with urllib.request.urlopen(BASE + '/actuator/health', timeout=20) as response:
        assert json.load(response)['status'] == 'UP'
    assert api('GET', '/courses')[0] == 401
    users = [signup() for _ in range(20)]
    token = users[0][2]
    assert api('PUT', '/local/registration/window', token, {'open': False})[0] == 200
    assert api('POST', '/enrollments', token, {'courseId': 'course-2'})[1]['code'] == 'NOT_OPEN'
    assert api('PUT', '/local/registration/window', token, {'open': True})[0] == 200
    status, courses = api('GET', '/courses', token)
    assert status == 200 and len(courses) == 24
    course = next(c for c in courses if c['id'] == 'course-2')
    assert course['capacity'] - course['enrolledCount'] == 1, 'Final-seat check needs the seeded vacancy; use a fresh project volume or cancel prior test enrollment.'
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        outcomes = list(executor.map(lambda u: api('POST', '/enrollments', u[2], {'courseId': 'course-2'}), users))
    successes = [i for i, result in enumerate(outcomes) if result[0] == 201]
    assert len(successes) == 1
    assert sum(status == 409 and body['code'] == 'FULL' for status, body in outcomes) == 19
    winner = successes[0]
    winner_token = users[winner][2]
    enrollment = outcomes[winner][1]
    assert api('POST', '/enrollments', winner_token, {'courseId': 'course-2'})[1]['code'] == 'DUPLICATE'
    other = users[(winner + 1) % len(users)][2]
    assert api('DELETE', '/enrollments/' + enrollment['id'], other)[0] == 404
    check_invariants()
    results['final_seat'] = {'requests': 20, 'created': 1, 'full': 19, 'count': int(sql("SELECT enrolled_count FROM courses WHERE id='course-2'"))}
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        canceled = list(executor.map(lambda _: api('DELETE', '/enrollments/' + enrollment['id'], winner_token)[0], range(20)))
    assert canceled == [204] * 20
    assert sql("SELECT enrolled_count FROM courses WHERE id='course-2'") == '39'
    results['cancel_race'] = {'requests': 20, 'no_content': 20, 'count_after': 39}
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        duplicates = list(executor.map(lambda _: api('POST', '/enrollments', token, {'courseId': 'course-3'}), range(20)))
    assert sum(s == 201 for s, _ in duplicates) == 1
    assert sum(s == 409 and b['code'] == 'DUPLICATE' for s, b in duplicates) == 19
    duplicate_id = next(b['id'] for s, b in duplicates if s == 201)
    assert api('DELETE', '/enrollments/' + duplicate_id, token)[0] == 204
    results['duplicate_race'] = {'requests': 20, 'created': 1, 'duplicate': 19}
    # A surviving enrollment demonstrates actual persisted user data after process restarts.
    status, persisted = api('POST', '/enrollments', token, {'courseId': 'course-4'})
    assert status == 201
    before_courses = api('GET', '/courses', token)[1]
    before_mine = api('GET', '/enrollments/me', token)[1]
    before_counts = sql('SELECT (SELECT count(*) FROM users), (SELECT count(*) FROM courses), (SELECT count(*) FROM enrollments), (SELECT count(*) FROM flyway_schema_history)')
    check_invariants()
    subprocess.run(['docker', 'compose', 'restart'], cwd=ROOT, check=True)
    for attempt in range(90):
        try:
            with urllib.request.urlopen(BASE + '/actuator/health', timeout=2) as response:
                if json.load(response)['status'] == 'UP':
                    break
        except (OSError, ValueError):
            pass
        time.sleep(1)
    else:
        raise AssertionError('Compose health did not recover after restart')
    assert api('GET', '/courses', token)[1] == before_courses
    assert api('GET', '/enrollments/me', token)[1] == before_mine
    assert sql('SELECT (SELECT count(*) FROM users), (SELECT count(*) FROM courses), (SELECT count(*) FROM enrollments), (SELECT count(*) FROM flyway_schema_history)') == before_counts
    assert api('POST', '/auth/logout', token)[0] == 204
    assert api('GET', '/auth/me', token)[0] == 401
    status, relogin = api('POST', '/auth/login', payload={'email': users[0][0], 'password': users[0][1]})
    assert status == 200
    assert api('GET', '/enrollments/me', relogin['token'])[1] == before_mine
    check_invariants()
    results['persistence'] = {'restart': 'PASS', 'relogin': 'PASS', 'counts_before_after': before_counts, 'course_and_enrollment_payloads_equal': True, 'seed_duplicates': 0}
    # Remove only this script's surviving enrollment; retain accounts as evidence without credentials.
    assert api('DELETE', '/enrollments/' + persisted['id'], relogin['token'])[0] == 204
    assert api('POST', '/auth/logout', relogin['token'])[0] == 204
    results['http'] = {'frontend': 200, 'health': 'UP', 'courses': 24, 'unauthenticated': 401, 'cross_user_cancel': 404, 'closed_window': 'NOT_OPEN'}
    results['db_invariants'] = 'PASS'
    output = ROOT / '.validation' / 'live-results.json'
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(results, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
