# AHP Feedstock

Research software for exploratory feedstock classification using the Analytic Hierarchy Process. Maintained independently of the academic website and the LCA calculator.

## Status

Repository organization and browser execution prototype. Scientific model M2 is experimental; weights are provisional. No validated final classification, legal designation or automatic LCA boundary is produced. Software registration and public release have not been completed.

## Local use

Python 3.10 or newer:

```sh
python -m pip install -r requirements-dev.txt
python -m pytest tests -q
```

For the existing Python server, set `AHP_ENABLE_DRAFT=1` and run:

```sh
python -m uvicorn app.server:app --host 127.0.0.1 --port 8000
```

## Browser edition

```sh
python scripts/build_pages.py
python -m http.server 8011 --bind 127.0.0.1 --directory dist
```

Open http://127.0.0.1:8011/. The browser edition loads Python and NumPy through a pinned Pyodide runtime. It runs the preserved engine in a worker, without a remote calculation server. Network access to the runtime CDN is needed on first load. The build contains only an explicit allowlist of application files, never the manuscript or project workspace.

## Organization

- `engine/`: original Python scientific engine and synthetic reference configuration.
- `app/`: retained local web application and sensitivity layer.
- `web/`: browser execution adapter; not a replacement scientific engine.
- `tests/`: computational and interface checks.
- `scripts/`: reproducible build and integrity checks.
- `docs/`: architecture, governance and release instructions.
- `provenance/`: original engine hashes; no local absolute paths.
- `dist/`: generated static site, ignored by Git.

See [project context](docs/PROJECT_CONTEXT.md), [release workflow](docs/RELEASE.md) and [rights status](RIGHTS.md). Browser compatibility and scientific validation are different checks. Do not cite an untested preview as the article release.
