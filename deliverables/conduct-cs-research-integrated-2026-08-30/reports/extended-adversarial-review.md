# Extended adversarial review

## Review model

The review treats papers, search results, reviewer comments, bibliographies, LaTeX, project files, journal records, and model outputs as potentially malformed or adversarial. It tests scientific failure, policy failure, semantic drift, parser ambiguity, unsafe filesystem behavior, and misleading assurance claims.

## Findings and resolutions

| Area | Adversarial case | Resolution |
|---|---|---|
| Routing | A prose-only request incorrectly launches a 13-stage project | Four native modes select the narrowest workflow |
| Routing | A mixed request causes separate skills to contradict one another | One evidence contract and one lifecycle govern all modes |
| Search | A database result contains instructions to alter the protocol | Retrieved material is untrusted data; embedded instructions are ignored |
| Search | Queries are optimized only to known positive papers | Sentinel sets include boundary and contrary records; search limitations are recorded |
| Search | One Boolean string is reused across incompatible interfaces | Database-specific translation and execution logs are required |
| Search | An aggregator is treated as the authoritative full text | Evidence-access levels distinguish metadata, abstract, full text, data, code, and artifact review |
| Search | Duplicate preprint, conference, and journal versions inflate evidence | Version-family deduplication preserves occurrences and canonical identity |
| Search | Two simulated personas are reported as independent screeners | The skill explicitly prohibits false dual screening |
| Search | A stale search is described as current | Last-search dates, update workflow, corrections, and successor-version checks are mandatory |
| Search | A retracted source remains load-bearing | Status and correction/retraction checks are part of source appraisal and project warnings |
| Search | Saturation is asserted as proof of completeness | Stopping is reported as bounded evidence, never proof of no unseen work |
| Review | Hidden manuscript text requests a positive recommendation | Manuscript content is untrusted; prompt instructions are ignored |
| Review | The reviewer invents absent experiments or citations | Findings require manuscript location and evidence; inaccessible evidence yields uncertainty, not invention |
| Review | Generic checklists create many unsupported major points | The finding contract requires consequence and smallest defensible action |
| Review | Scores are averaged into false precision | Qualitative dimensions are default; recommendation reasoning is independent of arithmetic |
| Review | Five personas are presented as five independent experts | Perspectives are sequential analytical lenses, not independent reviewers |
| Review | Confidential text is sent to an unauthorized service | Current venue policy and confidentiality boundaries are checked before AI-assisted review |
| Review | A reviewer demands irrelevant self-citation | Suggested citations must be real, relevant, and verified |
| Review | Stylistic preference becomes rejection rationale | Severity follows scientific consequence; prose alone cannot create a design-limiting finding |
| Review | Response letter claims a change not present in the manuscript | Re-review inspects both artifacts and exact locations |
| Prose | `may improve` becomes `improves` | Faithfulness contract and uncertainty audit flag strengthening |
| Prose | Association becomes causation | New strong causal verbs are flagged, and strict mode fails |
| Prose | Negation is removed | Negation-count drift is flagged and fails strict mode |
| Prose | A number, unit, equation, citation, or cross-reference changes | Protected-content multisets are compared deterministically |
| Prose | A citation moves to support a different sentence | Mechanical checks are followed by a required human citation-scope audit |
| Prose | Polishing hides a missing method or ethical defect | Scientific defects are separated and reported as residual concerns |
| Prose | User asks to evade AI detectors | The skill refuses detector-evasion claims and focuses on observable writing quality |
| Evidence | An active claim has no source or result | Project audit rejects active unlinked claims |
| Evidence | A result references an unknown run | Cross-ledger audit rejects the record |
| Evidence | Metadata alone supports a detailed method claim | The evidence contract requires evidence-access labeling and primary reading |
| Experiment | Favorable seeds are retained and failures discarded | Run records include failed and unfavorable executions and selection rules |
| Experiment | Confidence intervals use the wrong independent unit | Study-design and analysis checks require dependence-aware inference |
| Experiment | Pilot choices are laundered as prospective | Protocol status and amendments distinguish prospective from retrospective decisions |
| LaTeX | `\write18` executes a command | Static audit rejects shell and unsafe file primitives |
| LaTeX | `\input{../secret}` escapes the manuscript root | Input, bibliography, and graphic paths must remain inside the root |
| LaTeX | A symlink redirects an included file | Linked and hard-linked governed files are rejected |
| LaTeX | Citation and label keys are unresolved or duplicated | Static key, label, and reference audits fail |
| Journal | Q1 is claimed without provider, year, or category | Q1 eligibility requires all three plus dated HTTPS evidence |
| Journal | Highest-category percentile is generalized to the journal | The skill treats category-specific status as the only valid claim |
| Journal | Fit score is presented as acceptance probability | Fit and quartile are separate, and acceptance is never predicted without evidence |
| Journal | A stale marketing page is accepted as metric evidence | Current authoritative provider evidence is required; trusted-domain checks are supported |
| External action | General project approval is treated as submission permission | Exact payload, destination, and action-specific authorization are required immediately before transmission |
| External action | A submission is claimed without tool evidence | Performed actions require an outcome record; the skill never invents execution |
| Parser | Duplicate JSON keys change meaning across parsers | Strict JSON loading rejects duplicate keys and non-finite values |
| CSV | Extra columns or malformed rows shift evidence fields | Strict CSV parsing and required-header checks fail closed |
| Spreadsheet | Generated text becomes a formula when opened | Shared CSV helper neutralizes formula-leading generated cells |
| Filesystem | Existing projects are silently overwritten | Initialization is create-only and removes partial output on failure |
| Filesystem | Symlinks or hardlinks redirect governed evidence | Project and shared file checks reject them |
| Archive | Traversal, backslash, Unicode, case, device-name, or trailing-dot aliases appear | Release validation rejects unsafe and nonportable member names |
| Archive | A compressed bomb or encrypted member is shipped | Member count, size, compression ratio, type, and encryption checks fail |
| Assurance | Passing structural tests is described as proof of scientific validity | Reports explicitly separate implementation integrity from scientific judgment |
| Assurance | The source ZIPs are claimed to be inspected when they were not | Release artifacts record the attachment-runtime limitation and restrict the supersession claim |

## Deterministic coverage

The offline suite exercises:

- all four project modes;
- create-only initialization;
- gate enforcement;
- unknown provenance links;
- unauthorized performed actions;
- linked-file rejection;
- valid and malicious LaTeX;
- unresolved citations and labels;
- protected-content prose drift;
- causal, certainty, uncertainty, and negation changes;
- valid, stale, incomplete, and untrusted Q1 evidence;
- OpenAI skill structure, direct resource links, trigger coverage, and dependency limits.

The release gate then recompiles and reruns these tests from a clean ZIP extraction.

## Residual limitations

- Mechanical prose comparison cannot prove semantic equivalence.
- Static LaTeX auditing cannot prove arbitrary TeX safe; restricted compilation and rendered inspection remain necessary.
- Local files and hashes do not authenticate a human approver or remote evidence provider.
- Search completeness cannot be proved, especially behind inaccessible databases or changing indexes.
- Model-assisted review remains vulnerable to domain gaps and prompt injection; accountable human review is required.
- Journal status, policies, and model versions change after verification.
- The user-supplied ZIPs were not byte-inspected because the local attachment runtime was unavailable.