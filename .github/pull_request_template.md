## What changes

<!-- one or two lines: what the user notices -->

## Changelog

[...autoGenerate]

## Checklist

- [ ] Release? The branch is `release/X.Y.Z` and `VERSION` says the same (no other PR needs a version)
- [ ] `./run-tests.sh` ends with `ALL GREEN`
- [ ] `RUN_E2E=1 ./run-tests.sh` passed when a screen, a flow or the protocol changed
- [ ] New panel text is English inside `tr()` with its line in `PT_BR` in `tray/i18n.py`
- [ ] New app text is in `android/res/values/strings.xml` and `values-pt/strings.xml`
- [ ] Changed the protocol? Updated `docs/api.md`, the server and `PcClient.java`, and the app in the wild still works
- [ ] Changed `pyproject.toml`? Ran `uv lock` and exported `requirements-dev.txt`
- [ ] Changed the screens? Regenerated the GIFs with `e2e/record_demos.py`
