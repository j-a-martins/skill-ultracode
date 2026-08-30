# Overengineering review

## Objective

Retain controls that materially improve scientific validity, evidence traceability, publication accuracy, or safe external action. Remove controls whose maintenance cost, context burden, or brittleness exceeds their research value.

## Decisions

### Retained

- one concise `SKILL.md` with progressive disclosure;
- four native operating modes rather than separate overlapping skills;
- nine directly linked references organized by scientific task;
- a compact project scaffold created only when useful;
- stable source, run, result, and claim identifiers for complex projects;
- prospective protocols, amendments, and transparent retrospective reconstruction;
- strict local JSON and CSV parsing;
- create-only initialization;
- one project auditor;
- one LaTeX static auditor;
- one prose drift auditor;
- one journal-fit/Q1 record scorer;
- one offline regression suite;
- one deterministic release gate;
- explicit user authorization for external transmission.

### Removed or rejected

- cryptographic approval chains for every project stage;
- one-use authorization tokens and pseudo-ledgers;
- multiple validators implementing substantially the same archive checks;
- dozens of mandatory files for simple tasks;
- fake multi-agent reviewer panels;
- arbitrary aggregate reviewer scores;
- fixed reference-count or figure-count quotas;
- mandatory PICO for nonclinical computer-science questions;
- brittle universal blacklists of academic phrases;
- detector-evasion objectives;
- mandatory web services or third-party Python dependencies;
- automatic submission or public release;
- security hardening unrelated to the actual research threat model.

## Complexity budgets

The release gate enforces:

- `SKILL.md` at or below 500 lines;
- at most 10 reference files;
- at most 7 Python scripts;
- standard-library-only scripts;
- at most 26 files in the full generated workspace;
- one top-level folder in the installable ZIP;
- no README, changelog, installation guide, or quick-reference clutter inside the skill;
- no compiled bytecode or caches;
- direct links from `SKILL.md` to every reference and user-facing script.

## Why the remaining scripts exist

- `init_project.py`: prevents repeated ad hoc scaffold creation and silent overwrite.
- `audit_project.py`: checks cross-file provenance and stage readiness that prose instructions cannot verify reliably.
- `audit_latex.py`: catches unsafe paths, commands, missing files, and key mismatches before compilation.
- `audit_prose.py`: catches high-consequence technical drift during rewriting.
- `score_journals.py`: prevents fit arithmetic from silently conferring Q1 status.
- `self_test.py`: provides a repeatable regression boundary.
- `_common.py`: removes duplicated strict parsing and file-integrity code.

Each script is standard-library-only and optional for tasks where its assurance does not matter.

## Context-efficiency review

The main file contains routing, universal invariants, lifecycle stages, mode minimums, and script entry points. Detailed search, review, prose, design, experiment, manuscript, journal, and integrity guidance loads only when needed.

The imported capabilities are not copied wholesale into the main file. Repeated rules appear once in the evidence contract or the most relevant reference. Standalone modes do not instantiate the full lifecycle unless the request needs it.

## Scientific-value review

The strongest retained controls are:

1. claim-evidence mapping;
2. source-access distinction;
3. prospective versus retrospective decision tracking;
4. preservation of contradictory and negative evidence;
5. mode-specific methodological routing;
6. semantic-drift protection for prose;
7. evidence-anchored peer-review findings;
8. category-specific and dated Q1 verification;
9. exact-payload authorization before external action.

These controls address known failure modes directly. Removing them would reduce trustworthiness more than it would reduce complexity.

## Remaining deliberate redundancy

Some concepts appear in both `SKILL.md` and a reference because they are non-negotiable at trigger time: fabrication prohibition, untrusted document handling, claim calibration, and external-action authorization. This limited repetition is intentional.

The release gate and self-test both inspect structure, but at different boundaries: the self-test guards skill behavior; the release gate guards packaging, portability, clean extraction, and evidence reporting.

## Verdict

The integrated release is intentionally smaller and less administratively complex than the earlier hardened designs. Further consolidation would save little context while weakening mode-specific guidance or deterministic safeguards. Additional scripts, reviewer personas, approval ledgers, or mandatory project files should require a demonstrated failure that the current design cannot address.