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

## New P1 — Immutable real-run import: planned

**Problem:** CLI Ollama evidence cannot yet enter the UI review workflow.

**Behavior:** import a report only when its dataset hash, rubric hash, row coverage and judge identity validate; save the snapshot and queue development disputes.

**Dependencies:** strict report schema, provenance validation and adapter-call metadata.

**Success test:** reordered valid rows import; missing, duplicate or altered labels fail; imports cannot overwrite an existing snapshot.

**Risk/tradeoff:** a valid schema does not establish trustworthy upstream labels. Display source provenance and never silently treat a user-supplied report as verified execution. Medium effort; higher priority than hosted deployment because it connects the existing model adapter to the review product.

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
