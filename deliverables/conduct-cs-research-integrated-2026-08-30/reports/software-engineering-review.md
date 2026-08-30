# Full software-engineering review

## Scope

Review the installable skill as production software: instruction architecture, progressive disclosure, runtime modules, data contracts, filesystem safety, CLI behavior, tests, packaging, CI, maintainability, and failure semantics. Benchmark the skill against OpenAI's `skill-creator` at commit `49f948faa9258a0c61caceaf225e179651397431` and `SKILL.md` blob `72bc0b97e7a6476254a9d5c424c9971748402ec3`.

## Findings

### High: the core instruction file duplicated its delegated workflow

The prior `SKILL.md` contained a fourteen-stage lifecycle even though `references/workflow.md` already owned lifecycle gates, rollback, external actions, and archive semantics. Every bounded prose, review, or search task therefore loaded lifecycle instructions it did not need. This increased token cost and created two places that could drift.

**Remediation:** replace the repeated lifecycle with a compact routing and execution contract. Require bounded modes to load one task reference, and require the full lifecycle to load `workflow.md` plus only the current stage reference.

### High: the regression suite shipped as runtime skill content

`self_test.py` was large development infrastructure, not a runtime research capability. Shipping it increased archive size, code-review surface, context-discovery noise, and the number of executable files.

**Remediation:** move the suite to `tests/self_test.py` outside the installable folder. The release gate temporarily injects the exact test file into a source or clean-extraction copy, runs it with bytecode disabled, and removes it before source-set and archive validation. The installable skill contains six runtime modules, not the test harness.

### Medium: token efficiency had only permissive structural bounds

The prior gate enforced fewer than 500 lines, at most ten references, and at most seven scripts. These are useful ceilings but do not constrain real task-time context.

**Remediation:** add word budgets for `SKILL.md`, the total reference corpus, each bounded mode's initial load, and the full lifecycle's active-stage load. Add an exact long-paragraph duplication check between the core file and references.

### Medium: CLI compatibility was implicit

Scripts used `argparse`, but release validation did not verify every public helper's `--help` behavior or that help execution was side-effect free.

**Remediation:** execute every public helper with `--help`, require a zero exit and usage contract, and compare the complete skill tree before and after.

### Medium: Python-version coverage was narrow

The previous workflow ran the package gate on Python 3.12 only.

**Remediation:** run the complete release gate on Python 3.11 and 3.12 before the packaging job, then run it again for the uploaded artifact.

### Medium: official-format compatibility was implemented but not independently exercised

The existing validator enforced the official frontmatter and naming constraints but did not run OpenAI's current `quick_validate.py` itself.

**Remediation:** pin the official `openai/skills` commit in CI and run its validator against the final source before packaging. PyYAML is a build-only dependency; the installable skill remains standard-library only.

## Runtime architecture decision

Do not split `audit_project.py` merely because it is the largest module. It contains a cohesive orchestration layer over mode-specific validators, uses explicit schemas and pure validation helpers, and remains inside the existing function-size bound. Splitting it now would increase cross-module coupling and import surface without a demonstrated correctness or testability benefit. Reconsider only if a new mode or schema change creates independent ownership boundaries.

## Resulting architecture

- One compact router and operating contract in `SKILL.md`.
- Nine one-level, directly linked references loaded conditionally.
- Six standard-library runtime Python modules.
- One external regression suite used only by the build gate.
- One deterministic release path with source, alternate-hash-seed, clean-extraction, archive, capability, token, and CLI checks.
- No database, plugin framework, network client, package manager, model wrapper, or autonomous background service inside the skill.
