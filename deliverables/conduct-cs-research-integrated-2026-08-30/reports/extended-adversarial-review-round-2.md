# Extended adversarial review: second pass

## Scope

This pass began after the first clean GitHub Actions run reached the executable release boundary. It targeted discrepancies between documented guarantees and actual package behavior, cross-mode proportionality, evidence semantics, journal decisions, semantic-drift boundaries, parser edge cases, build reproducibility, and archive contents.

## Blocking findings and resolutions

| Severity | Finding | Resolution |
|---|---|---|
| Critical | Running the regression suite created `__pycache__` files after the source inventory, and those files entered the installable ZIP. The 18-file source inventory therefore produced a 24-member archive. | Tests now run with `-B` and `PYTHONDONTWRITEBYTECODE=1`; the gate rejects bytecode before packaging, checks that validation does not change the source file set, requires archive-member count to equal validated source-file count, and repeats the check after clean-extraction tests. |
| Critical | The journal scorer sorted verified Q1 records ahead of scientific fit, contradicting the stated fit-first policy. A poor-fit Q1 title could outrank a strong-fit non-Q1 title. | Default ranking is now scientific fit first. Verified Q1 is an independent field and an explicit `--verified-q1-only` filter, not an implicit ranking bonus. |
| Critical | Any HTTPS URL could make a Q1 record appear verified when no trusted-domain argument was supplied. | Verification now requires a provider-specific authoritative domain by default: Clarivate/Web of Science for JCR, Scopus/Elsevier for CiteScore, and SCImago for SJR. Additional domains require an explicit operator override. |
| High | Standalone peer-review and prose workspaces inherited most lifecycle files, despite the skill promising narrow modes. | Initialization is now mode-proportionate: 25 files for the full lifecycle, 12 for systematic search, 7 for peer review, and 6 for scientific prose. Each mode has its own stage vocabulary and gate audit. |
| High | A performed external action needed only a destination and timestamp; it was not bound to exact payload bytes. | Authorized, performed, and failed actions now require a nonempty action, destination, authorization time, and a list of project-relative payload paths with SHA-256 values. The auditor recomputes each hash. Performed or failed actions also require outcome and performance time. |
| High | An active claim could silently depend on a retracted source. | Active claims using retracted records must disclose the retraction. A retracted record cannot be the sole support for a non-retraction claim. Claims about the fact of retraction remain representable. |
| High | Manuscript marker checks included withdrawn and superseded claims. | Only active claims require manuscript markers. Withdrawn, rejected, and superseded claims remain in the ledger without forcing obsolete prose. |
| High | File inspection used path-level checks before ordinary reads, leaving a path-replacement race. | Shared file reads and hashes now open with no-follow semantics where available, compare `lstat` with descriptor identity, reject links and nonregular files, and verify the descriptor snapshot after reading. |
| High | The prose audit missed leading decimals, Unicode minus signs, inequality reversal, several citation commands, citation optional arguments, and punctuation-only DOI/URL movement. | Protected-token handling now covers leading decimals, Unicode signs, comparison operators, extended units, common natbib/biblatex citation forms, complete citation commands, and normalized sentence punctuation for DOI and URL tokens. |
| High | The LaTeX audit missed common optional-argument citation forms and direct Lua execution. | Citation parsing now handles common natbib and biblatex commands with optional arguments. Direct Lua execution is rejected alongside shell and unsafe file primitives. |
| High | Evaluation records and rubric files were copied without structural validation. | The release gate strictly parses the rubric and every JSONL record, rejects duplicate keys and IDs, validates mode/severity/assertion fields, and enforces minimum total and critical-case coverage. |
| High | The deterministic ZIP was not independently rebuilt and compared. | The gate now builds the archive twice and requires byte identity and matching SHA-256 before clean extraction. |
| Medium | GitHub Actions dependencies used floating major-version tags. | Workflow actions are pinned to the exact resolved commits used by the successful baseline runner. |
| Medium | Common helpers included functionality that was not connected to a control. | SHA-256 is now used for payload binding; obsolete formula-cell generation was removed. Every remaining helper has a concrete caller. |

## Additional test coverage

The regression suite now covers:

- exact per-mode workspace budgets;
- full-lifecycle, systematic-search, peer-review, and prose stage semantics;
- active versus withdrawn claims;
- retracted-source disclosure and sole-support rejection;
- external payload hashing and post-authorization mutation;
- duplicate and nonfinite JSON;
- malformed and duplicate-header CSV;
- symlinks and hardlinks;
- optional citation arguments in prose and LaTeX;
- percentage punctuation, leading decimals, Unicode minus, inequalities, DOI/URL punctuation, code spans, units, math, negation, uncertainty, and causal strength;
- authoritative provider domains, category and date completeness, fit-first ranking, and explicit verified-Q1 filtering;
- bytecode leakage, source-set mutation, deterministic rebuilds, archive portability, clean extraction, and evaluation-data structure.

## Assurance limits

- Token and regex audits are conservative safeguards, not proofs of semantic equivalence.
- Provider-domain checks establish source identity plausibility, not cryptographic attestation of a remote page or licensed database record.
- Project payload hashes detect changed local bytes but do not authenticate the approving human.
- Static TeX checks do not make arbitrary TeX safe; restricted no-shell-escape compilation remains mandatory.
- Search completeness, scientific validity, reviewer agreement, and publication outcomes remain human scientific judgments.
- The three user-supplied ZIP archives were not byte-inspected because the conversation attachment runtime remained unavailable.