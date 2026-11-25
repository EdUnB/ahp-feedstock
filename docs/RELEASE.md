# Release workflow

1. Develop in a branch and record the change.
2. Install requirements-dev.txt and run pytest plus the integrity check.
3. Build the static site and test baseline, sensitivity, invalid inputs, exports, mobile layout and repository subpath loading in a browser.
4. Compare browser outputs to the preserved Python engine, including all 54 state combinations, extreme weights, ties and the article demonstration where authorized.
5. Review distributable files and rights metadata. Do not include private source records.
6. Create a reviewed release tag and package. Do not silently update a release cited by an article.
7. Enable Pages and its PAGES_DEPLOY_ENABLED variable only for an authorized public preview or release; dispatch the manual workflow.
8. Verify the actual public URL before announcing publication.
9. For article submission, archive the exact reviewed version with DOI; retain newer development separately. Software registration identifiers are added only after issuance.

A repository can be prepared privately before its public preview. No automatic deployment runs from ordinary pushes.
