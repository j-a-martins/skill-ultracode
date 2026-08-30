# Experiments, analysis, and reproducibility

## Contents

1. Protocol before execution
2. Pilot and feasibility decision
3. Run provenance
4. Result provenance
5. Statistical and computational analysis
6. Robustness and negative evidence
7. Reproducibility package
8. Independent reproduction claims
9. Failure modes

## Protocol before execution

Before definitive execution, specify:

- research questions and estimands or formal propositions;
- datasets, participants, workloads, systems, or proof assumptions;
- sampling, splits, exclusions, and missing-data handling;
- baselines, comparators, controls, and ablations;
- outcomes, metrics, uncertainty, multiplicity, and robustness checks;
- environment, code version, data version, compute, and budget;
- stopping, failure, rerun, and deviation rules;
- which analyses are confirmatory and which are exploratory.

A protocol reconstructed after observing results is retrospective. Do not represent it as preregistered or prospective.

## Pilot and feasibility decision

Use a pilot to test:

- access and data quality;
- measurement validity;
- instrumentation and logging;
- runtime, memory, storage, and cost;
- pipeline correctness;
- baseline implementation;
- analysis assumptions;
- participant burden and safety where applicable.

Record `go`, `revise`, or `stop` in `study/pilot-decision.json`, with timezone-aware decision time, protocol effect, and one or more project-relative evidence paths plus SHA-256 values. A stop decision blocks definitive execution. A revise decision requires an amendment before affected definitive runs.

Do not promote a favorable pilot result into the definitive analysis without a protocol-authorized role.

## Run provenance

Assign each execution `E####` in `study/runs.csv`. Record:

- kind and phase: pilot, exploratory, definitive, or replication;
- start and end times with timezone;
- code or proof version;
- data version;
- environment and dependencies;
- parameters, seeds where meaningful, hardware, platform, and external-service versions;
- raw-output path and SHA-256;
- status and failure notes.

For local code, data, and environment manifests, record project-relative paths and hashes. A version string alone is not enough when local bytes are load-bearing. Sensitive or external data may use a hash-bound manifest rather than copying the data into the workspace.

A complete definitive or replication run needs terminal time and hash-bound raw output. Failed, cancelled, planned, running, pilot, or exploratory records do not satisfy the definitive execution gate.

Preserve unfavorable and failed runs when they affect selection, validity, or reproducibility.

## Result provenance

Assign each result `R####` in `study/results.csv`. Record:

- source run IDs;
- analysis code path and hash, or `not-applicable` for a genuinely noncomputational result;
- input paths and matching hashes;
- estimate or formal result;
- uncertainty;
- robustness and sensitivity result;
- status and notes.

An active, reported, or confirmed result may depend only on complete runs. Failed, withdrawn, or superseded results cannot silently support active manuscript claims.

If multiple files are inputs, separate paths and hashes with semicolons in the same order. Recompute hashes after any change and re-audit dependent results and claims.

## Statistical and computational analysis

Match analysis to design and estimand. Check as relevant:

- unit of analysis and independence;
- train/validation/test separation and leakage;
- repeated measures, clustering, hierarchy, and temporal dependence;
- multiplicity and researcher degrees of freedom;
- effect sizes and uncertainty, not only thresholded p-values;
- missing data and exclusions;
- model assumptions and diagnostics;
- calibration, class imbalance, and decision thresholds;
- stochastic variability across seeds or runs;
- hardware, compiler, library, model, API, and dataset drift;
- correctness and numerical stability;
- qualitative coding, reflexivity, and disagreement handling;
- formal proof assumptions, boundary cases, and machine checking where applicable.

Never select only favorable metrics, seeds, datasets, subgroups, stopping points, or output files. Exploratory analyses remain labeled exploratory.

## Robustness and negative evidence

Design checks around plausible failure modes rather than a ritual checklist. Consider:

- alternative specifications and estimators;
- ablations and component isolation;
- stronger or simpler baselines;
- distribution, workload, platform, or temporal shifts;
- sensitivity to seeds, thresholds, preprocessing, and hyperparameters;
- null, adverse, contradictory, or unstable results;
- failed assumptions and boundary cases;
- replication across implementations or sites where justified.

A robustness result is meaningful only when its data, code, parameters, and output are preserved like the primary result.

## Reproducibility package

A practical package may contain:

- source and build instructions;
- dependency lockfile or environment manifest;
- data access and license instructions;
- exact commands for tests, preprocessing, training, evaluation, and figure generation;
- seed and determinism policy;
- expected outputs and checksums;
- resource requirements;
- raw and processed outputs or lawful manifests;
- analysis scripts;
- claim-to-result mapping;
- known limitations and nondeterminism;
- archival location and persistent identifier.

Test from a clean, isolated, no-secret environment. Do not install unreviewed dependencies into a base environment or execute destructive commands. Record what actually ran.

## Independent reproduction claims

Use terms carefully:

- **internal consistency** — current local outputs match manuscript values;
- **author rerun** — authors reran their own artifact;
- **independent reproduction or replication** — an independent party performed the relevant procedure under stated conditions;
- **artifact badge or certification** — awarded by the responsible venue or evaluator under current rules.

Do not claim independent reproduction, replication, or a badge from a local audit alone.

## Failure modes

Reject or revise a record that:

- treats a retrospective plan as prospective;
- advances past a pilot stop decision;
- marks a run complete without raw-output bytes;
- lets a failed or exploratory run satisfy definitive execution;
- reports a result from missing, changed, or non-complete inputs;
- omits uncertainty or robustness for an active quantitative result;
- selects the best seed or metric without a prospective rule;
- hides failed or adverse runs;
- changes analysis after observing results without recording a deviation;
- calls internal consistency independent reproduction;
- claims a badge or reproducibility status without current external evaluation.

Reproducibility controls increase inspectability; they do not by themselves prove scientific validity.
