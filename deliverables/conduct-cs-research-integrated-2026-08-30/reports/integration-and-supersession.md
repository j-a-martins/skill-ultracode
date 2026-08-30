# Integration and supersession report

## Scope

This release consolidates the prior `conduct-cs-research` lifecycle with the intended capabilities of three user-supplied academic skills:

- `autonomous-systematic-search.zip`
- `academic-peer-reviewer.zip`
- `rewrite-scientific-prose.zip`

The result exposes one skill, `conduct-cs-research`, with four native operating modes rather than four competing trigger surfaces.

## Source-access limitation

The conversation's local attachment and Python runtime was unavailable during this build. The uploaded ZIP bytes could therefore not be enumerated, extracted, license-audited, or compared line by line. No text or code was copied from the archives. Integration was performed at the capability and trigger-contract level using:

- the skill identities supplied by the user;
- the previously built `conduct-cs-research` architecture summarized in the conversation;
- the current OpenAI `skill-creator` specification;
- public academic-search, peer-review, and scientific-writing skill analogues;
- current official research-reporting and publishing guidance.

Consequently, this release can claim capability-level supersession, not byte-level source equivalence. A future byte-level audit should compare the three archives against this matrix and preserve any applicable license notices.

## Architectural decision

The source skills are not embedded as nested subskills. Their behaviors are first-class modes:

| Prior trigger family | Unified mode | Native reference | Deterministic safeguard |
|---|---|---|---|
| End-to-end CS research and Q1 publication | `full-research-lifecycle` | `workflow.md`, `study-design.md`, publication references | project, LaTeX, journal, and regression scripts |
| Autonomous/systematic scholarly search | `systematic-search` | `systematic-search.md` | project search records and evidence-link audit |
| Academic manuscript review | `peer-review` | `peer-review.md` | evidence-linked project audit and adversarial evals |
| Scientific-prose rewriting | `scientific-prose` | `scientific-prose.md` | protected-content drift audit |

## Capability matrix

### Systematic search

Integrated capabilities:

- orientation, focused, novelty, systematic, mapping, scoping, and update modes;
- protocol-first review design;
- CS-appropriate concept frameworks rather than universal PICO;
- complementary database and citation-network strategy;
- database-specific query translation;
- sentinel-record tests and PRESS-style strategy review;
- exact query, source, interface, date, filter, count, export, and limitation logging;
- layered deduplication with version-family preservation;
- title/abstract and full-text screening with explicit reasons;
- no false claim of independent dual screening;
- structured extraction and evidence-access levels;
- corrections, retractions, contrary evidence, and version checks;
- synthesis, stopping, saturation, and update rules;
- current PRISMA/PRISMA-S routing when applicable;
- prompt-injection resistance for retrieved documents.

### Peer review

Integrated capabilities:

- self-review, journal-style pre-review, methodological, reproducibility, reference, rapid-triage, re-review, and rebuttal modes;
- manuscript reconstruction before judgment;
- contribution, methodology, evidence, integrity, reproducibility, communication, and venue-fit dimensions;
- findings anchored by location, evidence, consequence, action, and status;
- design-limiting, major, minor, and editorial severity classes;
- recommendation separated from confidence;
- sequential analytical lenses without fake independent reviewers;
- verified suggested citations and retraction checks;
- comment-to-change response matrix;
- review-of-review for unsupported criticism and severity inflation;
- confidential-material and prompt-injection protections.

### Scientific prose

Integrated capabilities:

- copyedit, line edit, substantive edit, section and venue calibration, plain-language rewriting, and requested translation;
- a faithfulness contract covering facts, numbers, units, equations, citations, cross-references, code identifiers, scope, causal language, modality, negation, and uncertainty;
- protected-span inventory for LaTeX and technical material;
- section-aware rhetorical contracts;
- information-flow and concision guidance without blanket passive-voice rules;
- clean rewrite by default, proportional change logs, and residual scientific concerns;
- no detector evasion, invented support, or style imitation;
- deterministic number, citation, cross-reference, math, code, DOI, URL, negation, uncertainty, causality, and certainty checks.

## What was retained from the research lifecycle

- study-family routing;
- prospective protocols and transparent retrospective reconstruction;
- pilot and definitive execution separation;
- evidence, decision, run, result, and claim identifiers;
- claim-evidence mapping and rollback;
- reproducibility and negative-evidence handling;
- current target-journal and reporting-guideline checks;
- category-specific Q1 verification;
- LaTeX, submission, review, revision, release, and correction stages;
- explicit authorization before external actions.

## What was deliberately not carried forward

The release removes or avoids:

- cryptographic approval chains for routine project stages;
- one-use authorization tokens and pseudo-blockchain history;
- dozens of mandatory files for bounded tasks;
- multiple independent validators implementing the same checks;
- fake multi-agent reviewer personas;
- arbitrary aggregate review scores;
- mandatory figures or fixed reference-count targets;
- universal PICO framing;
- claims that automated searching is exhaustive;
- detector-evasion or guaranteed publication language.

## Supersession contract

Install only `conduct-cs-research`. Its frontmatter now triggers on the standalone search, review, and prose requests previously routed to the three source skills. For a bounded request it selects the narrowest native mode and does not force the full lifecycle.

The three source skills should be considered superseded only at the capability and routing level until their original archive contents and licenses can be inspected byte by byte.