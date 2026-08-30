# Token efficiency and OpenAI skill-creator compliance

## Benchmark

The review uses OpenAI `skill-creator` commit `49f948faa9258a0c61caceaf225e179651397431`, skill blob `72bc0b97e7a6476254a9d5c424c9971748402ec3`, and its `openai.yaml` reference. The relevant requirements are: concise core instructions; frontmatter limited to `name` and `description`; all trigger conditions in the description; `SKILL.md` below 500 lines; progressive disclosure; no duplicated content between the core file and references; references one level deep and directly linked; contents sections for long references; tested deterministic scripts; no extraneous runtime documentation; and a short UI prompt that explicitly names the skill.

## Compliance design

- `SKILL.md` contains only `name` and `description` in frontmatter.
- The description names the full lifecycle and the standalone systematic-search, peer-review, scientific-prose, LaTeX, journal, Q1, revision, and release triggers.
- `agents/openai.yaml` contains only `display_name`, `short_description`, and `default_prompt`; all strings are quoted and the prompt explicitly uses `$conduct-cs-research`.
- All nine references are one level below the skill and linked directly from `SKILL.md` with a loading condition.
- Every reference longer than 100 lines contains a `Contents` section.
- No README, changelog, installation guide, quick reference, evaluation corpus, or test harness ships inside the installable folder.
- Runtime scripts implement only deterministic, fragile checks that would otherwise be repeatedly re-created.

## Loading policy

The core rule is **route before loading**.

- A bounded systematic search loads `SKILL.md` plus `systematic-search.md`.
- A bounded manuscript review loads `SKILL.md` plus `peer-review.md`.
- A bounded prose revision loads `SKILL.md` plus `scientific-prose.md`.
- A standalone study-design, experiment, LaTeX, journal, or integrity task loads only its matching reference.
- A full lifecycle loads `workflow.md` first and at most one active-stage reference by default.
- A second cross-cutting reference is allowed only when the artifact type or a documented policy, ethics, or study-design issue requires it.

This prevents a small task from paying for the complete publication pipeline and prevents inactive references from remaining in working context.

## Enforced budgets

The release gate fails when:

- `SKILL.md` exceeds 120 lines, 950 words, or an 80-word trigger description;
- the installable source exceeds 17 files or six runtime Python modules;
- the total reference corpus exceeds 13,000 words;
- a bounded mode's initial core-plus-reference load exceeds 2,600 words;
- the full lifecycle's core-plus-workflow-plus-largest-stage load exceeds 4,000 words;
- a long normalized paragraph is duplicated between `SKILL.md` and any reference;
- a public helper lacks a side-effect-free `--help` contract.

These are stricter project-specific budgets, not universal OpenAI limits. They turn the general principle of context economy into a regression-tested property.

## Deliberate non-goals

Do not minimize token count by deleting scientific safeguards, hiding uncertainty, abbreviating schemas beyond readability, or merging unrelated reference domains. Token efficiency is achieved through conditional loading and removal of duplication, not through compressed or ambiguous instructions.
