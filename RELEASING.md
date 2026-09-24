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
3. On GitHub: **Releases → Draft a new release**, tag `v<version>` (for example `v0.2.0`),
   then **Publish release**. The workflow builds, checks and uploads the package.
4. Check https://pypi.org/project/bpp-format/ and try `pip install bpp-format` in a clean
   virtualenv.

After the first release, the README's install command can become `pip install bpp-format`.

## Manual alternative

```bash
python -m pip install build twine
python -m build
python -m twine check dist/*
python -m twine upload dist/*      # asks for a PyPI API token
```
