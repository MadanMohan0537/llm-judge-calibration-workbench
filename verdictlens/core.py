"""Validated pair data, judge agreement and controlled bias probes."""
from collections import Counter
import hashlib
import json
import math
import random

LABELS = ('a', 'b', 'tie')
DEFAULT_RUBRIC = {'id': 'evidence-v1', 'instructions': 'Prefer correct, relevant, supported answers; ignore length and position.', 'terms': {'verify': 1, 'source': 1, 'uncertain': 1, 'evidence': 1}, 'tie_margin': 0}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def validate_dataset(data):
    if not isinstance(data, dict) or data.get('schema_version') != 1:
        raise ValueError('dataset schema_version must be 1')
    pairs = data.get('pairs')
    if not isinstance(pairs, list) or not 1 <= len(pairs) <= 500:
        raise ValueError('provide 1–500 pairs')
    seen = set()
    for p in pairs:
        if not isinstance(p, dict):
            raise ValueError('each pair must be an object')
        for key in ('id', 'category', 'prompt', 'a', 'b', 'family_a', 'family_b'):
            if not isinstance(p.get(key), str) or not p[key].strip() or len(p[key]) > 20000:
                raise ValueError(f'invalid {key}')
        if p['id'] in seen:
            raise ValueError('duplicate pair id')
        seen.add(p['id'])
        if p.get('split') not in ('development', 'holdout'):
            raise ValueError('explicit development or holdout split required')
        votes = p.get('human_votes')
        if not isinstance(votes, list) or len(votes) < 2 or any(v not in LABELS for v in votes):
            raise ValueError('at least two reference votes required, using a/b/tie')
    return data


def validate_rubric(r):
    if not isinstance(r, dict) or set(r) != {'id', 'instructions', 'terms', 'tie_margin'}:
        raise ValueError('rubric requires exactly id, instructions, terms, tie_margin')
    for key in ('id', 'instructions'):
        if not isinstance(r[key], str) or not r[key].strip() or len(r[key]) > 4000:
            raise ValueError('invalid rubric text')
    terms = r['terms']
    if not isinstance(terms, dict) or len(terms) > 100:
        raise ValueError('terms must be a small object')
    for key, value in list(terms.items()) + [('tie_margin', r['tie_margin'])]:
        if not isinstance(key, str) or not key.strip() or isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError('rubric weights must be finite numbers')
    if r['tie_margin'] < 0:
        raise ValueError('tie_margin must be nonnegative')
    return r


def reference(votes):
    label, count = Counter(votes).most_common(1)[0]
    return label if count > len(votes) / 2 else 'tie'


def kappa(left, right):
    if not left or len(left) != len(right) or any(v not in LABELS for v in left + right):
        raise ValueError('nonempty aligned categorical labels required')
    n = len(left)
    observed = sum(a == b for a, b in zip(left, right)) / n
    a, b = Counter(left), Counter(right)
    expected = sum(a[x] * b[x] for x in LABELS) / n**2
    return None if math.isclose(expected, 1) else (observed - expected) / (1 - expected)


def stats(rows, seed=17, draws=500):
    if not rows:
        return {'n': 0, 'agreement': None, 'kappa': None, 'agreement_interval': None, 'kappa_interval': None}
    if not 20 <= draws <= 5000:
        raise ValueError('bootstrap draws must be 20–5000')
    left = [r['reference'] for r in rows]
    right = [r['base'] for r in rows]
    rng = random.Random(seed)
    agreements, kappas = [], []
    for _ in range(draws):
        sample = [rng.randrange(len(rows)) for _ in rows]
        a, b = [left[i] for i in sample], [right[i] for i in sample]
        agreements.append(sum(x == y for x, y in zip(a, b)) / len(a))
        value = kappa(a, b)
        if value is not None:
            kappas.append(value)
    def interval(values):
        values = sorted(values)
        return [values[int((len(values)-1)*.025)], values[int((len(values)-1)*.975)]] if values else None
    return {'n': len(rows), 'agreement': sum(a == b for a, b in zip(left, right))/len(rows), 'kappa': kappa(left, right), 'agreement_interval': interval(agreements), 'kappa_interval': interval(kappas), 'defined_kappa_draws': len(kappas), 'bootstrap_draws': draws}


def summarize(rows, seed=17, draws=500):
    result = stats(rows, seed, draws)
    result.update({
        'order_flip_rate': sum(r['base'] != r['swapped'] for r in rows)/len(rows) if rows else None,
        'padding_flip_rate': sum(r['base'] != r['padded_a'] for r in rows)/len(rows) if rows else None,
        'padding_a_win_delta': (sum(r['padded_a'] == 'a' for r in rows)
                                - sum(r['base'] == 'a' for r in rows))/len(rows) if rows else None,
    })
    return result


def mock_judge(kind, a, b, rubric):
    if kind == 'mock-length':
        scores = [len(a.split()), len(b.split())]
    elif kind == 'mock-evidence':
        scores = [sum(weight * text.lower().split().count(term.lower()) for term, weight in rubric['terms'].items()) for text in (a, b)]
    else:
        raise ValueError('unknown mock judge')
    delta = scores[0] - scores[1]
    return 'tie' if abs(delta) <= rubric['tie_margin'] else ('a' if delta > 0 else 'b')


def evaluate(data, rubric, kind='mock-evidence', judge=None, seed=17, draws=500):
    validate_dataset(data)
    validate_rubric(rubric)
    call = judge or (lambda a, b, prompt: mock_judge(kind, a, b, rubric))
    rows = []
    for p in sorted(data['pairs'], key=lambda p: p['id']):
        def invoke(a, b):
            result = call(a, b, p['prompt'])
            if result not in LABELS:
                raise ValueError('judge returned invalid label; run aborted')
            return result
        base = invoke(p['a'], p['b'])
        swapped = invoke(p['b'], p['a'])
        swapped = {'a': 'b', 'b': 'a', 'tie': 'tie'}[swapped]
        padded = invoke(p['a'] + ' ' + 'Additional wording without additional information. ' * 12, p['b'])
        rows.append({'id': p['id'], 'category': p['category'], 'split': p['split'], 'reference': reference(p['human_votes']), 'base': base, 'swapped': swapped, 'padded_a': padded, 'reference_disputed': len(set(p['human_votes'])) > 1, 'review_priority': int(base != reference(p['human_votes']))*4 + int(base != swapped)*2 + int(len(set(p['human_votes'])) > 1), 'family_a': p['family_a'], 'family_b': p['family_b']})
    splits = {s: summarize([r for r in rows if r['split'] == s], seed, draws) for s in ('development', 'holdout')}
    categories = {c: summarize([r for r in rows if r['category'] == c], seed, draws) for c in sorted({r['category'] for r in rows})}
    # First two raters only: descriptive agreement, not a universal human ceiling.
    human_kappa = kappa([p['human_votes'][0] for p in data['pairs']], [p['human_votes'][1] for p in data['pairs']])
    report = {'schema_version': 1, 'dataset_sha256': digest(data), 'rubric_sha256': digest(rubric), 'rubric': rubric, 'judge': kind, 'seed': seed, 'summary': summarize(rows, seed, draws), 'splits': splits, 'categories': categories, 'reference_rater_pair_kappa': human_kappa, 'rows': rows, 'limitations': ['Synthetic labels are fixture annotations, not recruited human judgments.', 'Bootstrap intervals are descriptive; correlated/reused prompts violate independent-pair assumptions.', 'Holdout is excluded from review queue, but repeated inspection can still overfit it.', 'Family fields are provenance only; no family-bias inference from synthetic mocks.']}
    report['run_id'] = digest(report)
    return report


def validate_imported_report(data, report):
    """Validate a persisted evaluation before it can enter blinded review."""
    validate_dataset(data)
    if not isinstance(report, dict) or report.get('schema_version') != 1:
        raise ValueError('report schema_version must be 1')
    if report.get('dataset_sha256') != digest(data):
        raise ValueError('report dataset hash does not match supplied dataset bytes')
    rubric = validate_rubric(report.get('rubric'))
    if report.get('rubric_sha256') != digest(rubric):
        raise ValueError('report rubric hash does not match embedded rubric')
    if not isinstance(report.get('judge'), str) or not report['judge'].strip():
        raise ValueError('report judge identity must be nonempty')
    if isinstance(report.get('seed'), bool) or not isinstance(report.get('seed'), int):
        raise ValueError('report seed must be an integer')
    rows = report.get('rows')
    if not isinstance(rows, list):
        raise ValueError('report rows must be a list')
    by_id = {}
    required = {'id', 'category', 'split', 'reference', 'base', 'swapped', 'padded_a',
                'reference_disputed', 'review_priority', 'family_a', 'family_b'}
    for row in rows:
        if not isinstance(row, dict) or set(row) != required:
            raise ValueError('each report row must have the exact supported fields')
        if row['id'] in by_id:
            raise ValueError('report contains duplicate pair id')
        if any(row[field] not in LABELS for field in ('reference', 'base', 'swapped', 'padded_a')):
            raise ValueError('report labels must use a/b/tie')
        by_id[row['id']] = row
    pairs = {p['id']: p for p in data['pairs']}
    if set(by_id) != set(pairs):
        raise ValueError('report must cover every dataset pair exactly once')
    for pair_id, pair in pairs.items():
        row = by_id[pair_id]
        expected_reference = reference(pair['human_votes'])
        expected_priority = (int(row['base'] != expected_reference)*4
                             + int(row['base'] != row['swapped'])*2
                             + int(len(set(pair['human_votes'])) > 1))
        expected = {'category': pair['category'], 'split': pair['split'],
                    'reference': expected_reference,
                    'reference_disputed': len(set(pair['human_votes'])) > 1,
                    'review_priority': expected_priority,
                    'family_a': pair['family_a'], 'family_b': pair['family_b']}
        if any(row[key] != value for key, value in expected.items()):
            raise ValueError(f'{pair_id}: report row conflicts with dataset or derived evidence')
    ordered = [by_id[pair_id] for pair_id in sorted(by_id)]
    draws = report.get('summary', {}).get('bootstrap_draws')
    if isinstance(draws, bool) or not isinstance(draws, int):
        raise ValueError('report bootstrap draw count is missing')
    expected_summary = summarize(ordered, report['seed'], draws)
    expected_splits = {s: summarize([r for r in ordered if r['split'] == s], report['seed'], draws)
                       for s in ('development', 'holdout')}
    expected_categories = {c: summarize([r for r in ordered if r['category'] == c],
                                        report['seed'], draws)
                           for c in sorted({r['category'] for r in ordered})}
    human_kappa = kappa([p['human_votes'][0] for p in data['pairs']],
                        [p['human_votes'][1] for p in data['pairs']])
    if (report.get('summary') != expected_summary or report.get('splits') != expected_splits
            or report.get('categories') != expected_categories
            or report.get('reference_rater_pair_kappa') != human_kappa):
        raise ValueError('report aggregates do not reconcile with row evidence')
    identity = {key: value for key, value in report.items() if key not in ('run_id', 'execution')}
    identity['rows'] = sorted(identity['rows'], key=lambda row: row['id'])
    if report.get('run_id') != digest(identity):
        raise ValueError('report run_id does not match immutable evidence')
    return report


def review_queue(data, report):
    if digest(data) != report['dataset_sha256']:
        raise ValueError('dataset does not match run')
    lookup = {p['id']: p for p in data['pairs']}
    return [lookup[r['id']] for r in sorted(report['rows'], key=lambda r: (-r['review_priority'], r['id'])) if r['split'] == 'development' and r['review_priority'] > 0]

