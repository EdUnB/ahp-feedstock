# AHP Feedstock project instructions

- This repository is independent of EdUnB/edunb.github.io and of the LCA calculator. Never change either as a side effect.
- Preserve all original engine modules and the original reference JSON. Run scripts/check_integrity.py after changes.
- C1 is discard status; C2 is productive intentionality; C3 contains market significance and generation responsiveness. Infrastructure and processing remain outside the weighted M2 score.
- Reference weights 60/20/20 and C3 75/25 are provisional, not necessarily definitive article weights.
- Candidate priorities are exploratory. Never convert missing evidence to proof of incidental generation or automatically infer a legal category, LCA boundary or allocation.
- Keep source, tests, documentation and generated outputs separate. Build dist only through scripts/build_pages.py.
- No manuscript, unpublished personal material, credentials, commercial inventories, local paths or private evidence records in the repository or generated site. Use synthetic examples.
- Use one repository per software. Record changes in CHANGELOG.md. Keep reviewed publication versions on immutable release tags.
- Before publication, run computational checks and browser equivalence checks. A passing software check is not scientific validation.
- No automatic public deployment during preparation. The manual Pages workflow publishes only when explicitly dispatched and the repository variable PAGES_DEPLOY_ENABLED is true.
- Do not invent a license, DOI, registration identifier, authorship list or completed validation. Record unresolved ownership and licensing in RIGHTS.md.
