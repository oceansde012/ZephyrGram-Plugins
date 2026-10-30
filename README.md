# ZephyrGram plugins

Plugin store repository for the ZephyrGram Android client. Plugins are single Python
files (`<id>.plugin`) using the API documented in [docs/API.md](docs/API.md).
The app downloads a signed `index.json` from the `index` branch of this repository.

Layout:

```
plugins/<id>/<id>.plugin     the plugin (required)
plugins/<id>/CHANGELOG.md    "## <version>" sections; text shown in the store
plugins/<id>/icon.png        optional PNG <= 64 KB
plugins/<id>/meta.json       optional {"tags": ["tools", ...]}
plugins/<id>/revoked.json    optional [version_code, ...] to pull bad versions
templates/hello.plugin       starting point
docs/API.md                  plugin API v1
tools/build_index.py         validate / build / sign / verify / keygen
tools/keygen.md              owner-only: signing key setup
.github/workflows/publish.yml
```

## Publishing a plugin

1. Copy `templates/hello.plugin` to `plugins/<id>/<id>.plugin` (directory name,
   file name and `__id__` must be identical, `^[a-z][a-z0-9_]{2,31}$`).
2. Fill in the metadata (plain literals only) and write the plugin.
3. Add `plugins/<id>/CHANGELOG.md` with a `## <version>` section.
4. Run `python tools/build_index.py validate` locally.
5. Open a pull request (CI validates it). After merge to `main`, the `publish`
   workflow builds, signs and publishes the index; the store shows the plugin within
   minutes (the app checks at start if the last check is older than 6 h, and when the
   store is opened if the cache is older than 5 min).

Rules enforced by CI: valid id and matching names; types as in the API doc; SemVer
`__version__`; known permissions only; file compiles (`py_compile`); UTF-8, LF, no BOM,
no binaries, at most 512 KB; no stray files.

## Versioning rules

- Any change to the `.plugin` file must bump `__version_code__` (integer, strictly
  greater than every published one) **and** `__version__` (SemVer, greater than the latest).
  CI fails otherwise, and also on a version_code regression.
- Adding a permission is allowed but the app holds the update until the user approves.
- Use `__min_app_version__` / `__max_app_version__` (exclusive) to restrict app versions;
  `__api_version__` is `1`.
- The index keeps up to 10 versions per plugin, newest first. Published entries are
  immutable: their URLs are pinned to the commit that introduced them and carry a sha256.
- To pull a broken version, list its `__version_code__` in `plugins/<id>/revoked.json`
  and publish a fixed higher version. Revoked versions are never installed and
  installed copies are disabled with a notice.
- Removing a plugin directory lists the id under `removed`; the app uninstalls it.

## How the app updates

- Index: `https://raw.githubusercontent.com/oceansde012/ZephyrGram-Plugins/index/index.json`
  plus `index.json.sig` (fallback: `cdn.jsdelivr.net/gh/oceansde012/ZephyrGram-Plugins@index/`).
- The app verifies the Ed25519 signature against its built-in public keys, rejects an
  index whose `sequence` is lower than the last seen one, and keeps the cached copy
  (marked stale) when the index is expired. The workflow re-signs weekly; `expires` is
  generated + 60 days.
- For each installed plugin the app picks the highest non-revoked `versionCode` that
  supports its plugin API and app version, downloads the pinned URL, checks sha256 and
  size, and swaps the file atomically (previous version kept for rollback). Auto-update
  can be toggled globally and per plugin.

## Owner setup

See [tools/keygen.md](tools/keygen.md). Short version:

```
python tools/build_index.py keygen --out C:\secure\zephyr_index_key.pem
gh secret set INDEX_SIGNING_KEY --repo oceansde012/ZephyrGram-Plugins < C:\secure\zephyr_index_key.pem
```

Then paste the printed public key bytes into `PluginRepository.PUBLIC_KEYS` in the app.

## Tooling

```
python tools/build_index.py validate
python tools/build_index.py build --sha <40-hex> [--prev prev.json] --out out/index.json
python tools/build_index.py sign --index out/index.json --key key.pem
python tools/build_index.py verify --index out/index.json --pubkey <base64>
```
