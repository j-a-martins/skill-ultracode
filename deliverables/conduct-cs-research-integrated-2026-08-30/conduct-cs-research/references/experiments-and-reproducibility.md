# Experiments, analysis, and reproducibility

## Contents

1. Protocol before execution
2. Implementation and environment
3. Pilot and definitive runs
4. Statistical and computational analysis
5. Robustness and negative evidence
6. Reproducibility package
7. Domain-specific cautions
8. Adversarial checks

## Protocol before execution

Define the inferential target before collecting or inspecting definitive results. Record:

- datasets, repositories, participants, workloads, proofs, simulations, or tasks;
- sampling and inclusion rules;
- splits and leakage controls;
- baselines and comparator-selection rationale;
- primary and secondary outcomes;
- metrics and aggregation;
- uncertainty and multiplicity methods;
- hyperparameter or design-search budget;
- seeds and repeated-trial policy where stochasticity matters;
- exclusion, failure, and outlier handling;
- stopping and abandonment criteria;
- robustness, sensitivity, ablation, and subgroup analyses;
- compute, time, financial, and human-resource budgets;
- ethics, privacy, security, and disclosure constraints.

Do not choose a primary metric, dataset slice, baseline, prompt, or stopping point after seeing favorable outcomes and present it as prospective.

## Implementation and environment

Bind every definitive execution to recoverable inputs:

- source-code commit or immutable archive;
- uncommitted-diff status;
- data or corpus version and acquisition date;
- dependency lockfile, container, or environment export;
- operating system, hardware, accelerator, compiler, driver, and relevant service versions;
- model identifier, provider, release or snapshot date, and API parameters;
- configuration file and command line;
- random seeds and deterministic settings;
- credentials or proprietary dependencies described without exposing secrets;
- raw-output path and checksum when appropriate.

Capture the environment before it changes. A package list reconstructed after the run is weaker evidence and must be labeled as such.

## Pilot and definitive runs

Use pilots to test instrumentation, runtime, scale, data quality, and assumptions. Do not mix pilot and definitive evidence without a declared rule.

For every run, record:

- purpose and relation to protocol;
- start and end time;
- inputs and versions;
- parameterization;
- resource allocation;
- exit status and failures;
- raw outputs and logs;
- exclusions or manual intervention;
- whether the run is pilot, exploratory, confirmatory, or replication.

Preserve failed runs that reveal method fragility, selection pressure, or reproducibility problems. Do not repeatedly rerun until a favorable seed appears without reporting the selection process.

## Statistical and computational analysis

Match the analysis to the design and dependence structure. Check:

- unit of analysis versus unit of sampling;
- repeated measures, clustering, paired comparisons, and temporal dependence;
- missingness and censoring;
- model assumptions and diagnostics;
- effect estimates and uncertainty, not p-values alone;
- multiplicity across outcomes, models, datasets, subgroups, and repeated looks;
- practical as well as statistical significance;
- power, precision, or simulation-based operating characteristics where relevant;
- preregistered versus exploratory analyses;
- analysis-code version and test coverage;
- numerical stability and convergence;
- human-evaluation reliability and adjudication.

Avoid pseudo-replication. Multiple observations from one repository, participant, prompt, model, or dataset may not be independent evidence.

## Robustness and negative evidence

Plan checks that could change the conclusion:

- alternate defensible metrics and estimators;
- perturbations, stress tests, and distribution shifts;
- alternative data cleaning or exclusion rules;
- ablations and component substitution;
- stronger, simpler, and contemporary baselines;
- hardware, software, geographic, linguistic, demographic, temporal, or version variation;
- failure cases and counterexamples;
- replication on independent data or implementation;
- sensitivity to seeds, prompts, annotators, or search strategy;
- placebo, negative-control, or falsification tests where meaningful.

Report checks selected before and after initial results separately. Preserve null and adverse findings. If robustness fails, narrow the claim rather than hiding the result.

## Reproducibility package

Provide what another qualified researcher needs to audit or reproduce the work, subject to legal and ethical limits:

- overview and exact reproduction path;
- data provenance, licenses, access conditions, and checksums;
- code, configuration, dependencies, and environment;
- commands for preprocessing, execution, analysis, and figure generation;
- expected outputs and resource requirements;
- seed and nondeterminism notes;
- tests or smoke checks;
- mapping from manuscript tables and figures to generation commands;
- known deviations, failures, and unsupported platforms;
- archival identifier and license;
- restricted-data or proprietary-component substitute procedure.

Never claim full reproducibility when critical data, code, models, services, or manual steps are unavailable. Describe the actual level: inspectable, computationally reproducible, independently replicated, or only partially recoverable.

## Domain-specific cautions

### ML and LLM work

Control test-set and prompt leakage, model selection, repeated trials, evaluator bias, contamination, version drift, non-deterministic APIs, and hidden provider changes. Human evaluation needs a defined rubric, training, blinding where possible, disagreement handling, and uncertainty.

### Systems work

Control warm-up, caching, background load, clock and profiler effects, network variability, autoscaling, cloud tenancy, thermal behavior, and resource saturation. Report distributions rather than a selected best run.

### Empirical software engineering

Preserve repository snapshots and mining queries. Address forks, mirrors, bots, generated files, project size, survivorship, temporal leakage, and dependence within organizations or ecosystems.

### Security work

Use isolated authorized environments, a threat model, safe handling of exploit artifacts, and a disclosure plan. Do not publish operational details that create disproportionate harm.

### Formal work

Check definitions, theorem dependencies, proof obligations, boundary cases, counterexamples, executable specifications, and mechanized assumptions. A passing proof assistant checks the formalized statement, not whether the formalization matches the intended claim.

## Adversarial checks

Before accepting an experimental result, test for:

- hidden test-set use;
- favorable seed, prompt, metric, or subset selection;
- baseline handicapping or unequal budgets;
- unverifiable screenshots or copied summary values;
- missing raw outputs;
- result files modified after analysis;
- code or data version ambiguity;
- silent exclusion of crashes or timeouts;
- confidence intervals computed from the wrong unit;
- exploratory analyses described as confirmatory;
- robustness claims based on cosmetic variations;
- conclusions that extend beyond the tested versions or environments.

Re-open the relevant gate when a material check fails.