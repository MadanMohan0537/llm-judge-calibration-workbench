# VerdictLens

**Find out when an AI judge agrees with reference reviewers—and when its preferences change for the wrong reasons.**

VerdictLens is a local calibration workbench for pairwise answer judges. It measures agreement and Cohen's kappa, runs order-swap and length-padding probes, keeps development and holdout results separate, and queues disputed cases for blinded adjudication.

**Status:** working portfolio MVP. The bundled dataset has 24 synthetic pairs and generated reference annotations. The two demo judges are deterministic heuristics, not LLMs. An optional adapter calls a model you already have installed in local Ollama; no real-model benchmark is claimed.

## What works today

| Workflow | Implemented behavior |
| --- | --- |
| Compare judges | Evidence-term heuristic, deliberately length-biased heuristic, optional local Ollama adapter |
| Measure agreement | Agreement rate, unweighted categorical kappa, category/split breakdowns |
| Inspect uncertainty | Seeded pair-bootstrap percentile intervals; undefined kappa shown explicitly |
| Probe position preference | Swap answers, remap the decision to original identities, report preference flips |
| Probe length preference | Append fixed filler to answer A and report flip rate and A-win-rate change |
| Edit a rubric | Edit versioned JSON in the workbench; rerun both demo judges and compare with the previous run |
| Review disagreements | Prioritized development-only queue, blinded order per reviewer, separate independent votes |
| Preserve evidence | Dataset/rubric hashes, run snapshots in SQLite, JSON reports and vote exports |
| Import real runs | Reconcile a CLI report against its dataset, then save an immutable review snapshot |

The original planning idea is **AI PM Project Lab #2, Judge Calibration Lab**. VerdictLens is the product name. [project.json](project.json) preserves this traceability so the idea is not built twice.

## Start in two minutes

Requirements: **Python 3.11+**. The core and workbench use only the Python standard library. No API key, paid service, Node installation or cloud account is needed.

```bash
git clone https://github.com/MadanMohan0537/verdictlens.git
cd verdictlens
python -m unittest discover -s tests -v
python -m verdictlens serve --data examples/synthetic_pairs.json
```

Open **http://127.0.0.1:8788**. Leave the terminal running.

1. Click **Compare two judges** and inspect the agreement, kappa and bias results.
2. Expand the split/category evidence. The holdout contains eight pairs and is excluded from review.
3. Edit the rubric's terms or tie margin, rerun, and compare the previous result.
4. Enter a reviewer pseudonym and load a blinded development pair.
5. Vote A, B or tie. Ask another independent reviewer to use a different pseudonym without seeing the earlier vote.
6. Export the calibration report and review votes. Close the server with Ctrl+C.

The workbench writes `verdictlens.sqlite` locally; it is gitignored. SQLite contains raw pair text, run reports, vote records and a local blinding secret. Keep it private when using your own data. Reviewer pseudonyms are keyed hashes in exports, not anonymous identities.

## CLI reports

```bash
python -m verdictlens evaluate --data examples/synthetic_pairs.json --judge mock-evidence --out report.json
python -m verdictlens evaluate --data examples/synthetic_pairs.json --judge mock-length --out length-report.json
python -m verdictlens evaluate --data examples/synthetic_pairs.json --rubric examples/rubric.json --out revised-report.json
python -m verdictlens import-report --data examples/synthetic_pairs.json --report report.json --database verdictlens.sqlite
```

Optional arguments: `--seed 17` and `--draws 500` (20–5,000 bootstrap draws). Exit code **0** means analysis completed; **2** means invalid input or execution failure. There is no release pass/block policy.

### Use a real local judge

Install Ollama separately from its official source and install a model appropriate to your hardware. Then use its exact installed model tag:

```bash
python -m verdictlens evaluate --data examples/synthetic_pairs.json --judge ollama --model YOUR_INSTALLED_MODEL --out local-model-report.json
```

This makes three sequential calls per pair to `http://127.0.0.1:11434/api/chat`: original, swapped and padded. Temperature is zero and structured output requests `a`, `b` or `tie`. Invalid output, transport failure or timeout aborts the run; there is no silent mock fallback. Hardware execution remains nondeterministic even at zero temperature. The adapter contract is tested with mocked transport; a live model was not executed for this release.

The CLI includes call counts and wall-clock duration, but does **not** measure electricity, hardware cost or cost per 1,000 judgments.

### Import a CLI run for adjudication

`import-report` validates a report before it can enter the blinded review store. It
requires exact dataset and rubric hashes, complete and unique pair coverage, supported
labels, dataset-consistent metadata and reference votes, reconciled summary/split/category
statistics, and a matching immutable run identity. Row order may differ. Execution timing
metadata is retained but is not part of the deterministic run identity.

The first valid import reports `imported` and the number of queued development pairs.
Re-importing identical evidence is idempotent. An existing run can never be overwritten
with different content. Import validation establishes internal consistency, not that an
upstream model actually ran or that human labels are trustworthy.

## Bring your own reference pairs

Use the schema illustrated in [examples/synthetic_pairs.json](examples/synthetic_pairs.json):

```json
{
  "schema_version": 1,
  "provenance": "Document source, consent/license and labeling procedure here",
  "pairs": [{
    "id": "example-001",
    "category": "support",
    "split": "development",
    "prompt": "Which answer better addresses the question?",
    "a": "Answer A",
    "b": "Answer B",
    "family_a": "documented-model-family",
    "family_b": "another-model-family",
    "human_votes": ["a", "a", "tie"]
  }]
}
```

Required: unique IDs, nonempty text/family/category fields, an explicit `development` or `holdout` split, and at least two votes using `a`, `b`, `tie`. There are limits of 500 pairs and 20,000 characters per text field. Use only data you are permitted to process. Avoid publishing private conversations or review databases.

Reference aggregation uses a **strict majority**; no majority becomes tie. That conflates inconclusive votes with explicit tie and must be considered when interpreting results. A separate first-two-rater kappa describes those raters only; it is not a universal human-agreement ceiling.

## Reproducible demonstration

```bash
python -m examples.generate_fixture
python -m verdictlens evaluate --data examples/synthetic_pairs.json --out report.json
```

| Demo judge | Reference agreement | Kappa | Order flips | Padding flips |
| --- | --- | --- | --- | --- |
| Evidence heuristic | 75% | 0.6364 | 0% | 0% |
| Length heuristic | 25% | -0.0909 | 0% | 50% |

These values are measured on the committed synthetic fixture, not recruited human judgments or public benchmark results. The repeated templates intentionally make the probe understandable and invalidate claims of broad generalization. Full example outputs are in [examples/evidence-report.json](examples/evidence-report.json) and [examples/length-report.json](examples/length-report.json). Dataset and rubric hashes track content; elapsed time is excluded from the deterministic run identity.

## Methods and limitations

- Kappa is `(observed agreement − chance agreement) / (1 − chance agreement)` using the observed marginal label distributions. If chance agreement is one, kappa is undefined and represented by JSON `null`.
- Bootstrap resamples pairs with replacement and reports 2.5th/97.5th percentile endpoints. Undefined kappa draws are omitted and counted. Intervals are descriptive, especially for small or correlated samples.
- Order-flip rate measures consistency after identity remapping; it is not a complete estimate of causal position bias. Filler can alter perceived content, not just length.
- Family metadata is retained for provenance. Same-family/cross-family bias analysis is not implemented or inferred from the mocks.
- The review queue prioritizes baseline/reference disagreement, order flips and split reference votes. It excludes holdout pairs and never replaces reference labels.
- Blinding is a workflow aid, not a security boundary: the same local operator can inspect source labels or earlier reports. Pseudonyms do not authenticate reviewers or prove independence.
- The server is bound to `127.0.0.1`, validates Host/Origin, and processes requests sequentially. It has no authentication, TLS, multi-user isolation or production deployment support. Do not expose it publicly through a tunnel.
- Holdout inspection and repeated rubric tuning can overfit. Freeze the rubric before a final evaluation; a separate unseen transfer task remains planned.

See [METHODS.md](docs/METHODS.md) for the validation design and [FEATURES.md](FEATURES.md) for prioritized additions and their acceptance tests.

## Repository map

| Path | Purpose |
| --- | --- |
| `verdictlens/core.py` | Schemas, reference aggregation, metrics, probes, queue ranking and report reconciliation |
| `verdictlens/judges.py` | Local Ollama adapter |
| `verdictlens/review.py` | SQLite snapshots, stable blinding and append-only votes |
| `verdictlens/web.py`, `workbench.html` | Local HTTP API and rubric/review interface |
| `verdictlens/__main__.py` | CLI |
| `examples/` | Synthetic data generator, rubric and measured demo reports |
| `tests/` | Metric, adapter, import, queue, persistence and HTTP integration tests |
| `.github/workflows/ci.yml` | Python 3.11/3.12/3.13 tests and demo evaluation |

## Contributing

Keep fixes focused and run `python -m unittest discover -s tests -v`. Changes to metrics need hand-calculated examples; changes to blinding need tests that no labels or prior votes leak into assignments. Extend input schemas deliberately and retain provenance. Do not replace synthetic results with real-model claims without committing the method, configuration and permitted evidence.

## License and references

Original implementation released under [MIT](LICENSE). No third-party dataset is bundled. Methods and adapter references: [scikit-learn Cohen's kappa documentation](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.cohen_kappa_score.html), [Ollama API documentation](https://github.com/ollama/ollama/blob/main/docs/api.md). These references describe the interfaces and statistic; they do not validate this application's results.

