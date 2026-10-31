# Release

`VERSION` is the single source of the version. It feeds the app's `versionName`, and `versionCode` is computed from it.

1. Work on `dev`, in commits of one line in English.
2. Open a PR from `dev` to `main`, bumping `VERSION`. `auto-complete-fields.yml` refuses a version already released,
   assigns the author, adds labels, lists the commits where the template has `[...autoGenerate]` and sets the title to
   `Release vX.Y.Z - ...`.
3. On merge, `create-tag-and-release.yml` creates the tag `vX.Y.Z` and the GitHub release, with the source tarball and
   `SHA256SUMS`. Tags always have the `v` prefix, so they never collide with a branch name.

## Signed APK

The release carries an APK when the repository has these secrets. Without them it has the source only, because an APK
signed with a throwaway key could not update the previous one.

| Secret | Value |
| --- | --- |
| `ANDROID_KEYSTORE_BASE64` | `base64 -w0 release.keystore` |
| `ANDROID_KEYSTORE_PASSWORD` | Its password |
| `ANDROID_KEY_ALIAS` | The alias of the key |

Create the key once and keep it safe, since losing it means every phone has to reinstall the app:

```bash
keytool -genkeypair -keystore release.keystore -alias lan-file-share -keyalg RSA -keysize 4096 -validity 10000
```

The phone installed from a debug build has to uninstall it before moving to the signed one.

## Updating dependencies

| What | How |
| --- | --- |
| Python tools | Change `pyproject.toml`, `uv lock`, then the export command in `setup-dev.sh` |
| Android jars | Change `android/libs.lock`, compare the download with the `.sha1` Maven publishes, pin its SHA-256 |
| Maestro | Change `e2e/maestro.lock` with the SHA-256 from its release |
| GitHub Actions | Dependabot opens the PR, pinned by commit |
