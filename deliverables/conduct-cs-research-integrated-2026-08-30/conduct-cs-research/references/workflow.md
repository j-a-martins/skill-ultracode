# Research workflow and gates

## Contents

1. Operating principle
2. Lifecycle map
3. Gate criteria
4. Compact workspace
5. Provenance and rollback
6. Imported and retrospective projects
7. External actions

## Operating principle

Advance only when the evidence needed for the next decision exists. A gate is a decision checkpoint, not a bureaucratic ceremony. Use a short-form artifact when it is sufficient; create additional ledgers only when the project complexity justifies them.

Keep three statuses separate:

- `complete`: the required artifact exists and has been checked;
- `approved`: an accountable human accepts the scoped decision;
- `performed`: the external or irreversible action actually occurred.

None implies the others.

## Lifecycle map

Use these stages for full projects:

1. `intake` — objective, scope, governance, materials, constraints.
2. `question` — contribution contract, research questions, nearest-work frame.
3. `protocol` — prospective methods, analysis, search, and reporting plan.
4. `pilot` — feasibility evidence and go/revise/stop decision.
5. `execution` — definitive study, proof, implementation, or search.
6. `analysis` — results, uncertainty, robustness, deviations.
7. `manuscript` — claim-evidence map and complete draft.
8. `internal-review` — scientific, reproducibility, integrity, and prose review.
9. `journal-selection` — fit analysis and current Q1 evidence where requested.
10. `submission-ready` — exact files, disclosures, checklists, and authorization boundary.
11. `revision` — reviewer-response matrix and revised evidence graph.
12. `accepted` — final files, authorship, disclosures, and release plan.
13. `archived` — immutable release record and correction plan.

A standalone systematic search, peer review, or prose revision may use only the stages relevant to that mode.

## Gate criteria

### Intake gate

Confirm the deliverable, study family, available evidence, confidentiality, ethics status, data restrictions, authorship expectations, and AI-policy constraints. Record unknowns rather than guessing.

### Question gate

Require a contribution contract with a comparison class, intended claim types, non-claims, falsifiers, and resource constraints. For theory, identify definitions and proof obligations. For systems or ML, identify the comparison budget. For HCI or human data, identify the ethical route.

### Protocol gate

Require dated methods and analysis choices. For systematic reviews, freeze eligibility criteria and source-specific search strategy before full screening. For retrospective reconstruction, label the protocol as retrospective and list observed evidence that may have influenced choices.

### Pilot gate

Require feasibility findings and an explicit decision. A pilot may change the protocol, but the amendment must precede the definitive run.

### Execution gate

Require versioned inputs, code or proof state, environment, parameters, and raw-output locations. Do not advance on undocumented screenshots or selected summary values alone.

### Analysis gate

Require analysis code or derivation, uncertainty, robustness, exclusions, deviations, and contradictory findings. Mark exploratory analyses.

### Manuscript gate

Require a complete claim-evidence matrix. Every load-bearing claim must map to primary evidence, a result, or a clearly identified inference. Every number and table must have an origin.

### Internal-review gate

Require resolution or explicit acceptance of design-limiting findings. Style review cannot close methodological findings. Re-run affected analyses after material changes.

### Journal-selection gate

Require current scope and instruction checks, scientific-fit rationale, article-type fit, policy and cost checks, and provider/year/category-specific quartile evidence when Q1 is claimed.

### Submission-ready gate

Require the exact payload, destination, disclosures, author consent, and an explicit action-specific authorization immediately before transmission.

### Revision and acceptance gates

Require a comment-to-change matrix, revised claim-evidence audit, final-author approval, and release checks. Preserve rejected reviewer suggestions with reasons.

## Compact workspace

Use `scripts/init_project.py` when a workspace helps. The compact scaffold contains:

- `project.json` and `state.json`;
- `governance/charter.md`;
- `protocol/protocol.md` and `protocol/amendments.md`;
- `evidence/sources.csv` and mode-specific search files;
- `study/runs.csv`, `study/results.csv`, and `study/deviations.md`;
- `claims/claims.csv`;
- `manuscript/main.tex` and `manuscript/references.bib`;
- mode-specific review or prose records;
- `publication/journals.csv`, `publication/selected-journal.json`, and a submission checklist.

Do not create a second project-management system when the user already has a suitable repository, ELN, preregistration, issue tracker, or data-management plan. Map existing artifacts instead.

## Provenance and rollback

Use stable identifiers only when the project needs cross-file traceability. Record source notes separately from source metadata when interpretation matters. A note should state whether it supports, contradicts, qualifies, or merely contextualizes a claim.

When an upstream item changes:

1. identify dependent decisions, runs, results, claims, tables, and prose;
2. mark them `needs-review` rather than silently updating them;
3. rerun or re-derive what is materially affected;
4. record the amendment and reason;
5. re-open the earliest invalid gate.

Do not maintain cryptographic approval chains or one-use tokens for ordinary research bookkeeping. Use repository history, signed institutional systems, or preregistration services when stronger authentication or timestamping is genuinely required.

## Imported and retrospective projects

For an existing project:

1. inventory current artifacts and versions;
2. reconstruct the evidence graph;
3. distinguish prospective decisions from choices made after observing data;
4. identify missing raw evidence and unverifiable claims;
5. locate the earliest unsupported gate;
6. propose the smallest recovery plan.

Do not manufacture a clean prospective history. A transparent retrospective record is scientifically stronger than a fictional preregistration.

## External actions

Submission, public release, email, repository publication, reviewer-response transmission, and resubmission are separate actions. Before each action:

- show the exact payload and destination;
- identify material differences from the last approved version;
- confirm authorship and disclosure state;
- obtain explicit authorization for that action;
- record the outcome after it occurs.

Never infer authorization from a general instruction to prepare, revise, or continue.