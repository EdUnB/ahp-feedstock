# FeedClass

**Open the experimental browser preview:** https://edunb.github.io/ahp-feedstock/

Research software for exploratory feedstock classification using the Analytic Hierarchy Process. Maintained independently of the academic website and the LCA calculator.

## Status

Browser edition tested in Chrome, including 54 state combinations against the original Python engine, sensitivity controls, JSON/CSV exports and mobile width. Scientific model M2 is experimental; weights are provisional. No validated final classification, legal designation or automatic LCA boundary is produced. This is an experimental preview, not a registered or externally validated scientific release. Software registration remains pending.

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

See [project context](docs/PROJECT_CONTEXT.md), [release workflow](docs/RELEASE.md) and [rights status](RIGHTS.md). The public GitHub Pages preview was verified in Chrome on 2026-11-25. Browser compatibility and scientific validation are different checks. See docs/browser-verification.json for the recorded browser checks. Do not cite an untested preview as the article release.

## Browser audit

Generate the native reference fixtures with `python scripts/generate_browser_fixtures.py`, build the site, start `python scripts/serve_preview.py`, then run `node scripts/browser_audit.cjs`. The audit uses a separate Chrome profile. Set BROWSER_EXE when Chrome is installed elsewhere. Test reports and screenshots remain in ignored local-private/.

## Identity

FeedClass is the approved public-facing name. The original AHP Python engine, model identifiers and reference configuration remain unchanged. The header displays the approved FeedClass logo alongside the original LEA and PCMEC marks.
