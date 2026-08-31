# Extended adversarial review — round 4

## Threat model

This pass focused on defects that could survive ordinary happy-path testing: filesystem races, parser ambiguity, lifecycle laundering, evidence substitution, ranking ambiguity, resource exhaustion, archive aliasing, and misleading success semantics.

## Adversarial cases and disposition

| Attack | Expected defense | Disposition |
|---|---|---|
| Two initializers target the same path concurrently | Exactly one atomically reserves it; all others fail without replacing bytes | Implemented and regression tested |
| Audit target is a symlink to a valid workspace | Reject the caller-supplied linked root before resolution | Implemented and regression tested |
| Huge tree of small files or deeply nested directories | Fail on explicit entry, depth, or aggregate-byte budget | Implemented and regression tested |
| Stage jumps forward with persuasive prose but missing predecessors | Require the exact ordered predecessor-gate list and stage artifacts | Implemented and regression tested |
| Pilot says `revise` but definitive runs proceed without an amendment | Require completed amendment path and SHA-256 in the pilot decision | Implemented and regression tested |
| Completed run omits code, data, environment, or raw-output binding | Reject the run; it cannot support an active result | Implemented and regression tested |
| Active result depends on a running or failed run | Reject the result-to-run edge | Implemented and regression tested |
| Search flow claims more records than the screening ledger | Reconcile exact screened and full-text sets and counts | Implemented and regression tested |
| Included records and extraction rows differ | Reject synthesis readiness and identify missing or extra IDs | Implemented and regression tested |
| One source appears in several deduplication clusters | Reject ambiguous version-family membership | Implemented and regression tested |
| A claim remains `needs-review` at submission | Reject submission-ready, accepted, and archived states | Implemented and regression tested |
| Disputed major finding is hidden at submission | Reject shipping stage while unresolved | Implemented and regression tested |
| Accepted manuscript retains an open response item | Reject acceptance readiness | Implemented and regression tested |
| Q1 row has no ISSN or a bad checksum | Keep fit score but reject verified-Q1 status | Implemented and regression tested |
| Journal has several legitimate category rows | Preserve all observations; require exact tuple only for a verified selected claim | Implemented and regression tested |
| Provider homepage is offered as ranking evidence | Require a journal-specific authoritative HTTPS record and hash-bound capture | Implemented |
| BibTeX comment contains a fake nested entry | Ignore comment/string/preamble bodies; parse only top-level records | Implemented and regression tested |
| Same BibTeX key occurs in two files | Reject duplicate bibliography identity | Implemented and regression tested |
| TeX uses direct Lua, shell escape, raw file I/O, or path escape | Reject before compilation; still require restricted compilation and visual review | Implemented and regression tested |
| Authorized payload changes after approval | Recompute payload SHA-256 and reject stale authorization | Implemented and regression tested |
| ZIP uses traversal, case aliases, Unicode aliases, device names, links, encryption, or expansion abuse | Reject archive before extraction | Implemented in release gate |
| Build emits a clean narrative despite failed checks | Release builder exits nonzero and emits no ready marker | Implemented |

## Residual risks

Static analysis cannot prove arbitrary TeX safe or prose semantically equivalent. Local hashes do not authenticate remote providers or human approvers. Search completeness remains protocol- and coverage-relative. Model-level trigger behavior still requires runtime evaluation after installation. These are stated as assurance boundaries rather than represented as passed machine checks.
