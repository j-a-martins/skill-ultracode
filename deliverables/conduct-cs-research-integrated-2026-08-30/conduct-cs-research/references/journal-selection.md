# Journal selection and category-specific Q1 evidence

## Contents

1. Separate fit and ranking
2. Verify current facts
3. Record ranking evidence
4. Select an exact destination
5. Portfolio and failure modes

## Separate fit and ranking

Treat scientific fit and ranking evidence as different judgments. Fit covers contribution, methods, audience, article type, editorial practice, and open-science expectations. Ranking evidence asks whether one provider, metric year, and exact subject category place one identified journal in Q1. A poor-fit Q1 journal remains a poor destination.

Build a bounded candidate set from journals publishing nearest work, serving the intended audience, accepting the study family and article type, and imposing policies the project can meet. Check recent relevant articles; do not rely on title keywords or unverified lists.

## Verify current facts

Use current official journal, publisher, ranking-provider, and submission-system sources. Record access dates. Verify exact journal title and ISSN, scope and exclusions, article types, manuscript limits, review model, data/code/ethics/authorship/AI policies, access routes and fees, preprint and prior-publication rules, submission system, and current ranking fields.

Retain conflicts and prefer the source responsible for the fact. Ask the journal when ambiguity controls eligibility.

## Record ranking evidence

A local Q1 observation requires:

- journal and checksum-valid ISSN;
- provider and metric name;
- metric year and exact category;
- quartile, with rank and denominator together when available;
- a journal-specific authoritative HTTPS record;
- verification date;
- local evidence bytes and SHA-256;
- human verifier and timezone-aware verification time.

Do not use a provider homepage, search snippet, aggregator, marketing page, or manually typed list as the evidence record. Multiple category observations for one journal are valid separate rows. Keep fit fields identical across those rows.

The scorer validates local structure, dates, domain plausibility, ISSN, and evidence bytes. It neither fetches the provider page nor authenticates the remote capture or human verifier. Describe PASS as a complete local evidence record, not cryptographically authenticated remote truth.

## Select an exact destination

Use `scripts/score_journals.py`; default ordering is scientific fit. `--verified-q1-only` is an explicit eligibility filter, not a score bonus.

Write `publication/selected-journal.json` with:

- `journal` and `issn`;
- `fit_rationale` and timezone-aware `selected_at`;
- `q1_claim`: `verified`, `provisional`, or `not-claimed`.

For `provisional` or `not-claimed`, the journal/ISSN identity may have several category rows. For `verified`, also record the exact `provider`, `metric_year`, `category`, and `evidence_sha256`. That tuple must match one and only one currently verified candidate observation.

Before acting, inspect journal legitimacy, institution or funder recognition, editorial transparency, fee disclosure, indexing claims, correction policy, solicitation legitimacy, article availability, and conflicts with other submissions.

## Portfolio and failure modes

Prepare a small ordered portfolio: first choice, close-fit alternative, and conservative alternative. Record fit, ranking-evidence status, reframing cost, fee exposure, policy risks, and extra work. Re-verify before resubmission.

Reject a process that optimizes quartile before fit, omits ISSN/provider/year/category, collapses category rows into a timeless label, uses stale or generic evidence, treats a local PASS as remote authentication, ignores article-type or methods mismatch, hides fees, predicts acceptance from impact metrics, or preserves a ranking claim after its evidence changes.
