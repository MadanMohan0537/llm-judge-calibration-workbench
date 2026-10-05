"""Synthetic annotations only, not real human-preference data."""
import json
from pathlib import Path
from verdictlens.core import DEFAULT_RUBRIC


def main():
    pairs = []
    for i in range(24):
        category = ['support', 'research', 'product'][i % 3]
        good = 'verify source evidence uncertain'
        bad = 'The answer is certainly correct. Nothing needs to be checked at all. This explanation is polished and complete.'
        if i % 4 == 0:
            a, b, votes = bad, good, ['b', 'b', 'b']
        elif i % 4 == 1:
            a, b, votes = good, bad, ['a', 'a', 'b']
        elif i % 4 == 2:
            a, b, votes = 'verify source', 'uncertain evidence', ['tie', 'tie', 'a']
        else:
            a, b, votes = 'verify source evidence', 'source evidence', ['a', 'b', 'tie']
        pairs.append({'id': f'pair-{i+1:02}', 'category': category, 'split': 'development' if i < 16 else 'holdout', 'prompt': f'Synthetic {category} comparison {i+1}: which answer better communicates evidence limits?', 'a': a, 'b': b, 'family_a': 'fixture-alpha', 'family_b': 'fixture-beta', 'human_votes': votes})
    root = Path(__file__).parent
    (root/'synthetic_pairs.json').write_text(json.dumps({'schema_version': 1, 'provenance': 'Generated fixture annotations; no recruited human raters. Repeated templates limit generalization.', 'pairs': pairs}, indent=2)+'\n')
    (root/'rubric.json').write_text(json.dumps(DEFAULT_RUBRIC, indent=2)+'\n')


if __name__ == '__main__':
    main()
