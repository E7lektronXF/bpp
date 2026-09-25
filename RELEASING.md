# Releasing to PyPI

The package is published as **`bpp-format`** (the name `bpp` on PyPI belongs to an unrelated
project). The import name and the command stay `bpp`.

Publishing is automated by `.github/workflows/publish.yml` with PyPI *trusted publishing*, so
no API token is stored anywhere.

## One-time setup

1. Create an account at https://pypi.org and enable 2FA.
2. Open https://pypi.org/manage/account/publishing/ and add a **pending publisher**:
   * PyPI project name: `bpp-format`
   * Owner: `E7lektronXF`
   * Repository name: `bpp`
   * Workflow name: `publish.yml`
   * Environment name: `pypi`

## Each release

1. Bump `version` in `pyproject.toml` and `__version__` in `src/bpp/__init__.py`.
2. Commit and push to `main`; wait for CI to be green.
3. On GitHub: **Releases → Draft a new release**, tag `v<version>` (for example `v0.3.0`),
   then **Publish release**. The workflow builds, checks and uploads the package.
4. Check https://pypi.org/project/bpp-format/ and try `pip install bpp-format` in a clean
   virtualenv.

The first release (0.3.0) was published on 2026-09-25; the READMEs install with `pip install bpp-format`.

## Manual alternative

```bash
python -m pip install build twine
python -m build
python -m twine check dist/*
python -m twine upload dist/*      # asks for a PyPI API token
```

## Playground (GitHub Pages)

The browser playground is `docs/index.html`, built from `site/playground.html` and `js/bpp.js`:

```bash
python site/build.py
```

One-time setup: **Settings → Pages → Build and deployment → Deploy from a branch**, branch
`main`, folder `/docs`. The page is then served at https://e7lektronxf.github.io/bpp/.
Rebuild and commit `docs/index.html` whenever `js/bpp.js`, the examples or the template change.
