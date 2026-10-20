# LLM Judge Calibration Workbench

[![CI](https://github.com/MadanMohan0537/llm-judge-calibration-workbench/actions/workflows/ci.yml/badge.svg)](https://github.com/MadanMohan0537/llm-judge-calibration-workbench/actions/workflows/ci.yml)

**Find out how often an AI judge agrees with reference reviewers, and whether its preferences change for the wrong reasons, such as answer order or answer length.**

A local Python workbench (standard library only) with a browser review UI. The package name and the CLI program name are still `verdictlens` (`python -m verdictlens`; the setuptools script entry is also `verdictlens`). The page title in the browser UI is still VerdictLens.

## Problem and who it's for

When a team uses a model as a judge ("is answer A or B better?") to evaluate other models, a judge that prefers whichever answer comes first, or whichever is longer, passes that bias into every downstream score. This workbench is for ML evaluation engineers, AI PMs who rely on judge-based scores, and the human reviewers who settle disagreements, so they can calibrate a judge before trusting it.

## Approach

- Score a pairwise judge against reference human votes: **agreement rate and Cohen's kappa**, with seeded pair-bootstrap intervals (default seed 17, 500 draws) and breakdowns by category and split.
- **Order-swap probe:** swap A and B, map the decision back to the original identities, and count preference flips.
- **Length probe:** append a fixed filler string to answer A and report the flip rate and the change in A's win rate.
- Keep **development and holdout** results separate. The review queue contains only development pairs whose priority is above zero (reference disagreement, an order flip, or split reference votes). Holdout pairs stay out of the queue.
- A **blinded adjudication queue**: the next eligible pair is served in priority order. Whether the displayed answers are swapped is chosen per reviewer by a stable keyed hash. Votes are appended independently. A repeat vote from the same pseudonym is rejected and the original vote is kept.
- Record dataset and rubric hashes, and store run snapshots in SQLite.

## What exists today

Reproduced on Python 3.12.3 with the test and evaluate commands in Quick start. The same summary figures are in [examples/evidence-report.json](examples/evidence-report.json) and [examples/length-report.json](examples/length-report.json).

- Two deterministic demo judges (an evidence-term heuristic and a deliberately length-biased heuristic) and an optional CLI adapter for a model you already run in local Ollama. The browser UI runs only the two heuristics.
- On the bundled 24 synthetic pairs (16 development, 8 holdout):

  | Demo judge | Reference agreement | Kappa | Order flips | Padding flips | Change in A's win rate |
  |---|---|---|---|---|---|
  | Evidence heuristic | 75% | 0.6364 | 0% | 0% | 0 |
  | Length heuristic | 25% | -0.0909 | 0% | 50% | +0.5 |

  Kappa is rounded to four decimal places from `0.6363636363636364` and `-0.09090909090909091`. These figures come from the committed synthetic fixture, not from recruited human judgments or a public benchmark.
- A local workbench at `http://127.0.0.1:8788` for comparing the two demo judges, editing the rubric JSON and rerunning, blinded review, and exporting the report JSON and review votes.
- 28 tests in `tests/test_verdictlens.py` (metrics, review persistence, the Ollama adapter with a mocked transport, and HTTP). The GitHub Actions workflow [`.github/workflows/ci.yml`](.github/workflows/ci.yml) runs that suite on Python 3.11, 3.12, and 3.13. The local run above used Python 3.12.3 only.

## How success would be measured

| Measure | Status |
|---|---|
| Judge–reference agreement and kappa on labeled pairs | The evaluate command computes this. The only committed results are the synthetic fixture in the table above. |
| Length bias on a candidate judge | Measured on the synthetic fixture: the length heuristic has a 50% padding-flip rate and a +0.5 change in A's win rate. The evidence heuristic has 0% padding flips. |
| Order bias on a candidate judge | Both bundled demo judges have a 0% order-flip rate. A unit test checks a judge that always selects the displayed first answer and records a 100% order-flip rate. Not yet measured on a live model. |
| Results for a real LLM judge | Not yet measured. The Ollama adapter is tested with mocked transport. |
| Reviewer time per adjudicated disagreement | Not yet measured |

## Limitations

- The bundled dataset is small and template-based (four repeated answer patterns), so it shows how the probes work and supports no broad conclusions.
- A strict-majority reference treats "no majority" as a tie, which mixes inconclusive votes with explicit ties.
- The order-flip rate is a consistency check, not a full causal estimate of position bias. Filler text can change perceived content, not just length.
- Blinding is a workflow aid, not a security boundary. Pseudonyms do not authenticate reviewers. The assignment payload hides labels, and a local operator can still read the database.
- The server binds to `127.0.0.1`, checks the Host and Origin headers, and has no authentication or TLS. Do not expose it publicly.
- Cost per 1,000 judgments is not measured (`provider_billed_cost` is null). Importing CLI runs of real models into the review UI is backlog work described in [FEATURES.md](FEATURES.md).

See [docs/METHODS.md](docs/METHODS.md) and [FEATURES.md](FEATURES.md).

## Quick start

Running the workbench requires Python 3.11+. No API key and no cloud account. Run these commands from the repository root so `python -m verdictlens` can import the package.

```bash
git clone https://github.com/MadanMohan0537/llm-judge-calibration-workbench.git
cd llm-judge-calibration-workbench
python -m unittest discover -s tests -v
python -m verdictlens evaluate --data examples/synthetic_pairs.json --judge mock-evidence --out report.json
python -m verdictlens evaluate --data examples/synthetic_pairs.json --judge mock-length --out length-report.json
python -m verdictlens serve --data examples/synthetic_pairs.json   # then open http://127.0.0.1:8788
```

`serve` writes `verdictlens.sqlite` in the working directory. That file is gitignored. It holds pair text, run snapshots, votes, and the local blinding secret.

With a model already installed in local Ollama:

```bash
python -m verdictlens evaluate --data examples/synthetic_pairs.json --judge ollama --model YOUR_INSTALLED_MODEL --out local-model-report.json
```

That makes three sequential calls per pair to `http://127.0.0.1:11434/api/chat` (original, swapped, padded): 72 calls on this fixture. Temperature is 0. Invalid output, a transport error, or a timeout aborts the run with exit code 2. There is no silent fallback to a mock judge. A live model was not run for the figures above.

To use your own pairs, follow the schema in [examples/synthetic_pairs.json](examples/synthetic_pairs.json). The file needs `schema_version` 1 and 1–500 pairs. Each pair needs a unique `id`; nonempty `category`, `prompt`, `a`, `b`, `family_a`, and `family_b` (each at most 20,000 characters); an explicit `development` or `holdout` split; and at least two votes using `a`, `b`, or `tie`. Use only data you are permitted to process.

## Deployment

Cloudflare Workers is the planned target. This repository is not deployed, and Workers is not configured yet.

There is no `wrangler.toml` and no Worker entry point. The current program is a Python standard-library server bound to `127.0.0.1`. A Workers deploy needs:

- a `wrangler.toml`
- a Worker entry point
- Python Workers, or a JavaScript/TypeScript port of the workbench

The deploy path is Cloudflare Workers with `npx wrangler deploy`, with no versioned release steps. When the configuration above exists, deploy with:

```bash
npx wrangler deploy
```

## License

MIT. See [LICENSE](LICENSE). Method references: [scikit-learn Cohen's kappa](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.cohen_kappa_score.html), [Ollama API](https://github.com/ollama/ollama/blob/main/docs/api.md).
