# Experiments, analysis, and reproducibility

## Contents

1. Protocol and pilot
2. Run and result provenance
3. Analysis and robustness
4. Reproducibility package
5. Assurance boundaries

## Protocol and pilot

Before definitive execution, specify questions or estimands, data or proof assumptions, sampling and exclusions, comparators and ablations, outcomes and uncertainty, multiplicity, environment and budget, stopping and rerun rules, robustness, and confirmatory versus exploratory analyses. A plan reconstructed after observing results is retrospective.

Use the pilot to test access, measurement, instrumentation, runtime, cost, pipeline correctness, baselines, assumptions, participant burden, and safety. Record `go`, `revise`, or `stop` in `study/pilot-decision.json`, with timezone-aware decision time, protocol effect, and hash-bound evidence.

- `stop` blocks definitive execution.
- `revise` must include `amendment_path: protocol/amendments.md` and the current `amendment_sha256`; complete that amendment before affected definitive runs.
- `go` does not make favorable pilot outcomes definitive evidence unless the protocol authorizes their role.

## Run and result provenance

Assign runs `E####`. A complete run records kind, phase, start/end times, code and data versions, environment, parameters or seeds, and hash-bound code, data, environment, and raw output. For a genuinely absent binding, use the literal `not-applicable` with no hash; do not leave an unexplained blank. Failed, cancelled, planned, running, pilot, or exploratory records do not satisfy definitive execution.

Assign results `R####`. An active, reported, or confirmed result records source runs, analysis code and hash—or explicit noncomputational status—ordered input paths and matching hashes, estimate or formal result, uncertainty, robustness, status, and notes. It may depend only on complete runs. Failed, withdrawn, or superseded results cannot support active claims.

Preserve unfavorable and failed runs when they affect selection, validity, or reproducibility. Recompute hashes and re-audit downstream records after any byte change.

## Analysis and robustness

Match analysis to design and estimand. Check as applicable:

- unit of analysis, independence, clustering, hierarchy, and repeated measures;
- data leakage, train/validation/test separation, missingness, and exclusions;
- effect sizes, uncertainty, multiplicity, and researcher degrees of freedom;
- assumptions, diagnostics, calibration, imbalance, and thresholds;
- stochastic variation across seeds or runs;
- hardware, compiler, library, model, API, and dataset drift;
- qualitative coding, reflexivity, and disagreement handling;
- formal assumptions, boundary cases, and machine checking.

Design robustness around plausible failure modes: alternative estimators, ablations, stronger and simpler baselines, distribution or platform shifts, preprocessing and hyperparameter sensitivity, null or adverse outcomes, failed assumptions, and independent implementations when justified. Never select only favorable seeds, metrics, datasets, subgroups, stopping points, or output files.

## Reproducibility package

A practical package identifies source and build steps, locked dependencies or environment, lawful data access, exact commands, seeds and determinism policy, expected outputs and checksums, resource requirements, raw or manifested outputs, analysis scripts, claim-to-result mapping, limitations, and archival location.

Test from a clean, isolated, no-secret environment. Record what actually ran. Do not install unreviewed dependencies into a base environment or execute destructive commands.

## Assurance boundaries

Use precise terms:

- **internal consistency:** local outputs match manuscript values;
- **author rerun:** authors reran their artifact;
- **independent reproduction or replication:** an independent party performed the relevant procedure;
- **badge or certification:** awarded by the responsible evaluator under current rules.

A local audit cannot establish independent reproduction, a venue badge, or scientific validity. Report unrun, missing, or irreconcilable evidence as unverified rather than inferring it.
