# Meaning-preserving scientific prose revision

## Contents

1. Revision modes
2. Faithfulness contract
3. Protected content
4. Section-aware revision
5. Information flow
6. Workflow
7. Output contract
8. Prohibited transformations
9. Drift audit

## Revision modes

Choose the requested depth:

- `copyedit`: grammar, punctuation, spelling, consistency, and local clarity.
- `line-edit`: sentence structure, concision, emphasis, and transitions.
- `substantive-edit`: paragraph and section organization while preserving the scientific argument.
- `section-calibration`: adapt rhetorical moves to abstract, introduction, methods, results, discussion, conclusion, cover letter, or reviewer response.
- `venue-calibration`: conform to current target-venue style and length without imitating a named author's distinctive style.
- `plain-language`: explain the same evidence to a specified non-specialist audience.
- `translation`: translate when requested while preserving technical meaning and flagging terms without safe equivalents.

Do not assume that more rewriting is better. Apply the smallest change that achieves the stated purpose.

## Faithfulness contract

Unless the user explicitly authorizes a scientific change, preserve:

- factual propositions and their scope;
- numbers, signs, decimal precision, units, dates, sample sizes, and identifiers;
- equations, symbols, notation, and logical operators;
- citations, citation scope, and cross-references;
- code, variable, dataset, model, benchmark, and method names;
- causal versus associative language;
- modal strength, uncertainty, confidence, and limitation language;
- negation, comparison direction, temporal order, and conditionality;
- terminology identity across the manuscript;
- distinctions between observed results, interpretation, and speculation.

Never add a fact, result, citation, method, participant characteristic, author experience, or claim merely to improve flow.

## Protected content

Before editing technical material, inventory protected spans:

- LaTeX commands, environments, labels, references, citations, and math;
- inline and fenced code;
- URLs, DOIs, accession numbers, commit hashes, and persistent identifiers;
- table and figure values;
- quotations;
- defined terms and abbreviations;
- legal, ethical, disclosure, funding, and authorship statements.

Keep protected spans verbatim unless the requested task specifically includes them. When a protected span appears erroneous, flag it rather than silently changing it.

## Section-aware revision

### Title

Preserve the supported contribution and study type. Avoid universal, causal, first, best, or state-of-the-art claims without evidence.

### Abstract

Maintain objective, method, principal results with uncertainty, and calibrated conclusion. Do not introduce background claims or results absent from the manuscript. Respect the current venue structure and word limit.

### Introduction

Move from established context to the precise unresolved problem, nearest work, gap, and contribution. Do not create a straw-man gap. Keep contribution language consistent with the evidence and related-work audit.

### Related work

Organize by comparison logic or debate, not one-paper-per-sentence listing. Preserve contrary and predecessor work. Distinguish factual descriptions from the author's synthesis.

### Methods

Prioritize reproducibility and decision rationale. Preserve procedural order, parameters, exclusions, materials, and preregistered distinctions. Passive voice is acceptable when the actor is irrelevant; active voice is preferable when responsibility matters.

### Results

Lead with the question and result, report uncertainty, and separate observation from explanation. Do not replace precise values with adjectives or convert exploratory results into confirmatory claims.

### Discussion

Interpret results against the question and prior evidence, then address mechanisms, limitations, external validity, and implications. Keep speculation marked. Do not repeat every result.

### Conclusion

State the supported contribution and boundary. Do not add future impact, deployment, or policy claims unsupported by the study.

### Reviewer response

Answer the concern, state the action, cite the exact change, and provide evidence. Avoid defensive rhetoric and unsupported claims that the reviewer is satisfied.

## Information flow

Use these principles selectively:

- place familiar context before new information;
- place the sentence's intended emphasis near the end when natural;
- keep subjects and main verbs close enough to expose agency and logic;
- use stable terminology for stable concepts;
- give each paragraph one main rhetorical job;
- connect paragraphs through repeated concepts rather than generic transitions;
- prefer concrete verbs and explicit agents when they clarify responsibility;
- delete nominalizations, throat-clearing, empty intensifiers, and redundant metadiscourse;
- vary sentence structure for logic, not to appear human;
- retain legitimate disciplinary conventions.

Do not enforce blanket bans on passive voice, first person, long sentences, or field-specific terminology.

## Workflow

1. Confirm audience, section, venue, revision depth, language, and whether a change log is needed.
2. Extract the claim inventory and protected spans.
3. Separate writing defects from scientific defects.
4. Revise structure before sentences when substantive editing is authorized.
5. Revise sentences for clarity, precision, cohesion, and concision.
6. Run a semantic-drift audit.
7. Return the clean revision and list unresolved scientific concerns outside the prose.

For files, preserve encoding and line endings when practical. Never overwrite the only copy without explicit authorization. For LaTeX, edit source rather than reconstructed rendered text.

## Output contract

Default output:

1. the revised text only;
2. a short `Residual concerns` section only when scientific ambiguity, missing evidence, or a possible source error remains.

When requested, add:

- a concise change log;
- side-by-side original and revision;
- rationale for major structural changes;
- protected-content audit results;
- alternative phrasings for genuinely ambiguous passages.

Do not burden a routine copyedit with a large editorial report.

## Prohibited transformations

Do not:

- strengthen association into causation;
- replace `may`, `might`, or `suggests` with certainty without evidence;
- remove limitations, caveats, null results, or adverse findings to sound persuasive;
- reverse negation or comparison direction;
- change numbers, units, precision, or denominators;
- move a citation so that it appears to support a different claim;
- invent a missing transition fact;
- hide plagiarism, patchwriting, fabricated evidence, or ethical concerns behind polish;
- optimize for authorship-detector evasion or promise a detector outcome;
- imitate the distinctive style of a living author or reproduce copyrighted wording from a target paper;
- translate terminology mechanically when the target-language term changes the construct.

## Drift audit

Use `scripts/audit_prose.py` for a conservative mechanical check, then read both versions. Check:

- number and unit identity;
- citation, label, and cross-reference identity;
- math and code identity;
- negation and comparison direction;
- causal verbs and certainty markers added;
- uncertainty markers removed;
- claim boundaries, conditions, and populations changed;
- terminology drift;
- sentence mergers that alter citation scope;
- omissions of qualifications or contradictory evidence.

Mechanical equality is not semantic equivalence, and mechanical differences are not always errors. Resolve flagged differences against the author's intended meaning and evidence.