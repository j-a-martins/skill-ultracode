# Final independent verification review

Date: 2026-08-31

## Scope

This pass independently reviewed the software-engineered `conduct-cs-research` release rather than accepting its prior validation summary. It compared the installable tree and release pipeline with the current OpenAI `skill-creator` specification and `quick_validate.py`, then inspected runtime validators, regression coverage, progressive disclosure, token budgets, filesystem handling, provenance rules, systematic-search state, peer-review completion, scientific-prose preservation, journal verification, and deterministic packaging.

## Findings remediated

1. **Screening validation depended on CSV row order.** A valid full-text row preceding its title-and-abstract row was rejected. Screening rows are now normalized before validation, while duplicate and contradictory records still fail.
2. **Screening identity could drift between stages.** A record could refer to one source family at title-and-abstract screening and another at full-text screening. Cross-stage source sets must now agree.
3. **An `included` source could support an active claim without a hash-bound verified record.** Active claims may now rely on source evidence only when the source status is `verified` or `corrected`; retracted evidence retains its separate, explicit handling.
4. **Systematic-search completion could retain `needs-review` claims.** Internal-review and archived search states now reject unresolved synthesis claims.
5. **Scientific-prose auditing used aggregate semantic counts.** Opposite directional terms could be swapped between claims while preserving global counts. Strict auditing now checks ordered semantic events and paragraph ownership.
6. **The protected-spans record was procedural rather than executable.** Governed revision audits now parse exact literal spans, bind original and revised bytes to their recorded SHA-256 values, and require each protected span to remain present with the same occurrence count.
7. **Project-relative hash checks could follow a replaced intermediate path component.** On platforms supporting directory-relative opens, file access now walks from an opened project-root descriptor with no-follow semantics. Portable path aliases are also rejected.
8. **The release builder could package source bytes read after validation without a stable snapshot.** The revised release gate captures a checked source snapshot, builds both deterministic archives from that snapshot, and tests the clean extraction of the same bytes.
9. **Evaluation validation accepted arbitrary list element types.** Expected and forbidden behaviors must now be strings, and non-finite JSON is rejected.

## Architecture conclusion

The main skill remains appropriately compact and route-first. No additional orchestrator, plugin system, database, agent swarm, network client, or nested skill was introduced. The nine one-level references remain the correct progressive-disclosure boundary; merging them would increase irrelevant context, while further splitting would add routing overhead. Development tests and release evidence remain outside the installable skill.

## Assurance boundary

Passing deterministic checks establishes internal consistency and package integrity only. It does not prove scientific validity, novelty, complete search recall, semantic equivalence, ethics approval, authorship eligibility, current journal ranking, acceptance, or publication. Static TeX inspection still requires restricted compilation and rendered-output review. Concurrent mutation by a process with equivalent local privileges cannot be made impossible by a portable user-space audit, but descriptor-relative access and byte-bound checks materially reduce path-replacement risk.
