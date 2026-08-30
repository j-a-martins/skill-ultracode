# Research workflow and gates

## Contents

1. Operating principle
2. Mode selection and proportionality
3. Schema-v3 workspace
4. Full-lifecycle gates
5. Bounded-mode gates
6. Evidence graph and rollback
7. External actions
8. Acceptance, release, and correction
9. Audit semantics

## Operating principle

Use a goal → plan → execute → verify → reflect loop. Verification must rest on inspectable evidence: source records, content hashes, protocol status, run outputs, statistical diagnostics, compile results, policy pages, or explicit human decisions. A model’s own confidence is not a completion signal.

Stop when evidence is missing, the next step would change scientific scope, authorization is required, or the cost no longer matches the expected value. Do not manufacture artifacts merely to advance a stage.

## Mode selection and proportionality

Choose the narrowest mode:

- full research lifecycle;
- systematic search;
- peer review;
- scientific prose.

A bounded conversational task may need no workspace. Create a workspace when durable cross-artifact state, reviewability, handoff, or later audit justifies it.

## Schema-v3 workspace

Initialize with:

```text
python scripts/init_project.py OUTPUT --name NAME --mode MODE
```

The initializer publishes the directory atomically and refuses to replace an existing target. New workspaces use schema version 3. Do not treat an older workspace as audited until it is migrated to the current fields and evidence semantics.

Every stage change in `state.json` must:

- use a stage allowed for the project mode;
- include every predecessor gate exactly once;
- include no future or unknown gate;
- update `updated_at` with a timezone-aware timestamp.

A gate label is only an index into the workflow. It does not substitute for the required evidence files.

## Full-lifecycle gates

### Question

Require a completed charter defining objective, contribution, boundaries, governance, confidentiality, authorship, ethics, AI use, and stop conditions.

### Protocol

Require a prospective or explicitly retrospective protocol with study family, inputs, sampling, baselines, outcomes, analysis, robustness, stopping, reporting, and amendment process.

### Pilot

Require `study/pilot-decision.json` with:

- `go`, `revise`, or `stop`;
- timezone-aware decision time;
- protocol effect;
- one or more project-relative evidence paths and SHA-256 values.

Do not advance past `stop`. A `revise` decision must be reflected in the amendment record before definitive execution.

### Execution

Require at least one complete definitive or replication run. Each complete run must identify code, data, environment, parameters, start/end times, and hash-bound raw output. Planned, running, failed, cancelled, pilot, or exploratory records do not alone satisfy execution.

### Analysis

Require at least one active, reported, or confirmed result linked to complete runs. Record analysis code, input hashes, estimate, uncertainty, robustness, deviations, and status. A failed, withdrawn, or superseded result cannot support an active claim.

### Manuscript

Require active evidence-linked claims, recoverable `claim:C####` locations, no placeholders, and a passing static LaTeX/BibTeX audit. Static audit is followed by restricted no-shell-escape compilation and rendered-output inspection when tooling is available.

### Internal review

Require a completed review and structured summary containing scope, recommendation, confidence, and limitations. Findings must be evidence-backed and use valid severity and status values. If no material finding exists, state `No material findings`; do not invent one to populate a table.

### Journal selection

Require candidate records and one selected-journal record. Scientific fit remains independent of Q1. A `verified` Q1 claim must match exactly one current, category-specific, hash-bound candidate evidence record.

### Submission package

Require current journal instructions, exact package inventory, disclosures, author approval, and destination. This gate means the package is prepared; it is not authorization to transmit.

### Revision

Require one response-matrix row per reviewer or editor point. Implemented or verified rows identify the exact manuscript change and evidence. New evidence receives the same provenance and claim audit as original evidence.

### Accepted

Require `publication/decision.json` with accepted status, venue, timezone-aware decision time, and a hash-bound local capture of the editorial decision. Do not infer acceptance from correspondence, portal status remembered by the model, or user intent.

### Archived

Require a release manifest whose local artifacts and hashes match current bytes, licenses and archival times are recorded, and a correction or retraction response plan is complete.

## Bounded-mode gates

### Systematic search

The stage sequence is protocol → search → screening → extraction → synthesis → internal review → archived. Required evidence includes exact query logs, hash-bound exports or documented alternatives, deduplication clusters, screening decisions and exclusion reasons, extraction rows for every included full-text record, reconciled flow counts, active source-linked synthesis claims, and a search audit.

### Peer review

The sequence is review → final → archived. Require a review charter, manuscript reconstruction, evidence-backed findings or an explicit no-material-findings outcome, and a structured recommendation/confidence summary. Final state cannot contain open or partly addressed design-limiting or major findings.

### Scientific prose

The sequence is revision → final → archived. Every revision record binds the original and revised paths and hashes, records protected content and material changes, and runs the strict drift audit. Manual acceptance of deterministic warnings requires a specific rationale and residual-risk record.

## Evidence graph and rollback

Use stable IDs and explicit foreign keys. A downstream item is invalid when a required upstream item is missing, ineligible, failed, withdrawn, superseded, or changed without re-audit.

Typical trace:

```text
source S0007 → decision D0003 → run E0012 → result R0004 → claim C0005
```

When a source is retracted, a run is invalidated, an analysis changes, or a citation is corrected:

1. identify all directly dependent records;
2. invalidate or mark them for review;
3. roll back to the earliest affected gate;
4. re-run the relevant analysis, prose, citation, and manuscript checks;
5. record the decision and residual uncertainty.

Do not preserve a clean status by changing only the narrative.

## External actions

External actions include submission, upload, email, reviewer response, resubmission, public repository release, data publication, and payment.

Each action record uses a unique `A####`, exact action, exact destination, and a nonempty payload list of project-relative paths and SHA-256 values. Authorization must identify the authorizer, explicit statement, timezone-aware authorization time, and expiry no more than 48 hours later. Performed or failed actions record time and outcome inside that window.

Prepared is not authorized. A protocol, manuscript, or stage approval cannot authorize a later payload. If any byte changes, obtain new authorization.

Local records do not cryptographically authenticate the human authorizer; execution environments must still enforce the interaction-level confirmation.

## Acceptance, release, and correction

Before release, inspect:

- secrets, personal and participant data;
- consent and data-use restrictions;
- copyright and third-party assets;
- software, data, model, and documentation licenses;
- identifiers, versions, checksums, and archival locations;
- authorship and disclosures;
- correction, withdrawal, and retraction routes.

A public URL does not prove archival preservation, and a local hash does not authenticate the remote host. Record both local integrity and external status honestly.

## Audit semantics

`audit_project.py` verifies specified schema, timestamps, enums, paths, hashes, cross-links, stage evidence, LaTeX structure, local Q1 records, and revision drift. It cannot establish:

- novelty or universal search completeness;
- construct, internal, external, or causal validity;
- adequate power or correct statistical judgment;
- ethics approval or authorship eligibility;
- remote-source authenticity or human identity;
- journal fit, acceptance, indexing, or future Q1 status.

Report audit PASS as “no specified integrity defect detected,” not “scientifically valid,” “publication ready,” or “guaranteed acceptable.”
