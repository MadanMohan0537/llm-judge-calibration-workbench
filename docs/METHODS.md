# Validation and interpretation

The fixture was generated from four repeated answer patterns, cycled across three categories. The first 16 pairs are development and the last eight are holdout. Reference annotations are authored synthetic values; no human study or live model run occurred. A category name does not turn a repeated template into independent domain evidence.

The evidence heuristic counts configured terms. The length heuristic intentionally rewards token count. This establishes that the harness can reveal a known length defect, not that either heuristic evaluates answer quality well. The order-biased test double always selects displayed A; identity remapping must report a 100% order flip rate.

Kappa tests include perfect agreement, perfect reversal and undefined single-label marginals. Reordering preserves statistics while the exact dataset-content hash changes. Bootstrap resamples the paired reference/judge observations together. Undefined draws are excluded explicitly. Samples are not adjusted for repeated prompts, human correlation or finite repeated model-run variance.

Review tests verify response field boundaries, per-reviewer stable order, canonical vote mapping, persistence after restart, immutable repeat votes and held-out exclusion. The HTTP integration test executes page load, evaluation, assignment, vote and export against a real loopback HTTP server. These demonstrate behavior; they do not measure reviewer productivity or ensure independent reviewers.

The optional Ollama adapter is tested using transport mocks for its request and result contract. No live model is installed or used in this release, so latency, model reliability and hardware cost are unmeasured. A failed model request aborts the run instead of contaminating results with a deterministic fallback.

Before a real study: choose a permitted public or freshly authored dataset; document rater identity/procedure separately from public exports; freeze rubric and split; blind reviewers; predeclare sample size and decision thresholds; compare with a random review control; report per-category denominators and uncertainty. Do not interpret the synthetic 0.6364 kappa as validation for a real deployment.
