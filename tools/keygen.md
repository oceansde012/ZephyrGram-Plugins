# Generating the index signing key (one time, owner only)

The app trusts an index only if `index.json.sig` is a valid Ed25519 signature
(over the exact bytes of `index.json`) by a key in `PluginRepository.PUBLIC_KEYS`.

## 1. Generate

```
pip install cryptography
python tools/build_index.py keygen --out C:\secure\zephyr_index_key.pem
```

The command refuses to write inside this repository. It prints:

- the base64 public key,
- a Java `new byte[]{...}` literal, ready to paste as an entry of
  `PluginRepository.PUBLIC_KEYS`,
- the same key as hex.

Back up the PEM somewhere safe (password manager). Never commit it.

## 2. Store as a GitHub secret

```
gh secret set INDEX_SIGNING_KEY --repo oceansde012/ZephyrGram-Plugins < C:\secure\zephyr_index_key.pem
```

(PowerShell: `Get-Content -Raw C:\secure\zephyr_index_key.pem | gh secret set INDEX_SIGNING_KEY --repo oceansde012/ZephyrGram-Plugins`)

## 3. Put the public key into the app

Add the printed byte array to `PluginRepository.PUBLIC_KEYS` and ship an app
release **before** (or together with) the first published index.

## Rotation

`PUBLIC_KEYS` is an array; the app accepts a signature from any of them.

1. Generate a new key; ship an app release containing both public keys.
2. Wait until most users updated.
3. Replace the `INDEX_SIGNING_KEY` secret with the new key.
4. Later release may drop the old public key.

If the key leaks: do step 1-3 immediately; also publish an app release that removes
the leaked public key.

## Local test

```
python tools/build_index.py build --sha 0123456789012345678901234567890123456789 --out out/index.json
python tools/build_index.py sign --index out/index.json --key C:\secure\zephyr_index_key.pem
python tools/build_index.py verify --index out/index.json --pubkey <base64 public key>
```
