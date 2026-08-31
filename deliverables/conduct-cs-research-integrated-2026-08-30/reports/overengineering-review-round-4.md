# Overengineering review — round 4

## Decision

The final architecture is proportionate to the skill's broad academic scope. Complexity was retained only where a silent error would corrupt scientific evidence, workflow state, exact payload authorization, or release integrity.

## Removed or rejected complexity

- No database, vector store, scheduler, background daemon, plugin framework, dependency-injection container, or agent swarm.
- No third-party runtime dependency and no bundled scholarly-network client.
- No cryptographic signature theater, Merkle tree, blockchain, nonce registry, or chained approval ledger for ordinary research stages.
- No separate installed sub-skills or competing orchestrators for search, prose, peer review, and the full lifecycle.
- No duplication of PDF, DOCX, slide, spreadsheet, image, browser, or repository tooling.
- No bundled test suite, build script, report corpus, README, changelog, installation guide, or quick-reference document in the installable skill.
- No journal-specific template collection and no timeless ranking table.
- No generic scalar research-quality score that averages incompatible judgments.
- No automatic submission, upload, correspondence, payment, or publication action.

## Retained complexity and rationale

The nine reference modules remain separate because merging them would make bounded tasks load irrelevant methodology. Further splitting would increase routing overhead without material context savings.

The runtime package uses small modules with explicit roles:

- `_common.py`: strict local I/O, hashing, path confinement, and bounded traversal;
- `_project_model.py`: schemas, modes, stages, status vocabularies, and gate mappings;
- `_project_records.py`: row- and artifact-level validation;
- `_project_stages.py`: stage readiness and shipping conditions;
- `audit_project.py`: orchestration and CLI;
- `audit_latex.py` plus a private parser implementation: root protection and static manuscript checks;
- `audit_prose.py`: protected-content and semantic-drift heuristics;
- `score_journals.py`: fit scoring and local category-specific ranking evidence;
- `init_project.py`: proportional, create-only scaffolding.

The private module count is not capped arbitrarily. Release blockers instead target unused resources, excessive always-loaded content, large or highly branching functions, duplicated responsibility, unsafe imports, and development artifacts in the installed tree.

## Token efficiency

`SKILL.md` is budgeted to at most 800 words, 8,000 UTF-8 bytes, and 120 lines. A bounded request loads exactly one primary reference initially. Full-lifecycle work loads `workflow.md` first and one stage-specific reference as the active stage changes. The release gate also enforces per-route and full-active-stage word budgets plus a total reference budget. This preserves progressive disclosure instead of optimizing only file count.

## Conclusion

The remaining machinery is justified by deterministic integrity requirements. Removing it would reintroduce known silent-failure modes; adding generalized infrastructure would increase maintenance and token cost without improving the user's research outcome.
