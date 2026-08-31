# Software-engineering remediation

## Scope

This remediation addresses the release-blocking findings from the full software-engineering review of `conduct-cs-research`. The governing objective is a small, progressively disclosed OpenAI skill whose deterministic controls are explicit, bounded, portable, and independently testable outside the installable package.

## Architecture changes

The installable skill now separates four concerns:

1. `SKILL.md` performs trigger selection, narrow-mode routing, invariant declaration, and resource discovery only.
2. Nine one-level reference modules hold detailed research procedures and are loaded only when the active task requires them.
3. Standard-library runtime modules implement create-only workspace initialization, strict research-record validation, bounded LaTeX inspection, scientific-prose drift detection, and journal evidence scoring.
4. Build tools, regression tests, evaluation cases, and release reports remain outside the installable tree.

The former project-audit monolith was decomposed into `_project_model.py`, `_project_records.py`, `_project_stages.py`, and a small `audit_project.py` orchestrator. This is a cohesive module split, not a plugin system. The LaTeX public entry point similarly protects the caller-supplied root before delegating detailed parsing to a private implementation module.

## Correctness remediations

- The initializer atomically reserves the final target directory with `mkdir(exist_ok=False)`. It no longer uses a replace-capable rename after a time-of-check/time-of-use window. Safe cleanup requires the original device and inode identity plus an expected-tree check.
- Project and LaTeX auditors reject linked roots before canonicalization. Tree traversal is bounded by entry count, relative depth, and aggregate regular-file bytes; links, hardlinks, and special files fail closed.
- Lifecycle state uses schema version 3 and an exact ordered predecessor-gate sequence. Missing, duplicate, reordered, future, or unknown gate names fail.
- Complete runs bind code, data, environment, parameters, terminal times, and raw output. Active results bind complete runs, analysis code or an explicit noncomputational status, ordered inputs, hashes, estimate, uncertainty, and robustness.
- Pilot `stop` blocks execution. Pilot `revise` binds the completed protocol amendment bytes before definitive execution.
- Search flow exactly reconciles screened, full-text-assessed, and included counts with the screening ledger; the included record-ID set must equal the extraction record-ID set.
- Deduplication membership is globally unique. One source cannot occur in several version-family clusters.
- Shipping stages reject claims still marked `needs-review`, unresolved design-limiting or major findings, and open or planned reviewer-response items.
- Q1 evidence requires a checksum-valid ISSN. Multiple subject-category observations are supported, while a verified destination selects one exact journal, ISSN, provider, metric year, category, and evidence hash.
- The LaTeX audit ignores non-entry BibTeX constructs, detects duplicate keys across files, follows import families, confines paths, and rejects unsafe primitives and high-risk execution packages.

## Release engineering

One authoritative `tools/release.py` replaces layered release wrappers and runtime monkey-patching. It performs source-tree policy checks, token budgets, AST import and side-effect checks, function-size and branch budgets, evaluation validation, official OpenAI validator provenance and execution, two hash-seed test runs, deterministic dual ZIP construction, portable archive validation, clean extraction, byte-for-byte comparison, and the full regression suite against the extracted skill.

The installable ZIP excludes tests, caches, reports, build tools, package-manager manifests, and auxiliary user documentation. The CI compatibility matrix covers Python 3.10, 3.12, and 3.13 on Ubuntu 24.04; packaging uses one exact Python patch release.

## Assurance boundary

These controls establish the specified local integrity and release properties. They do not establish scientific validity, novelty, adequate power, ethics approval, authorship eligibility, remote evidence authenticity, journal acceptance, or future ranking status.
