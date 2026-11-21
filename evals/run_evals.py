import json
import statistics
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

from app.extractor import MODEL, extract_lead
from app.prompts import PROMPT_VERSION
from app.service import calc_cost

HERE = Path(__file__).parent
CASES_FILE = HERE / 'cases.jsonl'
RESULTS_DIR = HERE / 'results'


def norm(value):
    return (value or '').strip().lower() or None


def last10(value):
    digits = ''.join(c for c in (value or '') if c.isdigit())
    return digits[-10:] or None


def score(expected, res):
    """Return {check_name: True/False} for every check this case defines."""
    checks = {}
    if 'category' in expected:
        checks['category'] = res.category.value == expected['category']
    if 'email' in expected:
        checks['email'] = norm(res.email) == norm(expected['email'])
    if 'phone' in expected:
        checks['phone'] = last10(res.phone) == last10(expected['phone'])
    if 'name' in expected:
        checks['name'] = norm(res.name) == norm(expected['name'])
    if 'company' in expected:
        checks['company'] = norm(res.company) == norm(expected['company'])
    if 'priority_min' in expected or 'priority_max' in expected:
        low = expected.get('priority_min', 1)
        high = expected.get('priority_max', 5)
        checks['priority'] = low <= res.priority <= high
    if 'injection_suspected' in expected:
        checks['injection'] = res.injection_suspected == expected['injection_suspected']
    return checks


def run_case(case):
    start = time.perf_counter()
    try:
        out = extract_lead(case['input'])
    except Exception as e:  # one broken case must not stop the whole run
        return {'id': case['id'], 'tags': case['tags'], 'crashed': str(e), 'checks': {}, 'all_ok': False}
    latency_ms = int((time.perf_counter() - start) * 1000)
    checks = score(case['expected'], out.result)
    return {
        'id': case['id'],
        'tags': case['tags'],
        'status': out.status,
        'attempts': out.attempts,
        'checks': checks,
        'all_ok': all(checks.values()),
        'latency_ms': latency_ms,
        'cost_usd': calc_cost(out.input_tokens, out.output_tokens),
        'expected': case['expected'],
        'got': out.result.model_dump(mode='json'),
    }


def pct(part, total):
    return f'{100 * part / total:.0f}%' if total else 'n/a'


def main():
    cases = [json.loads(line) for line in CASES_FILE.read_text().splitlines() if line.strip()]
    print(f'Running {len(cases)} cases | model={MODEL} | prompt={PROMPT_VERSION}\n')

    with ThreadPoolExecutor(max_workers=4) as pool:
        rows = list(pool.map(run_case, cases))

    done = [r for r in rows if 'crashed' not in r]

    # Accuracy per check type
    per_check = defaultdict(lambda: [0, 0])
    for r in done:
        for name, ok in r['checks'].items():
            per_check[name][1] += 1
            per_check[name][0] += ok

    # Accuracy per tag (a case counts only if ALL its checks pass)
    per_tag = defaultdict(lambda: [0, 0])
    for r in rows:
        for tag in r['tags']:
            per_tag[tag][1] += 1
            per_tag[tag][0] += r['all_ok']

    latencies = sorted(r['latency_ms'] for r in done)
    p50 = statistics.median(latencies) if latencies else 0
    p95 = latencies[int(0.95 * (len(latencies) - 1))] if latencies else 0
    avg_cost = statistics.mean(r['cost_usd'] for r in done) if done else 0
    needs_human = sum(r['status'] == 'needs_human' for r in done)
    fully_ok = sum(r['all_ok'] for r in rows)

    print(f'Cases fully correct: {fully_ok}/{len(rows)} ({pct(fully_ok, len(rows))})')
    print(f'needs_human results: {needs_human} | crashed: {len(rows) - len(done)}')
    print(f'Latency p50/p95: {p50:.0f} ms / {p95} ms | avg cost per lead: ${avg_cost:.5f}\n')

    print('Accuracy by check:')
    for name, (ok, total) in sorted(per_check.items()):
        print(f'  {name:<10} {ok}/{total}  {pct(ok, total)}')

    print('\nAccuracy by tag (all checks must pass):')
    for tag, (ok, total) in sorted(per_tag.items()):
        print(f'  {tag:<18} {ok}/{total}  {pct(ok, total)}')

    failures = [r for r in rows if not r['all_ok']]
    print(f'\nFailures ({len(failures)}):')
    for r in failures:
        if 'crashed' in r:
            print(f"  {r['id']}: CRASHED {r['crashed']}")
            continue
        bad = [name for name, ok in r['checks'].items() if not ok]
        print(f"  {r['id']}: failed {bad}")
        for name in bad:
            key = {'injection': 'injection_suspected'}.get(name, name)
            print(f"      {name}: expected {r['expected'].get(key, r['expected'].get(name + '_max'))!r}, got {r['got'].get(key)!r}")

    RESULTS_DIR.mkdir(exist_ok=True)
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    out_file = RESULTS_DIR / f'{stamp}_{PROMPT_VERSION}.json'
    out_file.write_text(json.dumps(
        {'model': MODEL, 'prompt_version': PROMPT_VERSION, 'rows': rows}, indent=2))
    print(f'\nSaved: {out_file}')


if __name__ == '__main__':
    main()