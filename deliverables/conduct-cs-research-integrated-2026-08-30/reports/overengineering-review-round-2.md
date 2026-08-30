# Overengineering review: second pass

## Question

Does each retained artifact or control reduce a material research, integrity, publication, or execution risk, and is its cost proportionate to the mode that invokes it?

## Mode-proportionate design

The first integrated scaffold remained too lifecycle-shaped for bounded tasks. It has been replaced with explicit budgets:

| Mode | Generated files | Included control surface |
|---|---:|---|
| Full research lifecycle | 25 | governance, protocol, search, executions, claims, manuscript, review, prose revision, journals, submission |
| Systematic search | 12 | governance, search protocol, amendments, sources, searches, screening, extraction, synthesis, audit, claims |
| Peer review | 7 | governance, sources, review narrative, findings, response matrix |
| Scientific prose | 6 | governance, protected spans, revision log, residual concerns |

A bounded request need not initialize any workspace. These are maxima for tasks that benefit from persistent records.

## Controls retained after challenge

- One 171-line routing and invariant file rather than four overlapping skills.
- Nine one-level references because search, review, prose, study design, experiments, manuscript, journal, integrity, and workflow have materially different failure modes.
- Seven standard-library scripts, including one shared helper and one regression suite.
- One release validator rather than multiple validators with overlapping claims.
- Mode-specific stage models instead of forcing the 13-stage publication lifecycle everywhere.
- Exact payload hashing only for external-action records, where version confusion has direct consequences.
- Strict parsing and link-safe reads for governed local evidence, where silent parser or path ambiguity can corrupt provenance.
- A Q1 verifier that checks record completeness and authoritative domain but does not scrape or authenticate commercial metrics.
- Conservative prose and TeX audits followed by mandatory human review.

## Controls removed or rejected

- Per-stage cryptographic approval chains and one-use authorization tokens.
- A universal project scaffold for every mode.
- A second independent archive validator duplicating the same implementation.
- Network clients, database SDKs, browser automation, and commercial-index credentials inside the skill.
- A general BibTeX parser or TeX interpreter.
- Model-based semantic-equivalence scoring presented as proof.
- Autonomous submission, correspondence, release, or purchase.
- Multi-agent reviewer simulations described as independent experts.
- Fixed citation, figure, page, effect-size, or reviewer-count quotas.
- A universal quality score that averages unlike scientific dimensions.

## Script necessity review

- `init_project.py`: now pays for itself by creating four materially different minimal workspaces and refusing overwrite.
- `audit_project.py`: checks mode-specific gates, provenance links, retractions, open review findings, revision status, and exact external payloads.
- `audit_latex.py`: checks unsafe primitives, root confinement, included files, bibliography keys, labels, citations, and logs.
- `audit_prose.py`: protects numerical, symbolic, citation, code, identifier, polarity, uncertainty, and causal content.
- `score_journals.py`: prevents fit scores from conferring Q1 status and prevents Q1 from silently outranking fit.
- `self_test.py`: exercises the installed skill without third-party dependencies.
- `_common.py`: centralizes strict parsing and descriptor-level file integrity used by multiple scripts.

Removing any one of these would either duplicate substantial logic or eliminate a control tied to a demonstrated failure.

## Release complexity budget

The release gate now enforces:

- `SKILL.md` at or below 500 lines;
- at most 10 reference files and 7 scripts;
- direct links to every reference and user-facing script;
- standard-library-only imports;
- the mode budgets above;
- no bytecode, caches, auxiliary README, changelog, or installation clutter;
- exactly one skill folder in the installable archive;
- source-file and archive-member equality;
- two byte-identical archive builds;
- clean extraction with the complete suite rerun;
- a structurally valid evaluation dataset of at least 50 cases.

## Residual complexity

The script and reference bodies are substantial because the merged domain spans multiple study families, reproducible search, peer review, technical prose, LaTeX, journal metrics, and publication ethics. Progressive disclosure prevents most of that material from entering context for a bounded task.

Further consolidation would mostly create large mixed-purpose files, reduce targeted loading, or couple unrelated controls. Further expansion should require a reproducible failure that cannot be addressed by an existing mode or audit.