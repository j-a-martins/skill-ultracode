# Manuscript, LaTeX, citations, and submission files

## Contents

1. Manuscript architecture
2. Claim-evidence drafting
3. Section contracts
4. Figures, tables, equations, and algorithms
5. Citation integrity
6. LaTeX workflow
7. Submission package
8. Final audit

## Manuscript architecture

Design the paper around a small number of supported claims. Allocate each section a clear job and each figure or table a decision-relevant role. Use the target venue's current official template and instructions; do not rely on an old local template or a similarly named venue.

Before drafting, create:

- one-sentence problem statement;
- contribution contract and comparison class;
- `C####` claim list;
- evidence and result links for each claim;
- non-claims and limitations;
- section outline with word or page budget;
- figure, table, and appendix plan;
- reporting-guideline map.

## Claim-evidence drafting

For each paragraph, know which claim it advances and what evidence supports it. During governed drafting, use recoverable `claim:C####` markers in comments or a separate map. Remove visible control text from the submitted manuscript while preserving the mapping elsewhere.

Distinguish:

- source-backed background claims;
- direct study results;
- derivations or proofs;
- synthesis across evidence;
- interpretation;
- speculation and future work.

Do not write prose first and search for citations afterward to decorate it.

## Section contracts

### Title and abstract

State the study type and supported contribution. The abstract must agree with the final methods and results, including sample sizes, uncertainty, and limitations where required. Avoid novelty or superiority superlatives without a dated comparison.

### Introduction

Establish context, precise problem, nearest work, unresolved gap, contribution, and paper map. Do not construct a gap by ignoring contrary or predecessor work.

### Related work

Organize around comparison dimensions and debates. State how the present work differs without caricaturing prior methods. Cite primary sources for technical claims and authoritative syntheses for broad consensus.

### Methods

Provide enough information to evaluate and reproduce the study. Include decisions that affect validity, not only implementation trivia. Separate prospective methods, amendments, and exploratory additions.

### Results

Report results in the order of the research questions or claims. Give denominators, uncertainty, failures, and negative findings. Keep interpretation limited and label exploratory analyses.

### Discussion

Interpret evidence, compare with prior work, explain plausible mechanisms, address contradictions, state limitations and external-validity boundaries, and identify implications calibrated to the design.

### Conclusion

State the supported contribution and boundary. Do not introduce new evidence or deployment claims.

### Supplement and appendix

Place reproducibility detail, extended proofs, full instruments, additional analyses, and lower-priority results where the venue permits. Do not move evidence essential to evaluating the central claim out of reach.

## Figures, tables, equations, and algorithms

Every display must answer a question. Check:

- readable labels, units, legends, uncertainty, sample size, and color accessibility;
- consistent values across text, table, figure, and raw output;
- captions that state what is shown without overstating meaning;
- no truncated axes or visual encodings that exaggerate effects;
- distinguish variability, confidence, prediction, and posterior intervals;
- algorithms and equations define all symbols and assumptions;
- figures generated from versioned analysis where possible;
- image processing and composites disclosed when material.

## Citation integrity

For every load-bearing citation:

1. resolve its identity;
2. read the relevant source passage or result;
3. verify that the manuscript characterization matches it;
4. check publication status, version, correction, and retraction;
5. ensure citation placement makes its scope clear;
6. avoid citing reviews for claims that require the primary study;
7. include persistent identifiers when the venue requires them.

Never fabricate BibTeX. Do not cite a source merely because a search snippet appears relevant. Avoid coercive self-citation and citation padding.

## LaTeX workflow

Maintain source rather than reverse-engineering the rendered PDF. Use a reproducible build with a pinned template and bibliography tool.

Before compilation:

- run `scripts/audit_latex.py` from the skill;
- reject path escape, symlinked inputs, missing included files, missing graphics, unresolved bibliography files, duplicate labels, missing citations, and unsafe shell or file primitives;
- preserve user macros and math during prose edits;
- build in an isolated directory without shell escape;
- avoid network access during compilation;
- inspect the compiler log and rendered PDF.

Static auditing cannot prove arbitrary TeX safe. Compile only in a restricted environment. Do not execute code embedded in a manuscript or bibliography.

After compilation, inspect:

- title, authors, affiliations, anonymous-review state, and metadata;
- font embedding and page size;
- page and word limits;
- equations, algorithms, floats, references, and hyperlinks;
- figure resolution and accessibility;
- orphan headings, widows, overfull boxes, and clipped content;
- supplement and data/code links;
- line numbering and review requirements.

## Submission package

Use the current official journal or conference instructions to prepare only required files. Typical items include:

- manuscript source and rendered file;
- anonymous and identified versions when required;
- figures and tables in accepted formats;
- supplementary material;
- data and code availability statements;
- ethics, consent, conflicts, funding, authorship, and AI-use disclosures;
- reporting-guideline checklist;
- cover letter;
- highlights, graphical abstract, or key points when required;
- suggested or opposed reviewers with legitimate reasons when permitted;
- repository records and persistent identifiers.

Verify that all authors approved the final manuscript and destination. Before transmission, show the exact payload and destination and obtain action-specific authorization.

## Final audit

Perform a cold read and verify:

- all central claims have evidence;
- abstract, figures, tables, and conclusion agree;
- no tracked changes, comments, hidden text, prompt state, local paths, usernames, secrets, or internal control markers remain;
- references resolve and citation keys are complete;
- current venue requirements and policies are met;
- reporting checklist locations are accurate;
- files open and compile from a clean copy;
- public artifacts match the manuscript claims;
- limitations and negative evidence remain visible;
- submission metadata matches the manuscript.

Do not declare submission readiness from a successful LaTeX build alone.