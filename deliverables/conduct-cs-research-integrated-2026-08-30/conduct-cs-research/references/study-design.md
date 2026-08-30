# Study-design and reporting route

## Contents

1. Route by contribution and evidence
2. Study families
3. Cross-cutting design checks
4. Reporting guidelines
5. Failure modes

## Route by contribution and evidence

Select a study family from the question, intended contribution, inferential target, unit of analysis, and available evidence. A paper may use multiple families; specify which family supports each claim.

Do not force biomedical PICO framing onto computer-science questions. Use concept facets, population-task-context frames, PICOC, SPIDER, or theory-specific obligations when more appropriate.

## Study families

### Theory and formal methods

Define objects, assumptions, notation, propositions, proof obligations, and counterexample search. Separate theorem, conjecture, empirical illustration, and intuition. Check hidden regularity assumptions, boundary cases, constructiveness, computability, complexity, and dependence on prior lemmas. Use proof assistants or executable checks when proportionate, but do not equate mechanized syntax with a valid formalization.

### Algorithms

Specify computational model, inputs, outputs, invariants, correctness, complexity, approximation or regret guarantees, baselines, and pathological cases. Distinguish asymptotic improvement from practical performance. Use adversarial and distribution-shift tests when claims extend beyond average cases.

### Machine learning and AI

Define task, data-generating context, splits, leakage controls, baselines, hyperparameter budget, seeds, model-selection protocol, metrics, uncertainty, ablations, robustness, compute, and environmental or social costs when material. Separate benchmark performance, causal claims, generalization claims, and deployment claims. Use current domain-specific reporting guidance where applicable.

### LLM and generative-model evaluation

Specify model/version/date, system and user prompts, sampling parameters, tool access, context construction, evaluator design, contamination risk, repeated trials, failure taxonomy, human-evaluation protocol, prompt-injection defenses, and cost. Avoid treating a single model snapshot or benchmark as a stable population. Report prompt and model drift.

### Systems, networking, databases, and architecture

Define workload, platform, topology, implementation maturity, baselines, measurement instrumentation, warm-up, repetitions, variance, resource limits, failure injection, scalability envelope, and external validity. Do not generalize from one hardware or cloud configuration without justification.

### Empirical software engineering

Define repositories, sampling frame, mining procedure, construct operationalization, developer or artifact unit, labeling, inter-rater process, missingness, confounding, temporal leakage, and replication package. Distinguish repository prevalence from developer behavior or causal impact.

### HCI and human-subject research

Define participants, recruitment, consent, ethics review or exemption, tasks, instruments, researcher positionality, qualitative or quantitative analysis, power or information-power rationale, accessibility, harms, privacy, and compensation. Do not claim independent coding, saturation, or member checking unless performed.

### Security and privacy

Define threat model, attacker capabilities, assets, trust boundaries, vulnerability class, test environment, disclosure plan, dual-use controls, and harm minimization. Separate proof-of-concept capability from real-world prevalence or exploitability. Coordinate responsible disclosure before publishing actionable details.

### Dataset, benchmark, and measurement contribution

Define intended population, collection and consent, licensing, annotation, coverage, subgroup composition, leakage, duplication, quality controls, documentation, maintenance, governance, metric validity, benchmark incentives, and deprecation plan. Avoid declaring a dataset representative without a defensible sampling frame.

### Simulation and computational experiment

Define model assumptions, calibration, verification, validation, stochastic design, parameter ranges, sensitivity, uncertainty propagation, numerical stability, and relation to the real system. Separate conclusions about the model from conclusions about reality.

### Systematic, scoping, or mapping review

Define review type, protocol, databases and interfaces, search translation, eligibility, screening, extraction, appraisal, synthesis, updates, and reporting. Read [systematic-search.md](systematic-search.md).

### Mixed or hybrid study

Create a claim-to-method map. State how components integrate, which component dominates each inference, and how conflicting evidence will be handled. Do not use method variety as a substitute for a coherent inferential design.

## Cross-cutting design checks

For every family, check:

- construct validity: does the measure represent the concept?
- internal validity: can the design support the inferential language used?
- statistical-conclusion validity: are uncertainty, multiplicity, dependence, and power addressed?
- external validity: what population, task, environment, time, or version is supported?
- reproducibility: can another researcher recover inputs, procedures, and outputs?
- robustness: do conclusions survive plausible choices and perturbations?
- ethics and governance: are human, societal, legal, privacy, security, and environmental risks handled?
- negative evidence: what result would weaken or reverse the conclusion?

## Reporting guidelines

Before finalizing a protocol or manuscript:

1. fetch the current target-journal instructions from the official journal or publisher;
2. search the EQUATOR Network and the relevant disciplinary society for the applicable reporting guideline;
3. use the latest official checklist and explanation document;
4. map each item to a manuscript or supplement location;
5. report nonapplicable items with reasons rather than silently omitting them.

Possible routes include CONSORT or CONSORT-AI for randomized studies, STROBE for observational studies, PRISMA and PRISMA-S for systematic reviews and searches, PRISMA-ScR for scoping reviews, TRIPOD or TRIPOD+AI for prediction models, COREQ or SRQR for qualitative research, and field-specific ML, benchmark, HCI, security, or software-engineering guidance. Verify the current version; do not rely on this list as a static rule.

Journal rules and reporting guidelines solve different problems. Follow both. When they conflict, document the conflict and seek the target venue's interpretation.

## Failure modes

Reject or narrow designs that rely on:

- convenience data presented as population evidence;
- test-set iteration or benchmark leakage;
- post hoc outcomes presented as preregistered;
- arbitrary baseline exclusion;
- underidentified causal language;
- one run, seed, prompt, annotator, repository, device, or environment supporting a broad claim;
- unverified synthetic labels treated as ground truth;
- qualitative themes without a transparent analytic process;
- unavailable proprietary evidence supporting unreproducible claims;
- a systematic-review label without reproducible search and selection records.

When the design cannot support the intended claim, revise the claim, improve the design, or stop. Do not repair an inferential defect with prose.