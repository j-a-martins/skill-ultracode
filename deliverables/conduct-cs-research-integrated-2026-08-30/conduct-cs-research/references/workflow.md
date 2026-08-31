# Research workflow and gates

## Contents

1. Operating principle
2. Workspace and gate semantics
3. Full lifecycle
4. Bounded modes
5. Rollback and external actions
6. Audit boundary

## Operating principle

Use a goal → plan → execute → verify → reflect loop. Accept a stage only on inspectable evidence: source records, hashes, protocol status, run outputs, diagnostics, compile results, current policy sources, or an explicit human decision. Model confidence is not evidence.

Choose the narrowest mode. A bounded conversational task may need no workspace. Initialize durable state only when cross-artifact provenance, handoff, later audit, or external action justifies it.

## Workspace and gate semantics

Initialize with:

```text
python scripts/init_project.py OUTPUT --name NAME --mode MODE
```

The initializer atomically reserves the final directory and refuses an existing target. It then uses create-only writes. An interrupted initialization may leave a partial reserved directory; inspect or remove it deliberately rather than retrying with overwrite semantics.

New workspaces use schema version 3. Every state transition must use an allowed stage and the exact ordered predecessor-gate sequence—no omissions, duplicates, reordering, future gates, or unknown names. A gate label indexes the workflow; it does not replace the required evidence.

## Full lifecycle

- **Question:** complete the charter: objective, contribution, boundaries, governance, confidentiality, authorship, ethics, AI use, and stop conditions.
- **Protocol:** record study family, inputs, sampling, comparators, outcomes, analysis, robustness, stopping, reporting, and prospective or retrospective status.
- **Pilot:** bind `go`, `revise`, or `stop` to dated evidence. `stop` blocks execution. `revise` must bind the completed `protocol/amendments.md` bytes before definitive execution.
- **Execution:** require a complete definitive or replication run with terminal timestamps and hash-bound code, data, environment, parameters, and raw output. Use explicit `not-applicable` only when a binding genuinely does not exist.
- **Analysis:** require an active result linked only to complete runs, with analysis code or an explicit noncomputational status, ordered input paths/hashes, estimate, uncertainty, robustness, and deviations.
- **Manuscript:** require evidence-linked claims, recoverable `claim:C####` markers, no placeholders, and a passing static LaTeX/BibTeX audit before restricted compilation and rendered inspection.
- **Internal review:** require a completed review plus structured scope, recommendation, confidence, limitations, and evidence-backed findings. State `No material findings` rather than inventing criticism.
- **Journal selection:** separate scientific fit from ranking. A verified Q1 claim must match one exact journal/ISSN/provider/year/category/evidence-hash observation.
- **Submission package:** record current instructions, exact package, disclosures, approval, and destination. Preparation is not authorization to transmit.
- **Revision:** maintain one response row per reviewer or editor point. Implemented or verified rows bind the change and evidence.
- **Accepted:** bind accepted status to a dated local capture of the editorial decision.
- **Archived:** bind release artifacts, hashes, licenses, archival times, and correction or retraction planning.

`submission-ready`, `accepted`, and `archived` cannot contain `needs-review` manuscript claims, unresolved design-limiting or major findings, or open/planned response items. Revision may retain open items while work is in progress; acceptance may not.

## Bounded modes

### Systematic search

Use protocol → search → screening → extraction → synthesis → internal review → archived. Preserve exact queries, provider state, dated exports or documented alternatives, globally disjoint deduplication clusters, title/abstract and full-text decisions, exclusion reasons, extraction for every included full-text record, exact flow-to-ledger reconciliation, evidence-linked claims, and a search audit.

### Peer review

Use review → final → archived. Require a review charter, manuscript reconstruction, anchored findings or an explicit no-material-findings outcome, and separate recommendation and confidence. Final state cannot contain unresolved design-limiting or major findings.

### Scientific prose

Use revision → final → archived. Bind original and revised bytes, scope, protected content, material changes, residual concerns, and the strict drift result. Manual acceptance of a deterministic warning requires a specific rationale and residual-risk record.

## Rollback and external actions

A downstream record becomes invalid when a required upstream item is missing, ineligible, failed, retracted, withdrawn, superseded, or changed without re-audit. Identify dependents, mark them invalid or for review, return to the earliest affected gate, repeat relevant checks, and retain the decision trail.

Submission, upload, email, reviewer response, resubmission, public release, data publication, and payment require action-specific authorization. Bind `A####`, action, destination, exact project-relative payload paths and SHA-256 values, authorizer, explicit statement, authorization time, and an expiry no more than 48 hours later. Changed bytes require new authorization.

## Audit boundary

`audit_project.py` checks defined schemas, enums, timestamps, paths, hashes, links, stage evidence, local Q1 records, LaTeX structure, and revision drift. PASS means no specified integrity defect was detected. It does not prove novelty, search completeness, validity, power, ethics approval, authorship eligibility, remote authenticity, acceptance, indexing, or future Q1 status.
