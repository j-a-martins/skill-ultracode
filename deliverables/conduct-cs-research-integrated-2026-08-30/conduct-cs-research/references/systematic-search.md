# Systematic search and evidence synthesis

## Contents

1. Choose the search mode
2. Freeze the protocol
3. Execute and expand
4. Deduplicate and screen
5. Extract, appraise, and synthesize
6. Stop and report

## Choose the search mode

Use the minimum justified rigor:

- orientation or focused search for bounded factual support;
- novelty audit for nearest competing work;
- systematic, mapping, or scoping review for reproducible coverage;
- update search for a dated prior review.

Do not call a search exhaustive unless the protocol, source coverage, execution state, and stopping rule support that claim. Apply current PRISMA-family guidance only when the review design requires it; computer-science reviews often also need DBLP, IEEE Xplore, ACM Digital Library, arXiv, citation graphs, and venue-specific sources.

## Freeze the protocol

Before a formal search, record questions, concepts and synonyms, sources and interfaces, exact source-specific queries, dates, language and document limits, inclusion and exclusion criteria, deduplication and version policy, screening procedure, extraction fields, appraisal method, synthesis plan, stopping rule, and update plan.

A protocol written or changed after viewing favorable records is retrospective. Date amendments and explain their effect.

## Execute and expand

Log each run in `evidence/search-log.csv`: source, interface, exact query, filters, timezone-aware time, result count, and hash-bound export or a documented reproducible alternative. Distinguish:

- zero results from a successful provider response;
- provider failure, rate limiting, authentication failure, or partial coverage;
- a search that has not yet run.

Use several complementary routes where recall matters: database queries, venue-year enumeration, backward and forward chaining from multiple diverse seeds, author or project searches, distinctive mechanism terms, and reference reconciliation against the emerging manuscript.

## Deduplicate and screen

Represent each version family once in `evidence/deduplication.csv`. Every cluster has one canonical source and a unique member list. A source may belong to at most one cluster globally. Do not double-count preprint, conference, journal, repository, and corrected versions; retain the relationships and choose deliberately.

Screen in explicit stages. A full-text decision requires a preceding title/abstract `include`. Record every exclusion reason. Preserve uncertainty rather than silently resolving ambiguous eligibility.

## Extract, appraise, and synthesize

Create exactly one extraction row per included full-text record. Bind it to known source IDs and record method, outcomes, limitations, and evidence-access level. Do not present metadata-only or abstract-only evidence as if full text, data, code, or artifacts were inspected.

Appraise threats appropriate to the study family: selection, leakage, comparator quality, measurement, confounding, missingness, multiplicity, implementation fidelity, external validity, reproducibility, and selective reporting. Synthesize by concepts and evidence patterns rather than serial summaries. Retain contradictions, nulls, adverse findings, heterogeneity, and unresolved gaps.

At synthesis, `evidence/flow.json` must exactly reconcile:

- `screened` with distinct screening record IDs;
- `full_text_assessed` with distinct full-text record IDs;
- `included` with full-text include decisions;
- the included record-ID set with the extraction record-ID set.

`identified ≥ deduplicated ≥ screened` remains an aggregate constraint where provider exports prevent exact reconstruction of the earlier counts.

## Stop and report

Use a declared stop rule such as executed protocol with all provider states resolved, successive rounds yielding no material eligible records, stable thematic coverage plus complete citation chaining, or a documented resource boundary. Autonomous searching is bounded; it is not an indefinite background process.

Report exact dates, queries, sources, provider failures, screening flow, deduplication policy, access levels, appraisal, synthesis limits, and the meaning of completeness. A partial provider run, unresolved version family, unreconciled flow, or missing extraction is a blocker for a formal completeness claim.
