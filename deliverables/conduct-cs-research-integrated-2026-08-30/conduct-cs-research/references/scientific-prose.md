# Meaning-preserving scientific prose revision

## Contents

1. Revision modes
2. Establish the scientific contract
3. Protect immutable content
4. Revise information flow
5. Preserve epistemic force and logical direction
6. Handle citations and LaTeX
7. Audit the actual file pair
8. Report material changes and residual concerns
9. Failure modes

## Revision modes

Choose the narrowest mode:

- **copyedit** — grammar, spelling, punctuation, and local concision;
- **line edit** — sentence structure, cohesion, emphasis, and information flow;
- **substantive restructure** — paragraph or section reorganization while preserving the scientific contract;
- **plain-language version** — communicate the same evidence to a specified nonexpert audience;
- **translation** — translate when requested while preserving scientific meaning, notation, and citation scope;
- **venue calibration** — adapt register and structure to current journal instructions without changing the evidence.

Do not silently change the research question, methods, analysis, results, limitations, or contribution. When scientific repair is needed, separate it from the prose edit and request authorization.

## Establish the scientific contract

Before revising, identify:

- section type and rhetorical purpose;
- intended audience and target venue if relevant;
- claims and their support;
- facts supplied by the user;
- numbers, signs, units, ranges, uncertainty, and statistical language;
- causal versus associational force;
- conditions, exceptions, scope, direction, and comparison class;
- citations and the exact text each citation supports;
- equations, algorithms, code identifiers, labels, references, and user-defined macros;
- terminology and abbreviations;
- quotations and legally or ethically sensitive wording;
- explicit instructions about permissible scientific change.

If the source is ambiguous, do not resolve the ambiguity by guessing. Preserve it or flag it separately.

## Protect immutable content

Treat the following as protected unless the user explicitly authorizes a scientific change:

- numerical values and their signs;
- units and scale;
- equations, mathematical operators, inequalities, and complexity statements;
- p-values, intervals, uncertainty measures, thresholds, and significance status;
- citation keys, citation commands, optional page locators, and citation scope;
- LaTeX labels, cross-references, macro names, and code spans;
- URLs, DOIs, dataset IDs, model names, variable names, and software versions;
- negation, polarity, direction, temporal order, and comparison direction;
- causal strength, modality, hedging, and certainty;
- conditions, exceptions, inclusion or exclusion scope, and boundary cases;
- limitations, null results, contradictions, and adverse findings.

Build `manuscript/protected-spans.txt` for governed work. Record `None` only after an actual inventory.

## Revise information flow

Use information structure deliberately:

- place familiar context before new information;
- put the sentence’s main action in the grammatical core;
- keep the topic near the beginning and the stress-bearing contribution near the end;
- keep each paragraph focused on one rhetorical job;
- make links between problem, method, evidence, and implication explicit;
- prefer concrete agents and operations when they improve clarity;
- retain passive voice when the procedure, object, or result is the appropriate topic;
- remove repetition that does not carry a distinction;
- preserve technical terms when a simpler synonym would change meaning.

Do not apply blanket style rules such as deleting all passive voice, all nominalizations, all hedges, or all long sentences.

## Preserve epistemic force and logical direction

Check every revision for semantic drift:

- `increased`, `higher`, `improved`, `positive`, `before`, and `supports` must not become their opposites;
- association must not become causation;
- possibility must not become proof;
- a conditional claim must not become unconditional;
- a subset must not become a population-wide statement;
- a negative or nonsignificant result must not become positive or significant;
- “consistent with” must not become “confirms” without stronger evidence;
- temporal order and method sequence must remain intact;
- limitations and uncertainty must remain visible.

Synonymous wording within the same direction is acceptable when the scientific relation is unchanged. A direction, scope, or certainty change is a scientific change even when every number remains identical.

## Handle citations and LaTeX

For citations:

- preserve cite keys and optional locators;
- preserve the clause or proposition supported by each citation;
- do not move a citation from a narrow claim to a whole paragraph without checking the source;
- do not add a plausible-looking reference;
- route new or changed citations through source verification.

For LaTeX:

- preserve citation, label, reference, and user-macro syntax;
- do not rewrite equations or algorithmic identifiers as prose;
- do not alter table or figure cross-references without checking the target;
- edit source files rather than reconstructed PDF text when possible;
- compile in a restricted no-shell-escape environment after static audit;
- inspect the rendered output after source changes.

## Audit the actual file pair

A revision log is not evidence unless it identifies the current original and revised bytes. For each revision record:

- assign `V####`;
- record project-relative original and revised paths;
- record SHA-256 for both;
- state scope and protected content;
- state material scientific changes, if any;
- state residual concerns;
- record deterministic audit status and final review status.

Run:

```text
python scripts/audit_prose.py ORIGINAL REVISED --strict --json
```

The audit checks protected tokens, direction, polarity, temporal order, support versus contradiction, conditions, scope markers, causal strength, uncertainty, citation placement, and LaTeX macros. It is conservative and cannot prove semantic equivalence.

If strict audit fails because an authorized scientific change is intentional, record `manual-accepted` only with a specific material-change rationale and residual-risk explanation. Do not use manual acceptance to conceal an unexamined drift.

## Report material changes and residual concerns

Return the requested clean revision. Separately report only material items:

- scientific changes explicitly authorized;
- ambiguities preserved or flagged;
- suspected factual or methodological defects in the source;
- citations requiring verification;
- unresolved semantic-drift warnings;
- venue constraints that could not be verified.

Do not present copyediting as scientific validation.

## Failure modes

Reject or revise an edit that:

- changes a number, sign, unit, equation, identifier, or citation without authorization;
- reverses direction, polarity, time order, or support relation;
- removes a condition, exception, or limitation;
- changes association to causation;
- removes uncertainty to sound confident;
- moves citation scope without checking the source;
- hides a missing control or design defect through polished language;
- invents a citation or fact;
- promises detector evasion or exact imitation of a living author’s distinctive style;
- breaks LaTeX macros or references;
- records a passing revision audit without binding the actual file bytes.

The purpose is clearer scientific communication with preserved meaning, not stronger-sounding claims.
