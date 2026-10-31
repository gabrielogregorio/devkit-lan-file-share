# CLAUDE.md - LAN File Share

Rules and context for any agent or person who touches this project. Read it before editing. Code, comments,
logs, file names, commits and docs are in English. The app and the panel speak English and Brazilian Portuguese.

## 1. What it is

Share anything from an Android phone to a folder on an Ubuntu PC, over the local network, with no cloud and no
account. Two pieces: a top bar icon that turns a receiving server on and off, and an Android app that shows up in
the share sheet. Phone to PC only for now; `/api/v1` is versioned so the other direction can come later.

## 2. Priorities

In any change, preserve in this order:

1. keys and files never leave the user's control
2. authentication on the server, never trusted to the app
3. no file lost or overwritten
4. clarity of the code
5. types
6. test coverage
7. performance

In a conflict: safety beats convenience, clarity beats short code.

## 3. Map

```
server/              stdlib only, runs on the system python3
  settings.py        the ONLY module that reads the environment
  http_api.py        routes, kept thin; FileShareServer
  storage.py         Inbox: writes .part, renames when complete
  keys.py            KeyStore: keys.json, file lock, shared with the tray
  proofs.py          HMAC proofs, pinned to Protocol.java by tests/vectors.txt
  lockout.py         LoginGuard
  body.py names.py network.py discovery.py certificate.py config_store.py private_file.py main.py
tray/                the icon and the panel
  panel_data.py      everything the panel shows, free of GTK and tested
  panel.py indicator.py    GTK, imported only when the icon starts
  i18n.py icons.py process.py desktop_entry.py app_info.py
tray_icon.py         entry point
android/             Java, no gradle. See android/README.md
e2e/                 emulator suite and the GIF recorder
tests/               process-level tests and repository rules; unit tests sit next to their code
docs/                api.md, security.md, release.md, adr/
```

## 4. Hard rules

- **Never run automated E2E on a real phone.** `e2e/run.py` refuses it. A real phone is only for fixing a bug or
  validating when a person asks.
- **Never touch an emulator of another project.** `e2e/run.py` and `e2e/emulator.sh` check the AVD name for this.
  Another one running on 5554? Use `E2E_EMULATOR_PORT=5556` and `E2E_DEVICE=emulator-5556`.
- **Never run the E2E with a real server up.** The emulator's broadcast reaches the host and pairs with it, which
  writes a key into the real `keys.json`. `e2e/run.py` refuses when port 8908 is busy.
- **Real keys and QR codes never go into a commit or an image.** Images come from `e2e/record_demos.py`, which uses a
  throwaway home folder.
- **The protocol has apps in the wild.** Adding a field is fine; changing one needs a new `/api/v2` route. The app
  reads only the HTTP status of an error.
- **GET changes nothing.** `/api/v1/hello` does not even record the use of a key.
- **No dependency at runtime.** The server and the tray use the standard library plus apt packages. The Android jars
  live in `android/libs.lock`.
- **Pin versions and hashes of everything**: `uv.lock`, `android/libs.lock`, `e2e/maestro.lock`, actions by commit.
- **The tray has no Quit item**, starts off at login, is gray when off and colored on air, and only errors notify.

## 5. Code style

Python has type annotations everywhere (`mypy --strict` runs in CI) and no `from __future__ import annotations`.
Java has `if`, `for`, `while` and `else` always in blocks with braces.

- Blank line before `return`, unless it is the first statement of the block.
- `total += 1`, never `total++`.
- Early return instead of `else`. No nested ternaries: extract a function with early returns.
- Descriptive names always, in loops and callbacks too: `key_record`, `index`, `view`. Never `k`, `s`, `x`, `e`, `i`.
  An unused parameter starts with `_` in Python or says why it is ignored in Java (`waitedEnough`).
- No magic numbers or arrays: a named constant says what it is.
- Dynamic text inside a message goes between double quotes: `'upload of "%s" failed'`. It exposes stray spaces.
- Never the em dash character. Use a hyphen.
- Around 200 to 400 lines per file; past 500, split by responsibility.
- Do not import something only to export it again.
- Regex: compiled once at module level, anchored, bounded, on input of limited size, no nested quantifiers.
- Logs explain the operation and never carry a secret, a key or a proof. Every refusal logs its `request_id`.
- Text the person reads goes through `tr()` with a line in `PT_BR`, or in both `strings.xml`. Tests fail on a gap.

### Comments

A comment is the exception, for what the code cannot say: non-obvious behavior, a workaround, a security restriction.

- First try a better name, an extracted function or an early return.
- A good name kills the comment: do not write both.
- A comment describes the code as it is now, never the path to it. Nothing like "removed", "used to", "on purpose
  not", and never the task that caused the change. Reasons that matter go in the commit, in an ADR or in the docs.
- No comment block at the top of a test file.

## 6. Android ids and Maestro

The id names the role of an element, never the instance: every row of the list is `history_row`, never `row_3` or
`row_report_pdf`. A list row and each action inside it need an id; the id goes on the element that receives the tap.
Taps use ids, so they survive a language change. Text in a flow is for what the person must read, or for data such
as a file name. `tests/test_repository_rules.py` fails when a flow uses an id that no layout declares.

## 7. Tests

Unit tests sit next to the file they test (`server/keys.py`, `server/keys_test.py`). JUnit is the exception, in
`android/test/`, since everything under `android/src` goes into the APK.

Run what the change can break, not everything by reflex:

| Change | Run |
| --- | --- |
| Lint, log, comment, a constant renamed | `.venv/bin/ruff check .` |
| Logic of a function | ruff + the test file of that code, `.venv/bin/pytest --no-cov server/keys_test.py` |
| Server route, protocol or `PcClient` | `./run-tests.sh` |
| A screen, a flow, the manifest, the build | `RUN_E2E=1 ./run-tests.sh` with the emulator up |

A test failed? Run that test alone to read the error, not the whole suite again.

What a test must do:

- **Assert the value, not the existence.** `assert stored.size == 11`, never `assert stored`.
- **Think of the mutant.** If flipping an `if` or swapping `<` for `<=` breaks no test, the test is decoration. Test the
  boundary: `MAX_FAILURES - 1` does not lock, `MAX_FAILURES` does.
- **No magic number.** Import the constant from the code under test.
- **Cover the error path** and the denied side effect: the refused upload that must leave no file.
- **Behavior, not implementation.** A test breaks only when something observable breaks.
- **One scenario per test**, named as a sentence, with no `if` or `for` in the body: use `parametrize`.
- **Do not test the library**, and do not write a test that cannot fail. Move a decision to a pure function next to
  its code (`Failure.of`, `PairingPlan.choose`, `key_state`) and test that.
- **Freeze time by injection.** `KeyStore` and `LoginGuard` take a `clock`, `Names.textFile` takes a `Date`. A test never
  depends on the real clock.
- A bug comes with a regression test.

## 8. Layout checks

A change to the panel or to a screen is looked at, not only tested: the panel at its fixed 640 px, the app at 320 and
at 412 dp, in English and Portuguese, light and dark. `e2e/record_demos.py` regenerates the images in the README.

## 9. Release

See `docs/release.md`. `VERSION` is the single source of the version; a PR into `main` that bumps it creates the tag
`vX.Y.Z`. Tags always have the `v` prefix, so they never collide with a branch name.
