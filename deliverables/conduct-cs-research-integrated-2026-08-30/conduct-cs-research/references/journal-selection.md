# Journal selection and Q1 verification

## Contents

1. Separate fit from quartile
2. Candidate discovery
3. Fit assessment
4. Q1 evidence record
5. Policy and practical checks
6. Portfolio decision
7. Reverification
8. Failure modes

## Separate fit from quartile

Treat scientific fit and Q1 status as independent variables. A verified Q1 journal may be unsuitable for the paper's contribution, methods, audience, or article type. A strong-fit journal may not be Q1 under the chosen provider, year, and category.

Never describe a journal as simply `Q1` without the provider, metric year, and exact subject category. Quartile is not a permanent scalar property of a title.

## Candidate discovery

Build candidates from:

- journals publishing the nearest comparable work;
- journals cited by and citing the relevant evidence base;
- official society and publisher portfolios;
- target audiences and communities;
- appropriate article types;
- current indexing and metric-provider records;
- funder, institution, licensing, and open-access constraints.

Exclude journals with a scope mismatch, unverifiable identity, deceptive practices, or policies incompatible with the study.

## Fit assessment

Assess each candidate on a transparent scale, normally 0 to 5, for:

- scope and contribution fit;
- methodological fit;
- audience fit;
- article-type fit;
- precedent for similar work;
- open-science and artifact fit;
- length and format feasibility;
- review model and timeline when material;
- policy compatibility;
- cost and licensing constraints.

Scores support comparison; they do not predict acceptance. Explain the evidence behind high-impact differences rather than relying on arithmetic alone.

## Q1 evidence record

To accept a Q1 claim, record:

- canonical journal title and ISSN where available;
- metric provider, such as Journal Citation Reports, CiteScore/Scopus, or SCImago SJR;
- metric name and metric year;
- exact subject category;
- quartile in that category;
- rank and denominator or percentile when available;
- authoritative verification source;
- access or capture date;
- notes on ties, multiple categories, title changes, and coverage.

Use the provider's official or institutionally licensed record when available. A search snippet, journal marketing page, crowd-sourced list, or undated table is not sufficient evidence.

If only a secondary record is available, label the status `provisional` and do not state verified Q1.

## Policy and practical checks

Fetch current official pages and record the check date for:

- aims and scope;
- accepted article types;
- author instructions and template;
- word, page, figure, table, and supplement limits;
- data, code, materials, and reporting policies;
- preprint and prior-publication rules;
- AI-writing and AI-review policies;
- ethics, consent, conflicts, funding, authorship, and CRediT requirements;
- anonymous-review requirements;
- open-access route, APCs, waivers, and licensing;
- submission system and file requirements;
- special issues and deadlines;
- withdrawal, transfer, and appeal policies.

Publisher-wide policies may differ from journal-specific rules. The journal-specific current page governs unless the publisher states otherwise.

## Portfolio decision

Create a small portfolio rather than one supposedly perfect target:

- primary target;
- close alternative with similar manuscript requirements;
- lower-risk or different-audience alternative;
- optional conference or journal transfer route when disciplineally appropriate.

For each, state fit, verified metric status, principal risks, required manuscript changes, costs, and fallback logic. Avoid serial submissions to obviously mismatched journals solely to chase quartile.

Do not estimate acceptance probability without a defensible empirical basis. Historical acceptance rates, when available, may not transfer to the article type, topic, or current editorial regime.

## Reverification

Recheck before every submission or transfer:

- title, ISSN, ownership, and scope;
- current instructions and policies;
- category-specific quartile and metric year;
- APC and licensing;
- special-issue legitimacy and deadline;
- editor and submission-system destination;
- retraction, delisting, or indexing changes.

Record the exact verification date. A journal status verified for one submission is not permanently valid.

Use `scripts/score_journals.py` to rank documented fit while rejecting incomplete Q1 records. The script does not retrieve or authenticate journal data; a human must verify the evidence source.

## Failure modes

Reject or qualify decisions based on:

- highest percentile shown without its category;
- current title confused with a predecessor or similarly named journal;
- quartile from an unspecified provider or year;
- impact factor confused with CiteScore or SJR;
- indexing assumed from publisher branding;
- stale APC, scope, or policy information;
- special-issue invitations with unverifiable editors or domains;
- fit scores presented as acceptance probabilities;
- Q1 status used to excuse weak methodological fit;
- a paper reshaped beyond its evidence merely to match a venue.

No workflow can guarantee Q1 publication. Optimize for defensible fit, methodological quality, and a transparent submission strategy.