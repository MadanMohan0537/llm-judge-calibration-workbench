# VerdictLens feature decisions and backlog

Base traceability: AI PM Project Lab #2, Judge Calibration Lab. Priorities are decisions for the current MVP, not delivery promises. October 5, 2026.

## Implemented baseline

Pairwise reference loader, two deterministic judges, optional local Ollama calls, categorical agreement/kappa, category and split breakdowns, bootstrap intervals, order/length probes, rubric reruns and JSON reports. Synthetic provenance is explicit. Public dataset adapters, live-model benchmarks, family-bias analysis and deployment are not complete.

## P1 — Blinded adjudication workbench: implemented behavior, utility unmeasured

**Problem/trigger:** evaluator builders spend reviewer time on obvious pairs while disagreements remain unresolved.

**Behavior:** prioritize development disagreements, order flips and split reference votes; randomize answer order per reviewer; hide labels and prior votes; retain independent votes separately without changing the frozen reference dataset. Persist across restarts and reject repeat votes from the same pseudonym.

**Dependencies:** validated pairs, immutable run snapshots, HMAC blinding secret, SQLite and independently participating reviewers. No hosted service.

**Success tests:** labels/metadata absent from assignments; canonical mapping restores the chosen original answer; independent votes persist; duplicate votes preserve the original; holdout and mismatched datasets never enter the queue. These tests pass. A random-sampling utility comparison has **not** been run.

**Benefit experiment:** freeze a fresh development pool and compare disagreement-prioritized versus seeded random review at equal reviewer budget. Predeclare ambiguity-resolution rate and review time; report denominators and intervals. Evaluate changes on an untouched random holdout. Reject the feature's efficiency claim if it saves no review time or reduces holdout agreement.

**Risk/tradeoff:** selective adjudication biases the reviewed pool; separate it from the benchmark. Pseudonyms do not ensure independent people, and a local operator can reveal hidden labels.

## P2 — Rubric transfer challenge: planned from the original extensions

**Problem:** a rubric optimized for support answers may fail on research answers.

**Behavior:** freeze the rubric hash, evaluate a separately labeled task and show in-domain versus transfer agreement loss.

**Dependencies:** compatible quality definitions, an unseen task, independently acquired labels and sufficient sample size.

**Success test:** refuse comparison when rubric hashes differ or tasks use incompatible label definitions; seeded transfer failure must remain visible even if pooled kappa improves.

**Risk/tradeoff:** task differences can make the metric misleading. Prefer an explicit compatibility review over automatic cross-domain rankings. Relative effort: medium.

## New P1 — Immutable real-run import: implemented October 21, 2026

**Problem:** CLI Ollama evidence cannot yet enter the UI review workflow.

**Behavior:** import a report only when its dataset/rubric hashes, exact row coverage,
labels, dataset-derived fields, aggregates, judge identity and deterministic run identity
validate. Row order is normalized. Save the snapshot without permitting overwrite and
queue development disputes. Identical re-import is idempotent.

**Dependencies:** strict report schema, provenance validation and adapter-call metadata.

**Success test:** reordered valid rows import; missing, duplicate or altered labels,
metadata, aggregates and run identities fail; imports cannot overwrite an existing
snapshot. Six import-focused tests plus the CI round trip pass.

**Risk/tradeoff:** a valid schema does not establish trustworthy upstream labels or
verified execution. The local database stores raw text and reports. Execution timing is
mutable wrapper metadata so the same evidence can be moved across machines; this means it
cannot authenticate runtime claims.

## Refined priorities — planned

| Priority | Problem and behavior | Dependencies | Success test | Risks/tradeoffs |
| --- | --- | --- | --- | --- |
| P0 | Rubric transfer can fail unseen tasks; freeze a rubric and compare compatible domains separately. | Independently labeled transfer fixture and compatibility declaration | Seeded transfer loss remains visible even if pooled kappa rises. | Domain quality definitions may be incomparable. |
| P1 | Adjudication efficiency is asserted but unmeasured; compare prioritized and seeded-random queues at equal budgets. | Fresh pool and review-time capture | Predeclared ambiguity-resolution gain without holdout loss. | Selective review can bias conclusions. |
| P1 | Imported execution is self-asserted; add a local artifact manifest with model/configuration digests. | Adapter metadata contract | Changed model/config artifact invalidates provenance. | Digests do not prove execution. |
| P2 | Reviewer counts can conceal sparse or divergent raters; show overlap-aware reliability. | Sufficient shared assignments | Contradictory rater visible; sparse overlap suppressed. | Disagreement may reflect expertise. |
| P2 | Single probes confound instability and intervention; add symmetric repeated probes with budgets. | Recorded runtime/model versions | Position bias and stochasticity have distinct seeded signatures. | Triples calls and energy use. |

## New P2 — Reviewer reliability panel: planned

**Problem:** a growing vote count can hide one consistently divergent reviewer.

**Behavior:** show pairwise agreement and coverage for pseudonymous reviewers on overlapping assignments, withholding identities in exports.

**Dependencies:** enough overlapping independently labeled pairs and explicit missing-data handling.

**Success test:** sparse overlap is marked insufficient; a seeded contradictory rater is visible without changing reference labels.

**Risk/tradeoff:** disagreement may represent valid expertise, not poor quality. Do not rank staff or remove a reviewer automatically. Medium effort.

## New P2 — Symmetric and repeated probes: planned

**Problem:** padding only answer A and making one model call confounds style preference with model variability.

**Behavior:** pad both identities in separate runs, repeat original judgments, and report within-configuration instability beside intervention deltas.

**Dependencies:** probe schema, budget caps and recorded model/runtime versions.

**Success test:** a position-biased test judge and a stochastic test judge produce different failure signatures; fixed budgets are enforced.

**Risk/tradeoff:** more calls increase time and energy cost. Start on a small frozen subset, stop when instability prevents interpretation. Medium effort.

## New P3 — Family provenance audit: planned

**Problem:** a team suspects self-family preference but lacks balanced evidence.

**Behavior:** stratify by documented judge/answer families only when labels, tasks and sample coverage are comparable.

**Dependencies:** actual model provenance, balanced examples and a credible held-out labeling procedure.

**Success test:** unknown families stay unknown; imbalanced samples cannot produce a headline bias conclusion.

**Risk/tradeoff:** family names are not causal controls and models may have seen benchmark pairs. Defer until real-run ingestion and provenance checks work. Large validation effort.

