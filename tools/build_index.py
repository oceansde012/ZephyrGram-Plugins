#!/usr/bin/env python3
"""ZephyrGram plugin index tool.

Subcommands:
  validate  check every plugin under plugins/ (no output files)
  build     validate + write index.json (history carried over from --prev)
  sign      sign index.json -> index.json.sig (base64 Ed25519 over exact bytes)
  verify    verify index.json against index.json.sig and a public key
  keygen    generate an Ed25519 key pair (private PEM written to --out)

Only the standard library is needed, except `sign`, `verify` and `keygen`
which need `pip install cryptography`.
"""
import argparse
import ast
import base64
import datetime as dt
import hashlib
import json
import os
import py_compile
import re
import sys
import tempfile

SCHEMA = 1
SUPPORTED_API = {1}
MAX_VERSIONS = 10
MAX_PLUGIN_BYTES = 512 * 1024
MAX_ICON_BYTES = 64 * 1024
EXPIRES_DAYS = 60
DEFAULT_REPO = "oceansde012/ZephyrGram-Plugins"
KNOWN_PERMISSIONS = {
    "network.requests", "updates.read", "messages.send", "ui.menu", "internet", "java.raw",
    "ai.complete", "chat.read",
}
ID_RE = re.compile(r"^[a-z][a-z0-9_]{2,31}$")
SEMVER_RE = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$")
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
REQUIRED = ["__id__", "__name__", "__description__", "__author__", "__version__",
            "__version_code__", "__api_version__", "__min_app_version__", "__permissions__"]
OPTIONAL = ["__max_app_version__", "__icon__"]
ALLOWED_FILES = {"CHANGELOG.md", "icon.png", "meta.json", "revoked.json", "README.md"}


class ValidationError(Exception):
    pass


def semver_key(v):
    m = SEMVER_RE.match(v)
    major, minor, patch, pre = m.groups()
    # a release sorts above any pre-release of the same x.y.z
    pre_key = (1, ()) if pre is None else (0, tuple(
        (0, int(p), "") if p.isdigit() else (1, 0, p) for p in pre.split(".")))
    return (int(major), int(minor), int(patch), pre_key)


def sha256_hex(data):
    return hashlib.sha256(data).hexdigest()


def read_metadata(path, errors):
    """Parse top-level `__x__ = <literal>` assignments with ast (no execution)."""
    with open(path, "rb") as f:
        raw = f.read()
    if len(raw) > MAX_PLUGIN_BYTES:
        errors.append("%s: larger than %d bytes" % (path, MAX_PLUGIN_BYTES))
    if b"\x00" in raw:
        errors.append("%s: contains NUL bytes (binary?)" % path)
        return raw, {}
    if raw.startswith(b"\xef\xbb\xbf"):
        errors.append("%s: UTF-8 BOM not allowed" % path)
    if b"\r" in raw:
        errors.append("%s: CR / CRLF line endings not allowed (use LF)" % path)
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as e:
        errors.append("%s: not valid UTF-8 (%s)" % (path, e))
        return raw, {}
    try:
        tree = ast.parse(text, filename=path)
    except SyntaxError as e:
        errors.append("%s: syntax error: %s" % (path, e))
        return raw, {}
    meta = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 \
                and isinstance(node.targets[0], ast.Name):
            name = node.targets[0].id
            if name.startswith("__") and name.endswith("__"):
                try:
                    meta[name] = ast.literal_eval(node.value)
                except ValueError:
                    errors.append("%s: %s must be a plain literal" % (path, name))
    # py_compile for full compile-time checks
    try:
        with tempfile.TemporaryDirectory() as td:
            py_compile.compile(path, cfile=os.path.join(td, "x.pyc"), doraise=True)
    except py_compile.PyCompileError as e:
        errors.append("%s: does not compile: %s" % (path, str(e).strip()))
    return raw, meta


def validate_plugin(plugin_dir, pid):
    """Returns (record, errors). record has everything but url/published."""
    errors = []
    path = os.path.join(plugin_dir, pid + ".plugin")
    if not ID_RE.match(pid):
        errors.append("directory name '%s' is not a valid plugin id %s" % (pid, ID_RE.pattern))
    if not os.path.isfile(path):
        return None, ["%s: missing %s.plugin" % (pid, pid)]
    for name in sorted(os.listdir(plugin_dir)):
        full = os.path.join(plugin_dir, name)
        if name == pid + ".plugin":
            continue
        if os.path.isdir(full):
            errors.append("%s: unexpected sub-directory '%s'" % (pid, name))
        elif name not in ALLOWED_FILES:
            errors.append("%s: unexpected file '%s' (allowed: %s.plugin, %s)"
                          % (pid, name, pid, ", ".join(sorted(ALLOWED_FILES))))
    raw, meta = read_metadata(path, errors)
    for k in REQUIRED:
        if k not in meta:
            errors.append("%s: missing %s" % (pid, k))
    for k in meta:
        if k not in REQUIRED and k not in OPTIONAL:
            errors.append("%s: unknown metadata %s" % (pid, k))
    if errors and any(k not in meta for k in REQUIRED):
        return None, errors

    def need_str(k, maxlen):
        v = meta.get(k)
        if not isinstance(v, str) or not v.strip():
            errors.append("%s: %s must be a non-empty string" % (pid, k))
        elif len(v) > maxlen:
            errors.append("%s: %s longer than %d chars" % (pid, k, maxlen))
        return v

    if meta.get("__id__") != pid:
        errors.append("%s: __id__ %r does not match directory/file name" % (pid, meta.get("__id__")))
    need_str("__name__", 64)
    need_str("__description__", 500)
    need_str("__author__", 64)
    ver = meta.get("__version__")
    if not isinstance(ver, str) or not SEMVER_RE.match(ver):
        errors.append("%s: __version__ %r is not semver" % (pid, ver))
    vc = meta.get("__version_code__")
    if isinstance(vc, bool) or not isinstance(vc, int) or vc < 1 or vc > 2**31 - 1:
        errors.append("%s: __version_code__ must be a positive int" % pid)
    api = meta.get("__api_version__")
    if isinstance(api, bool) or not isinstance(api, int) or api not in SUPPORTED_API:
        errors.append("%s: __api_version__ must be one of %s" % (pid, sorted(SUPPORTED_API)))
    mn = meta.get("__min_app_version__")
    if not isinstance(mn, str) or not SEMVER_RE.match(mn):
        errors.append("%s: __min_app_version__ %r is not semver" % (pid, mn))
    mx = meta.get("__max_app_version__", "")
    if mx != "" and (not isinstance(mx, str) or not SEMVER_RE.match(mx)):
        errors.append("%s: __max_app_version__ %r is not semver" % (pid, mx))
    if isinstance(mn, str) and isinstance(mx, str) and SEMVER_RE.match(mn) and mx \
            and SEMVER_RE.match(mx) and semver_key(mx) <= semver_key(mn):
        errors.append("%s: __max_app_version__ must be greater than __min_app_version__" % pid)
    perms = meta.get("__permissions__")
    if not isinstance(perms, (list, tuple)) or not all(isinstance(p, str) for p in perms):
        errors.append("%s: __permissions__ must be a list of strings" % pid)
        perms = []
    else:
        for p in perms:
            if p not in KNOWN_PERMISSIONS:
                errors.append("%s: unknown permission '%s'" % (pid, p))
        if len(set(perms)) != len(perms):
            errors.append("%s: duplicate permissions" % pid)
    icon = meta.get("__icon__", "")
    if not isinstance(icon, str) or len(icon) > 64:
        errors.append("%s: __icon__ must be a short string" % pid)
        icon = ""

    # optional meta.json
    tags = []
    mj = os.path.join(plugin_dir, "meta.json")
    if os.path.isfile(mj):
        try:
            with open(mj, "r", encoding="utf-8") as f:
                m = json.load(f)
            tags = m.get("tags", [])
            if not (isinstance(tags, list) and all(isinstance(t, str) and 0 < len(t) <= 24
                                                   for t in tags) and len(tags) <= 8):
                errors.append("%s: meta.json tags must be <=8 short strings" % pid)
                tags = []
        except (ValueError, AttributeError) as e:
            errors.append("%s: meta.json invalid: %s" % (pid, e))
    revoked = []
    rj = os.path.join(plugin_dir, "revoked.json")
    if os.path.isfile(rj):
        try:
            with open(rj, "r", encoding="utf-8") as f:
                revoked = json.load(f)
            if not (isinstance(revoked, list) and all(
                    isinstance(c, int) and not isinstance(c, bool) for c in revoked)):
                raise ValueError("must be a JSON list of ints (version codes)")
        except ValueError as e:
            errors.append("%s: revoked.json invalid: %s" % (pid, e))
            revoked = []
    has_icon_png = False
    ip = os.path.join(plugin_dir, "icon.png")
    if os.path.isfile(ip):
        with open(ip, "rb") as f:
            head = f.read(MAX_ICON_BYTES + 1)
        if len(head) > MAX_ICON_BYTES or not head.startswith(b"\x89PNG\r\n\x1a\n"):
            errors.append("%s: icon.png must be a PNG of at most %d bytes" % (pid, MAX_ICON_BYTES))
        else:
            has_icon_png = True

    if errors:
        return None, errors
    return {
        "id": pid, "name": meta["__name__"], "author": meta["__author__"],
        "description": meta["__description__"], "tags": tags, "icon": icon,
        "has_icon_png": has_icon_png, "permissions": list(perms), "revoked_local": revoked,
        "version": ver, "versionCode": vc, "apiVersion": api, "minAppVersion": mn,
        "maxAppVersion": mx, "sha256": sha256_hex(raw), "size": len(raw),
        "changelog": changelog_for(os.path.join(plugin_dir, "CHANGELOG.md"), ver),
    }, []


def changelog_for(path, version):
    """Text under the `## <version>` heading of CHANGELOG.md (first 500 chars)."""
    if not os.path.isfile(path):
        return ""
    with open(path, "r", encoding="utf-8") as f:
        lines = f.read().splitlines()
    out, on = [], False
    for ln in lines:
        m = re.match(r"^##\s+\[?v?([^\]\s]+)\]?", ln)
        if m:
            if on:
                break
            on = m.group(1) == version
            continue
        if on:
            out.append(ln)
    text = "\n".join(out).strip()
    return text[:500]


def raw_url(repo, sha, rel):
    return "https://raw.githubusercontent.com/%s/%s/%s" % (repo, sha, rel)


def utc_iso(t):
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def load_prev(path):
    if not path or not os.path.isfile(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def build(repo_dir, prev, repo, sha, now):
    plugins_dir = os.path.join(repo_dir, "plugins")
    errors, records = [], []
    ids = sorted(d for d in os.listdir(plugins_dir)
                 if os.path.isdir(os.path.join(plugins_dir, d))) if os.path.isdir(plugins_dir) else []
    for pid in ids:
        rec, errs = validate_plugin(os.path.join(plugins_dir, pid), pid)
        errors.extend(errs)
        if rec:
            records.append(rec)
    # binaries / stray files directly under plugins/
    if os.path.isdir(plugins_dir):
        for n in os.listdir(plugins_dir):
            if not os.path.isdir(os.path.join(plugins_dir, n)):
                errors.append("plugins/%s: stray file (only plugin directories allowed)" % n)

    prev_by_id = {p["id"]: p for p in (prev or {}).get("plugins", [])}
    out_plugins = []
    published = utc_iso(now)
    for rec in records:
        pid = rec["id"]
        old = prev_by_id.get(pid)
        history = list(old["versions"]) if old else []
        by_code = {v["versionCode"]: v for v in history}
        entry = {
            "version": rec["version"], "versionCode": rec["versionCode"],
            "apiVersion": rec["apiVersion"], "minAppVersion": rec["minAppVersion"],
            "maxAppVersion": rec["maxAppVersion"],
            "url": raw_url(repo, sha, "plugins/%s/%s.plugin" % (pid, pid)),
            "sha256": rec["sha256"], "size": rec["size"], "changelog": rec["changelog"],
            "published": published,
        }
        if history:
            top = max(history, key=lambda v: v["versionCode"])
            if rec["versionCode"] in by_code:
                same = by_code[rec["versionCode"]]
                if same["sha256"] != rec["sha256"]:
                    errors.append("%s: content changed but __version_code__ %d is unchanged "
                                  "(bump __version_code__ and __version__)" % (pid, rec["versionCode"]))
                elif rec["versionCode"] != top["versionCode"]:
                    errors.append("%s: version_code regression: %d is older than published %d"
                                  % (pid, rec["versionCode"], top["versionCode"]))
                # identical to published: keep the old entry (and its pinned url)
            elif rec["versionCode"] < top["versionCode"]:
                errors.append("%s: version_code regression: %d < published %d"
                              % (pid, rec["versionCode"], top["versionCode"]))
            else:
                if semver_key(rec["version"]) <= semver_key(top["version"]):
                    errors.append("%s: __version__ %s must be greater than published %s"
                                  % (pid, rec["version"], top["version"]))
                if any(v["version"] == rec["version"] for v in history):
                    errors.append("%s: __version__ %s was already published" % (pid, rec["version"]))
                history.append(entry)
        else:
            history.append(entry)
        history.sort(key=lambda v: v["versionCode"], reverse=True)
        history = history[:MAX_VERSIONS]
        revoked = sorted(set(rec["revoked_local"]) | set((old or {}).get("revoked", [])))
        live = [v for v in history if v["versionCode"] not in revoked]
        latest = (live[0] if live else history[0])["version"]
        icon = rec["icon"]
        if rec["has_icon_png"]:
            icon = raw_url(repo, sha, "plugins/%s/icon.png" % pid)
        elif old and old.get("icon", "").startswith("https://") and not rec["icon"]:
            icon = ""
        out_plugins.append({
            "id": pid, "name": rec["name"], "author": rec["author"],
            "description": rec["description"], "tags": rec["tags"], "icon": icon,
            "permissions": rec["permissions"], "latest": latest,
            "versions": history, "revoked": revoked,
        })
    present = {r["id"] for r in records}
    removed = sorted(((set((prev or {}).get("removed", [])) | set(prev_by_id)) - present))
    if errors:
        raise ValidationError("\n".join(errors))
    seq = int((prev or {}).get("sequence", 0)) + 1
    return {
        "schema": SCHEMA, "sequence": seq, "generated": utc_iso(now),
        "expires": utc_iso(now + dt.timedelta(days=EXPIRES_DAYS)), "repo": repo,
        "plugins": out_plugins, "removed": removed,
    }


def dump_bytes(index):
    return (json.dumps(index, ensure_ascii=False, indent=1) + "\n").encode("utf-8")


# ---- crypto ----------------------------------------------------------------

def _crypto():
    try:
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import ed25519
        from cryptography.exceptions import InvalidSignature
        return serialization, ed25519, InvalidSignature
    except ImportError:
        sys.exit("error: this command needs the 'cryptography' package: pip install cryptography")


def load_private(pem_bytes):
    ser, ed, _ = _crypto()
    key = ser.load_pem_private_key(pem_bytes, password=None)
    if not isinstance(key, ed.Ed25519PrivateKey):
        raise ValueError("not an Ed25519 private key")
    return key


def raw_public(key):
    ser, _, _ = _crypto()
    return key.public_key().public_bytes(ser.Encoding.Raw, ser.PublicFormat.Raw)


def sign_bytes(data, pem_bytes):
    return base64.b64encode(load_private(pem_bytes).sign(data)) + b"\n"


def load_public_arg(value):
    """value: base64 raw 32 bytes, or path to PEM private/public key."""
    ser, ed, _ = _crypto()
    if os.path.isfile(value):
        data = open(value, "rb").read()
        if b"PRIVATE KEY" in data:
            return ed.Ed25519PublicKey.from_public_bytes(raw_public(load_private(data)))
        return ser.load_pem_public_key(data)
    raw = base64.b64decode(value)
    if len(raw) != 32:
        raise ValueError("public key must be 32 raw bytes (base64)")
    return ed.Ed25519PublicKey.from_public_bytes(raw)


def verify(index_bytes, sig_bytes, pubkeys):
    _, _, InvalidSignature = _crypto()
    sig = base64.b64decode(sig_bytes.strip())
    for pk in pubkeys:
        try:
            pk.verify(sig, index_bytes)
            return True
        except InvalidSignature:
            continue
    return False


# ---- commands --------------------------------------------------------------

def cmd_validate(a):
    try:
        build(a.root, load_prev(a.prev), a.repo, "0" * 40, dt.datetime.now(dt.timezone.utc))
    except ValidationError as e:
        print("VALIDATION FAILED:\n" + str(e), file=sys.stderr)
        return 1
    print("OK: all plugins valid")
    return 0


def cmd_build(a):
    sha = a.sha or os.environ.get("GITHUB_SHA", "")
    if not SHA_RE.match(sha):
        sys.exit("error: need a full 40-hex commit SHA (--sha or $GITHUB_SHA) for pinned URLs")
    now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
    if a.now:
        now = dt.datetime.strptime(a.now, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)
    prev = load_prev(a.prev)
    if a.prev and not prev:
        print("note: no previous index found, starting at sequence 1", file=sys.stderr)
    try:
        index = build(a.root, prev, a.repo, sha, now)
    except ValidationError as e:
        print("VALIDATION FAILED:\n" + str(e), file=sys.stderr)
        return 1
    data = dump_bytes(index)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "wb") as f:
        f.write(data)
    print("wrote %s: sequence=%d plugins=%d expires=%s"
          % (a.out, index["sequence"], len(index["plugins"]), index["expires"]))
    return 0


def read_key_arg(a):
    if a.key_env:
        v = os.environ.get(a.key_env)
        if not v:
            sys.exit("error: environment variable %s is empty" % a.key_env)
        return v.encode("utf-8")
    if a.key:
        return open(a.key, "rb").read()
    sys.exit("error: give --key FILE or --key-env VAR")


def cmd_sign(a):
    data = open(a.index, "rb").read()
    sig = sign_bytes(data, read_key_arg(a))
    out = a.out or a.index + ".sig"
    with open(out, "wb") as f:
        f.write(sig)
    # self-check
    pub = load_private(read_key_arg(a)).public_key()
    assert verify(data, sig, [pub]), "self-check failed"
    print("signed %s -> %s" % (a.index, out))
    return 0


def cmd_verify(a):
    data = open(a.index, "rb").read()
    sig = open(a.sig or a.index + ".sig", "rb").read()
    keys = [load_public_arg(k) for k in a.pubkey]
    if not verify(data, sig, keys):
        print("SIGNATURE INVALID", file=sys.stderr)
        return 1
    idx = json.loads(data.decode("utf-8"))
    exp = dt.datetime.strptime(idx["expires"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)
    state = "EXPIRED" if exp < dt.datetime.now(dt.timezone.utc) else "fresh"
    print("signature OK (sequence=%d, %s, expires %s)" % (idx["sequence"], state, idx["expires"]))
    return 0


def cmd_keygen(a):
    ser, ed, _ = _crypto()
    out = os.path.abspath(a.out)
    if os.path.exists(out):
        sys.exit("error: %s already exists, refusing to overwrite" % out)
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    if (os.path.normcase(out) + os.sep).startswith(os.path.normcase(repo_root) + os.sep):
        sys.exit("error: do not write the private key inside the repository")
    key = ed.Ed25519PrivateKey.generate()
    pem = key.private_bytes(ser.Encoding.PEM, ser.PrivateFormat.PKCS8, ser.NoEncryption())
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    fd = os.open(out, flags, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(pem)
    raw = raw_public(key)
    print("private key (PEM) written to: %s" % out)
    print("  -> keep it secret; paste its whole content into the GitHub secret INDEX_SIGNING_KEY")
    print("")
    print("public key (base64, 32 raw bytes):")
    print("  " + base64.b64encode(raw).decode())
    print("")
    print("Java byte[] for PluginRepository.PUBLIC_KEYS:")
    print("  new byte[]{" + ", ".join("(byte) 0x%02x" % b for b in raw) + "}")
    print("")
    print("Kotlin / hex:")
    print("  " + raw.hex())
    return 0


def main(argv=None):
    root_default = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    def common(sp):
        sp.add_argument("--root", default=root_default, help="repo root (default: parent of tools/)")
        sp.add_argument("--repo", default=DEFAULT_REPO, help="owner/name used in URLs")
        sp.add_argument("--prev", help="previous index.json to carry version history from")

    s = sub.add_parser("validate"); common(s); s.set_defaults(fn=cmd_validate)
    s = sub.add_parser("build"); common(s)
    s.add_argument("--sha", help="commit SHA to pin URLs to (default $GITHUB_SHA)")
    s.add_argument("--out", default="index.json")
    s.add_argument("--now", help="override clock, UTC 'YYYY-MM-DDTHH:MM:SSZ' (tests)")
    s.set_defaults(fn=cmd_build)
    s = sub.add_parser("sign")
    s.add_argument("--index", default="index.json")
    s.add_argument("--out", help="default: <index>.sig")
    s.add_argument("--key", help="Ed25519 private key PEM file")
    s.add_argument("--key-env", help="env var holding the PEM text (e.g. INDEX_SIGNING_KEY)")
    s.set_defaults(fn=cmd_sign)
    s = sub.add_parser("verify")
    s.add_argument("--index", default="index.json")
    s.add_argument("--sig", help="default: <index>.sig")
    s.add_argument("--pubkey", action="append", required=True,
                   help="base64 raw public key, or PEM file; repeatable")
    s.set_defaults(fn=cmd_verify)
    s = sub.add_parser("keygen")
    s.add_argument("--out", required=True, help="where to write the private key PEM (outside the repo)")
    s.set_defaults(fn=cmd_keygen)

    a = p.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
