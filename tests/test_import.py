import copy
import json
from pathlib import Path
import tempfile
import unittest

from verdictlens.__main__ import main
from verdictlens.core import DEFAULT_RUBRIC, evaluate, validate_imported_report
from verdictlens.review import ReviewStore

ROOT = Path(__file__).resolve().parents[1]
DATA = json.loads((ROOT/'examples/synthetic_pairs.json').read_text())


class ImportTests(unittest.TestCase):
    def setUp(self):
        self.report = evaluate(DATA, DEFAULT_RUBRIC, draws=20)

    def test_valid_report_and_reordered_rows_import(self):
        self.report['rows'].reverse()
        validate_imported_report(DATA, self.report)

    def test_missing_and_duplicate_rows_rejected(self):
        for mutate in (lambda rows: rows.pop(), lambda rows: rows.append(rows[0])):
            report = copy.deepcopy(self.report)
            mutate(report['rows'])
            with self.assertRaises(ValueError):
                validate_imported_report(DATA, report)

    def test_altered_labels_and_priority_rejected(self):
        for field, value in (('reference', 'tie' if self.report['rows'][0]['reference'] != 'tie' else 'a'),
                             ('base', 'b' if self.report['rows'][0]['base'] != 'b' else 'a'),
                             ('review_priority', 99)):
            report = copy.deepcopy(self.report)
            report['rows'][0][field] = value
            with self.assertRaises(ValueError):
                validate_imported_report(DATA, report)

    def test_altered_aggregates_and_identity_rejected(self):
        for field in ('summary', 'run_id'):
            report = copy.deepcopy(self.report)
            if field == 'summary':
                report[field]['agreement'] = 0
            else:
                report[field] = 'forged'
            with self.assertRaises(ValueError):
                validate_imported_report(DATA, report)

    def test_import_is_idempotent_but_cannot_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ReviewStore(Path(tmp)/'review.sqlite')
            self.assertEqual(store.import_run(DATA, self.report)['status'], 'imported')
            self.assertEqual(store.import_run(DATA, self.report)['status'], 'already_present')
            altered = copy.deepcopy(self.report)
            altered['execution'] = {'note': 'different wrapper metadata'}
            with self.assertRaisesRegex(ValueError, 'immutable'):
                store.import_run(DATA, altered)
            store.close()

    def test_cli_import_and_review_assignment(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp)/'data.json'
            report = Path(tmp)/'report.json'
            db = Path(tmp)/'review.sqlite'
            data.write_text(json.dumps(DATA))
            report.write_text(json.dumps(self.report))
            self.assertEqual(main(['import-report', '--data', str(data), '--report',
                                   str(report), '--database', str(db)]), 0)
            store = ReviewStore(db)
            self.assertIsNotNone(store.assignment(self.report['run_id'], 'reviewer-one'))
            store.close()


if __name__ == '__main__':
    unittest.main()
