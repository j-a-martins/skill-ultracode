# Manuscript, LaTeX, citations, and submission files

## Contents

1. Manuscript architecture
2. Claim-to-text control
3. Section functions
4. Citation integrity
5. LaTeX source safety
6. Static audit and restricted compilation
7. Figures, tables, and accessibility
8. Submission package
9. Failure modes

## Manuscript architecture

Design the manuscript around the contribution and evidence, not a generic section template. Allocate each section a rhetorical job:

- establish the problem and evidence gap;
- position the contribution against nearest work;
- define the method or study sufficiently for evaluation;
- report results before interpretation;
- discuss meaning, limitations, threats, and boundary conditions;
- provide reproducibility, ethics, data, code, and disclosure information required by the current journal and reporting guideline.

Use the official journal template and current instructions. Do not copy layout hacks or obsolete template invocations from prior papers.

## Claim-to-text control

Before drafting, maintain a claim matrix. Active claims identify source IDs, result IDs, claim type, status, limitations, and manuscript locations. During governed drafting, place recoverable markers such as:

```text
% claim:C0007
```

The marker does not prove support. It makes it possible to compare the manuscript with the evidence ledger. Candidate, excluded, unresolved, withdrawn, failed, or superseded records cannot support an active claim.

When a source or result changes, locate and re-audit every dependent claim and paragraph.

## Section functions

### Title and abstract

Represent the actual study, population or artifact, method, principal result, and limitations without overclaiming. Respect current journal word and structure limits. Do not add citations or numerical detail unsupported by the manuscript.

### Introduction and related work

Move from problem to gap to contribution. Compare with nearest work using verified sources. Distinguish what is new from what is reused. Preserve contrary and negative evidence.

### Methods

Provide enough information to evaluate and reproduce the work: design, data, preprocessing, sampling, controls, baselines, implementation, parameters, outcomes, analysis, exclusions, robustness, ethics, and deviations. A prose edit must not silently repair or conceal a missing methodological element.

### Results

Report estimates, uncertainty, negative findings, robustness, and deviations. Keep observation separate from interpretation. Tables and figures must trace to current analysis artifacts.

### Discussion

Interpret within the evidence boundary. Address limitations, threats, alternative explanations, generalizability, implications, and future work. Do not turn association into causation or exploratory evidence into confirmation.

## Citation integrity

For every citation:

- verify that the work exists and resolve the canonical record;
- inspect the level of evidence actually accessed;
- verify that the cited work supports the exact statement and scope;
- distinguish preprints, proceedings versions, journal extensions, corrections, and retractions;
- preserve citation commands, keys, locators, and paragraph scope during editing;
- prefer primary evidence for direct findings;
- cite reviews for synthesis without laundering unverified primary claims;
- re-check retractions and corrections before submission and camera-ready release.

A resolving DOI proves that a record exists, not that it is relevant, canonical, unretracted, or adequate support.

## LaTeX source safety

Treat LaTeX as executable input. Never compile an untrusted tree with shell escape. Reject or isolate:

- `\write18`, shell-escape helpers, and pipe input;
- direct Lua execution;
- raw file read/write primitives;
- raw PDF launch actions or specials;
- high-risk packages such as `minted`, `pythontex`, `sagetex`, `gnuplottex`, `luacode`, `shellesc`, and `catchfile` unless a separately reviewed, sandboxed workflow explicitly requires them;
- input, import, bibliography, graphic, or compiler-log paths that escape the manuscript root;
- symlinks, hardlinks, FIFOs, sockets, devices, and other special files;
- dynamically constructed dangerous control sequences.

Use a disposable, restricted container or sandbox with no secrets and no unnecessary network access. Visual inspection remains mandatory.

## Static audit and restricted compilation

Run:

```text
python scripts/audit_latex.py ROOT --main main.tex --json
```

The static audit follows common input and import commands, checks the entire manuscript tree for unsafe file types, resolves graphics and bibliographies, parses real top-level BibTeX entries, ignores `@comment`, `@string`, and `@preamble` as citation records, detects duplicate keys across files, accepts `\nocite{*}`, checks labels and references, and scans for unsafe primitives and packages.

Static parsing is conservative and incomplete. TeX macro expansion is Turing-complete; a PASS does not prove arbitrary source safe. After static audit:

1. compile with shell escape disabled in a restricted environment;
2. review compiler errors, undefined citations/references, and overfull boxes;
3. inspect the final PDF page by page;
4. inspect metadata, fonts, links, figure quality, and accessibility;
5. compare final page count and mandatory sections against current journal instructions.

Do not use negative spacing, font substitution, margin changes, or other template manipulation to evade limits.

## Figures, tables, and accessibility

Every figure and table should:

- have a precise purpose and evidence source;
- use readable labels and units;
- include uncertainty and sample size where relevant;
- avoid misleading axes, truncation, or selective subsets;
- remain interpretable in grayscale and for common color-vision differences;
- use accessible text alternatives or descriptions when required;
- have a caption that states what is shown without overstating the conclusion;
- trace to code, data, or a documented manual process.

Do not recreate a result figure from memory or alter a value for visual impact.

## Submission package

Before handoff, assemble and verify:

- main manuscript source and rendered PDF;
- bibliography and supplementary files;
- data, code, materials, and availability statements;
- ethics, consent, conflicts, funding, authorship, contribution, and AI-use disclosures;
- reporting checklists;
- cover letter and suggested or excluded reviewers where permitted;
- exact journal, article type, and submission destination;
- file names, page and word limits, anonymity, and metadata;
- checksums for the exact payload.

The prepared package is not authorization to submit. Show exact current bytes and destination and obtain action-specific authorization.

## Failure modes

Reject or revise a manuscript process that:

- drafts claims before identifying support;
- fabricates or guesses citations;
- treats an abstract as support for inaccessible detail;
- leaves active claims unmapped;
- uses retracted or inactive evidence without disclosure;
- silently changes numbers, equations, citation scope, or causal strength during editing;
- accepts fake BibTeX keys embedded in comments or field text;
- compiles untrusted TeX with shell escape or secrets available;
- ignores imported source files or path escapes;
- treats static audit as proof of safety;
- manipulates the template to evade limits;
- claims a submission occurred without an exact authorized payload record.

A manuscript is ready for human submission only after scientific, policy, source, static, compile, and visual checks converge.
