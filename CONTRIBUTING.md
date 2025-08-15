# Contributing

Thanks for considering contributing!

## Development setup
1. Install dev tools: `pip install -U black ruff pre-commit qgis-plugin-ci`.
2. Install hooks: `pre-commit install`.
3. Generate resources: `./build_resources.sh` (macOS/Linux) or `pyrcc5 -o resources_rc.py resources.qrc` (Win).

## Code style
- Follow **PEP 8** (enforced by **Black** and **Ruff**).
- Keep functions small and with docstrings for clarity.

## Packaging
- Run `qgis-plugin-ci package` to create the ZIP in `dist/`.

## Releasing
- Create a tag like `v1.1.0`; GitHub Actions will build the ZIP and create a release.
- To publish to plugins.qgis.org, add repo secrets `QGIS_PLUGIN_REPO_USERNAME` and `QGIS_PLUGIN_REPO_PASSWORD`.