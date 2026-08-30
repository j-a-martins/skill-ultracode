# Software-engineering adversarial and overengineering review

## Adversarial review

The release gate exercises the following architecture-specific attacks:

- a bounded request attempts to trigger the full lifecycle and all references;
- a user explicitly instructs the model to preload every reference;
- a generic coding or business-writing request attempts to trigger the academic skill;
- a LaTeX copyedit attempts to load unrelated search, journal, and experiment material;
- confidential peer-review material attempts to bypass policy and confidentiality routing;
- a development test file is inserted into the runtime package;
- a helper's `--help` path creates files or mutates source bytes;
- core instructions repeat a long paragraph already owned by a reference;
- an archive contains traversal, aliasing, links, devices, bytecode, or nondeterministic metadata;
- a test run succeeds only under one hash seed, one Python version, or the source tree but not clean extraction.

Remediation is fail-closed: route narrowly, load conditionally, keep tests outside runtime, snapshot helper side effects, run two Python versions and multiple hash seeds, rebuild archives independently, and rerun from clean extraction.

## Overengineering review

The following additions were rejected:

- a vector database or retrieval service for nine bounded references;
- a plugin or agent framework for four routes;
- a second project auditor split only to reduce file length;
- a bespoke YAML parser dependency in the installable skill;
- runtime network clients for journal or literature providers;
- separate skills for search, review, and prose after semantic integration;
- a persistent daemon or autonomous background-search loop;
- cryptographic approval chains for ordinary stage transitions;
- shipping tests, evaluations, reports, or release tooling with the runtime skill;
- combining all reference material into one large document.

The retained architecture uses the smallest stable boundaries that have distinct loading conditions or deterministic responsibilities. The largest runtime module remains monolithic only where its validators share schemas, state, and cross-link invariants. The release and test infrastructure remains outside the installable folder.

## Residual boundaries

Token budgets do not prove that every model will obey conditional loading. Runtime evaluations must still test triggering and route selection after installation. Static code and LaTeX audits cannot prove scientific correctness or arbitrary TeX safety. Standard-library-only code reduces dependency risk but does not eliminate implementation defects. Current journal, policy, and reporting facts still require authoritative retrieval at use time.
