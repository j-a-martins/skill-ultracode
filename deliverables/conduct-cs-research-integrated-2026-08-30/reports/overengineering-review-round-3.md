# Overengineering review — round 3

Date: 2026-08-30

## Review question

Does the final hardening add complexity that exceeds its scientific or integrity value, duplicate another capability, or make bounded academic tasks unnecessarily administrative?

## Retained architecture

The installable skill retains:

- one `SKILL.md` router;
- four operating modes;
- nine directly linked references;
- six user-facing standard-library scripts plus one shared module and one regression runner;
- no nested skill, plugin loader, database, scheduler, network client, model wrapper, vector store, package manager, or background daemon;
- no imported source-skill executables or raw prompts;
- no generic PDF, DOCX, spreadsheet, slide, image, or repository implementation.

The consolidated skill continues to delegate generic artifact operations to the environment’s dedicated skills.

## Complexity added in this pass

Schema-v3 workspaces add concrete pilot, review-summary, decision, release, deduplication, and flow records. The full scaffold contains 30 files, systematic search 14, peer review 8, and scientific prose 6. These are maximum persistent scaffolds, not mandatory output for conversational tasks.

The larger project auditor centralizes validation that would otherwise be duplicated across four mode-specific auditors. It uses small domain functions and one shared path/record layer. The release gate enforces a largest-function bound and a fixed script/reference count.

## Complexity removed or rejected

The design still rejects:

- autonomous paper-writing or submission agents;
- fake multi-reviewer panels;
- cryptographic signatures, Merkle trees, blockchains, or append-only ledgers;
- reusable authorization tokens or multi-stage nonce chains;
- a universal quantitative quality score;
- fixed numbers of searches, citations, reviewers, experiments, figures, or revisions;
- mandatory PRISMA or PICO for focused computer-science searches;
- separate packages for prose, search, and peer review;
- a database-backed evidence graph;
- remote journal-metric retrieval inside the skill;
- scholarly API clients and credential storage;
- automatic installation or execution of research code;
- duplicate user documentation such as README, installation guide, quick reference, or changelog.

## Proportionality controls

The router requires the narrowest mode. A two-sentence edit should return a two-sentence edit. A request for three papers should use a focused search, not a systematic-review scaffold. A peer review may contain zero findings when the evidence supports that outcome. A workspace is created only when durable state, handoff, or auditability justifies it.

The release gate fixes explicit file-count budgets by mode and rejects accidental scaffold growth. It also limits reference and script counts, requires direct links from `SKILL.md`, checks long references for navigation, and rejects undeclared top-level files.

## Why the remaining controls are justified

The retained additional records each close a demonstrated bypass:

- pilot decision prevents a stage label from replacing feasibility evidence;
- editorial decision prevents inferred acceptance;
- release manifest prevents an archival label from replacing byte identity;
- review summary separates recommendation from confidence without forcing invented findings;
- deduplication and flow records prevent inflated or irreconcilable reviews;
- file hashes prevent a ledger from referring to different bytes than the artifact under review;
- strict status enumerations prevent typos from bypassing safeguards;
- short-lived exact-payload authorization prevents routine stage approval from becoming submission permission.

These controls are local, standard-library, optional until the relevant stage, and inspectable without a service dependency.

## Remaining deliberate non-automation

Human judgment remains mandatory for:

- novelty and search sufficiency;
- study validity and statistical adequacy;
- ethics and authorship;
- semantic equivalence of substantive prose revisions;
- journal fit and interpretation of licensed ranking data;
- confidential-review policy;
- final rendered manuscript quality;
- submission, payment, public release, correction, and retraction decisions.

## Conclusion

The third-pass remediation increases deterministic code and a full-lifecycle scaffold from 25 to 30 files, but each addition corresponds to a previously demonstrated false-pass class. Bounded modes remain small, no remote infrastructure was added, and administrative requirements activate only at relevant stages. No material component was identified whose maintenance cost exceeded its risk-reduction value.
