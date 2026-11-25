# Project context

AHP Feedstock supports an experimental absolute-measurement AHP model for waste, by-product and co-product candidate priorities. The source baseline is the internal application dated 2026-11-12, interface version 2.0. The repository organization begins at version 0.1.0-preparation; this does not rename or recalibrate the scientific engine.

The browser edition uses the same Python files and NumPy in Pyodide. web/bridge.py supplies a transport adapter. app/sensitivity.py and app/stability.py remain unchanged. app/server.py remains the local FastAPI edition. Published static files must use project-relative resource paths so that GitHub Pages repository subpaths work.

The article, supplementary material and original LCA reference results are outside this repository. The LCA S3 energy reference remains 594.31 g CO2e/MJ in its own project. The AHP repository does not implement the LCA engine.

Scientific validation, software verification, public hosting, DOI archiving and software registration are separate statuses. Record each accurately in releases. No affiliation or right of ownership is inferred from an account name.
