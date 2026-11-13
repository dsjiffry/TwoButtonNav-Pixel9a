# Building a release (maintainers)

Every release is built for one Pixel 9a (`tegu`) Android build. The builder refuses any other
device.

## Requirements

* Python 3.10+ (3.14+ for OTAs that use zstd compression)
* Java 17+
* [apktool](https://apktool.org/) 3.x, saved as `tools/apktool.jar`
* Android SDK build-tools (`zipalign`, `apksigner`); found via `ANDROID_HOME` or `--build-tools <dir>`
* 7-Zip (to read the OTA's ext4 partition), or adb with a Pixel 9a for phone input

## Build

```bash
# from Google's full Pixel 9a OTA: https://developers.google.com/android/ota#tegu
python build_module.py --ota tegu-ota-<build>.zip
```

Alternatives: run `python build_module.py` with a Pixel 9a connected over adb (no root
needed), or pass `--apk <launcher.apk> --device-path <path> --built-for <fingerprint>
--security-patch YYYY-MM-DD`.

The builder prints the release tag and writes into `out/`:

| File | Use |
|---|---|
| `TwoButtonNav-tegu-<BUILD_ID>-<version>.zip` | The module (to test on a phone; **not** published) |
| `TwoButtonNav-tegu-<BUILD_ID>-<version>.zip.sha256` | Checksum of your local zip |
| `release-notes-<version>-<BUILD_ID>.md` | Release description, including the exact OS version, prerequisites and build steps |

If any patch doesn't match the launcher (Google changed the code), the build stops and no zip
is made.

## Publish a release

Releases are **source only**. Never attach the zip: it contains Google's (patched) launcher.

1. Build as above and test the zip on a Pixel 9a on that build.
2. Add a row (newest first) to the **Which release do I need?** table in `README.md`, commit
   and push.
3. Create a GitHub release:
   * tag: `<version>-<BUILD_ID>` (e.g. `v3.2-CP4A.261105.040.A1`) on the pushed commit
   * title: first line of the release notes file (without the `# `)
   * description: the rest of the release notes file
   * assets: none (GitHub adds the source code archives)

When patches or module scripts change, bump `VERSION` / `VERSION_CODE` at the top of
`build_module.py`, add a `CHANGELOG.md` entry, and rebuild every build still listed in the README.

## Signing key

The first build creates `keystore/twobtn.p12`, the private key that signs the patched
launcher. It is git-ignored: **never commit or share it**, and back it up. Use the same key
for every release. Set `TWOBTN_KEYSTORE` / `TWOBTN_KEYSTORE_PASS` to keep it elsewhere or use
another password.

## Project layout

| Path | Contents |
|---|---|
| `build_module.py` | Patches the launcher and packages the module |
| `ota_extract.py` | Pulls the Pixel Launcher out of a full OTA's `payload.bin` |
| `patch/` | Helper classes (smali) added to the launcher |
| `module_template/` | Module scripts and the 2-button framework overlay |
