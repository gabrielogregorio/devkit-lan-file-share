# Release

A release comes only from a branch named `release/X.Y.Z`. Any other PR into `main` merges without a new version and
publishes nothing, so day-to-day changes and Dependabot never have to touch `VERSION`.

`VERSION` feeds the app's `versionName`, and `versionCode` is computed from it, so on a release branch it must say the
same as the branch name.

1. Work on `dev`, in commits of one line in English, and merge into `main` through PRs as often as you like.
2. To release, branch off `dev` and set the version:

   ```bash
   git switch -c release/1.2.3 dev
   echo 1.2.3 > VERSION
   git commit -am "Release 1.2.3"
   git push origin release/1.2.3
   ```

3. Open a PR from `release/1.2.3` to `main`. `auto-complete-fields.yml` refuses a badly named branch, a branch that
   disagrees with `VERSION` and a version already released, and sets the title to `Release v1.2.3 - ...`. Every PR gets
   the author, the labels and the commit list where the template has `[...autoGenerate]`.
4. On merge, `create-tag-and-release.yml` runs the same checks and creates the tag `v1.2.3` and the GitHub release, with
   the source tarball and `SHA256SUMS`. Tags always have the `v` prefix, so they never collide with a branch name.

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
