# Journal selection, Q1 evidence, and portfolio decisions

## Contents

1. Separate fit from ranking
2. Build the candidate set
3. Verify current journal facts
4. Record Q1 evidence without overclaiming
5. Score fit and choose a destination
6. Check integrity and operational constraints
7. Plan a portfolio
8. Failure modes

## Separate fit from ranking

Treat journal selection as a scientific and operational decision. Do not use quartile, impact factor, or prestige as a substitute for scope, methods, audience, article type, editorial practice, and reproducibility fit.

Maintain two distinct judgments:

- **scientific fit** — whether the journal publishes this contribution, study family, article type, and level of evidence;
- **ranking evidence** — whether an identified provider, metric year, and exact subject category place the journal in Q1.

A poor-fit Q1 journal remains a poor choice. A strong-fit journal without a complete Q1 evidence record must not be represented as verified Q1.

## Build the candidate set

Generate a bounded candidate set from:

- journals publishing the nearest prior work;
- journals explicitly covering the contribution and method;
- journals serving the intended audience;
- journals accepting the required article type and manuscript scale;
- journals whose data, code, ethics, reporting, and artifact policies the project can meet;
- legitimate alternatives for different contribution framings.

Do not recommend a journal solely because its title contains a keyword or because it appears on an unverified list. Check recent relevant articles and current scope.

## Verify current journal facts

Use current official journal, publisher, indexing-provider, and submission-system sources. Record the access date. Verify at least:

- exact title, ISSN, publisher, and official journal page;
- scope, exclusions, article types, and recent relevant content;
- manuscript, abstract, figure, table, reference, and supplementary limits;
- peer-review and anonymity model;
- data, code, materials, ethics, consent, conflict, authorship, and AI-use policies;
- open-access routes, mandatory or optional charges, waivers, and licensing;
- preprint, prior-publication, conference-extension, and duplicate-submission policy;
- submission system and required metadata;
- current ranking provider, metric name, metric year, exact category, quartile, rank, and denominator when available.

If facts conflict, retain the conflict and prefer the source responsible for that fact. Ask the journal when an ambiguity controls submission eligibility.

## Record Q1 evidence without overclaiming

A Q1 statement must identify:

- journal and ISSN;
- provider, such as Journal Citation Reports, CiteScore/Scopus, or SCImago Journal Rank;
- metric name and metric year;
- exact subject category;
- quartile;
- rank and denominator when available;
- a journal-specific authoritative HTTPS record;
- verification date;
- a local evidence capture and SHA-256;
- the person who checked the record and a timezone-aware verification timestamp.

Save the provider page or a lawful local capture under the same directory as `publication/journals.csv`, then record its relative path and hash. Do not use a general provider homepage, a search-result snippet, an aggregator, a marketing page, or a manually typed list as journal-specific evidence.

The local scorer checks structural completeness, provider-domain plausibility, age, category specificity, and evidence bytes. It does **not** retrieve the provider page, prove that the local capture came from that server, authenticate the verifier, or establish that a licensed database record has not changed. Describe its result as a **complete local Q1 evidence record**, not cryptographically authenticated remote truth.

Never collapse category-specific results into a timeless scalar label. State, for example, “Q1 under provider P, metric year Y, category C, verified on date D.”

## Score fit and choose a destination

Use `scripts/score_journals.py` only after records are populated. Fit fields use a 0–5 scale:

- scope fit;
- methods fit;
- audience fit;
- article-type fit;
- open-science fit.

The default ranking is scientific fit first. `--verified-q1-only` is an explicit eligibility filter; Q1 is not an implicit score bonus. Review component scores and rationale rather than accepting the total mechanically.

For a selected journal, write `publication/selected-journal.json` with:

- `journal`;
- `fit_rationale`;
- timezone-aware `selected_at`;
- `q1_claim`: `verified`, `provisional`, or `not-claimed`;
- when `verified`, the exact provider, metric year, category, and evidence SHA-256 copied from the candidate record.

A verified claim must match exactly one candidate row and its current evidence bytes.

## Check integrity and operational constraints

Before choosing, check:

- whether the journal is recognized by the institution or funder;
- transparent editorial board and peer-review process;
- verifiable publisher identity and contact details;
- realistic indexing claims;
- fee transparency and waiver policy;
- retraction, correction, and research-integrity policies;
- whether special issues or solicitations are legitimate;
- whether the journal is currently accepting the relevant article type;
- whether submission creates conflicts with other manuscripts or prior versions.

Do not rely on a single blacklist or whitelist. Investigate the journal itself.

## Plan a portfolio

Prepare a small ordered portfolio:

1. first-choice journal;
2. close-fit alternative;
3. conservative alternative.

For each, record fit, Q1 evidence status, required reframing, format cost, fee exposure, policy risks, and likely additional work. Re-verify current facts before any resubmission because policies and rankings can change.

Do not submit simultaneously where prohibited. Do not promise acceptance probabilities unsupported by journal-specific evidence.

## Failure modes

Reject or revise a selection process that:

- optimizes quartile before scope;
- calls a journal Q1 without provider, year, and category;
- uses stale, generic, or non-journal-specific evidence;
- accepts a self-authored evidence file without human source checking;
- treats a script PASS as remote authentication;
- ignores article type, methods, or audience mismatch;
- omits publication charges or policy constraints;
- predicts acceptance from impact metrics;
- recommends a journal with unverifiable identity or editorial practices;
- preserves a Q1 label after the source record or metric year changes.

The final recommendation is a reasoned portfolio decision, not a publication guarantee.
