# Extended adversarial review — round 3

Date: 2026-08-30

## Scope

This pass reviewed the installable skill, deterministic scripts, generated workspaces, evaluation set, release builder, and prior assurance claims. It did not claim byte-level equivalence to the three original conversation attachments because those attachment bytes were not exposed to the build environment. Their supersession remains capability-level and semantic only.

## Findings and remediation

### Critical: blank structured records could satisfy lifecycle stages

Comma-only CSV rows were parsed as records. Execution, analysis, screening, extraction, review, and revision stages could therefore appear populated without evidence.

**Remediation:** strict CSV parsing now rejects all-empty records, extra fields, duplicate headers, and NUL bytes. Every governed row requires its identifier and stage-specific nonempty fields.

### Critical: gate strings could outrun their evidence

A project could record later gate labels without a contiguous predecessor sequence or the corresponding evidence files.

**Remediation:** schema-v3 state validation rejects duplicate, unknown, missing-predecessor, and future gates. Gate labels are insufficient without pilot, run, result, review, journal, decision, and release records.

### Critical: pilot, acceptance, and archive states were self-asserted

A `pilot`, `accepted`, or `archived` stage could be represented by prose or a state label alone.

**Remediation:** pilots require a dated go/revise/stop decision with hash-bound evidence; accepted status requires a hash-bound editorial decision capture; archived status requires a byte-verified release manifest and correction plan.

### Critical: inactive or malformed records could support active claims

Status typos, candidate sources, unresolved sources, failed results, or superseded results could evade downstream checks.

**Remediation:** source, result, claim, finding, screening, revision, and action statuses use closed enumerations. Active claims reject ineligible sources and inactive results. Retraction controls remain explicit.

### Critical: local Q1 records overstated verification

A broad official-domain URL or arbitrary trusted-domain override could produce `q1_verified` without a journal-specific record, evidence capture, or human check.

**Remediation:** the custom trusted-domain override was removed. Recognized providers use narrow platform domains, bare home pages are rejected, evidence captures and hashes are mandatory, verifier and timestamp are mandatory, duplicate records are rejected, metric age is bounded, and output states the local-only assurance scope.

### Critical: BibTeX pseudo entries could spoof citation keys

`@comment`, `@string`, embedded `@article` text, and duplicate keys across files could satisfy or confuse citation resolution.

**Remediation:** the LaTeX audit now parses real top-level BibTeX entries, ignores non-entry directives, skips entire balanced entries, rejects malformed records, and detects duplicate keys across bibliographies.

### High: imported TeX files and high-risk packages escaped static review

Common import commands were not followed, and high-risk packages or direct Lua constructs could avoid the previous primitive set.

**Remediation:** the auditor follows braced and unbraced input, include, subfile, import, subimport, inputfrom, and related commands. It rejects path escape, special files, direct Lua, shell escape, raw I/O and PDF primitives, launch actions, and high-risk packages. `\nocite{*}` is handled correctly.

### High: prose audits missed direction and scope reversals

A rewrite could keep every number while changing higher to lower, support to contradiction, before to after, conditional to unconditional, or a narrow citation to another paragraph.

**Remediation:** the strict audit now compares normalized directional, polarity, temporal, evidential, significance, conditional, universal, and restrictive categories; checks citation paragraph placement; protects citation/reference commands and macro inventories; and binds revision rows to original and revised hashes.

### High: run and result provenance was descriptive rather than byte-bound

Version strings could be supplied without proving which raw output or analysis input supported a result.

**Remediation:** complete runs require hash-bound raw outputs and permit hash-bound code, data, and environment manifests. Results bind analysis code and ordered input paths/hashes and may depend only on complete runs when active.

### High: search corpora were not fully reconciled

Search exports, included screening records, extraction rows, version-family deduplication, and flow counts were not cross-checked.

**Remediation:** query exports can be hash-bound; source IDs are checked; full-text included records require extraction rows; dedup clusters require canonical members; and flow counts must be nonnegative and monotonic.

### High: reviews could be closed with invented or malformed findings

Invalid severity or status values could bypass unresolved-major checks, while requiring at least one finding could pressure the system to invent criticism.

**Remediation:** review fields use closed enumerations and require location, evidence, consequence, action, and confidence. Zero findings are valid only when the review explicitly states `No material findings` and supplies a structured recommendation/confidence summary.

### High: external-action records lacked bounded authorization time

An old authorization could be replayed against a later action.

**Remediation:** actions use unique IDs, exact payload hashes, authorizer, statement, timezone-aware authorization and expiry, a maximum 48-hour window, and performed times inside that window. Prepared is not authorized.

### High: workspace trees and archives did not reject every special file

FIFOs, sockets, or devices could be silently omitted or mishandled.

**Remediation:** workspace, manuscript, source, support, release, and extracted trees permit only directories and single-link regular files. Links, hardlinks, bytecode, FIFOs, sockets, and devices fail closed.

### High: release construction had time-of-check/time-of-use and cleanup weaknesses

The release builder used ordinary reads after validation and recursively cleaned a potentially replaced output path.

**Remediation:** the builder uses no-follow descriptor reads with identity and stability checks, a bounded safe cleanup routine, create-only output writes, stable reads for archive members and support artifacts, and byte-for-byte clean-extraction comparison.

### High: installable scripts could acquire network or dynamic execution capabilities unnoticed

Standard-library network clients or `eval`/`exec`/subprocess calls would have passed a third-party-import check.

**Remediation:** AST policy now rejects network/process/unsafe-serialization imports and dynamic/process execution calls in the installable scripts.

### Medium: prior release language exceeded its source-archive evidence

A later narrative implied full inspection even though release records said the uploaded archives were unavailable.

**Remediation:** the validation, manifest, reports, and release summary now use one consistent statement: capability-level semantic supersession only; no line-by-line equivalence, source-code reuse, or license verification is claimed.

## Regression coverage added

Tests now cover blank-record bypasses, schema migration, gate ordering, pilot evidence and stop decisions, inactive evidence, status typos, retraction use, accepted/archive evidence, no-material-findings reviews, invalid findings, search-flow reconciliation, strict prose-file audits, authorization expiry, special files, BibTeX spoofing, cross-file duplicate keys, import traversal, high-risk TeX packages, prose direction reversals, citation movement, malformed provider URLs, evidence mutation, duplicate journal records, and fit-first ranking.

## Residual boundaries

- Static TeX analysis cannot prove arbitrary TeX safe; restricted compilation and rendered inspection remain required.
- Strict prose analysis cannot prove complete semantic equivalence; human scientific review remains required.
- Local hashes do not authenticate remote provider pages or human identities.
- Search completeness is relative to the protocol, sources, access, and date.
- Structural integrity does not establish scientific validity, ethics approval, authorship eligibility, acceptance, or publication.
- Original source-archive bytes remain uninspected in this build environment.
