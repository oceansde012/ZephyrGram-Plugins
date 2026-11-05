import datetime as dt
import importlib.util
import json
import os
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location(
    "build_index_mod", os.path.join(HERE, "..", "tools", "build_index.py"))
bi = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bi)

SHA = "a" * 40
NOW = dt.datetime(2026, 11, 5, 12, 0, 0, tzinfo=dt.timezone.utc)
KB = 1024


def plugin_source(pid, version, code, size, min_app="0.2.0", max_app=None):
    head = ('__id__ = "%s"\n__name__ = "N"\n__description__ = "d"\n__author__ = "a"\n'
            '__version__ = "%s"\n__version_code__ = %d\n__api_version__ = 1\n'
            '__min_app_version__ = "%s"\n__permissions__ = []\n' % (pid, version, code, min_app))
    if max_app:
        head += '__max_app_version__ = "%s"\n' % max_app
    pad = size - len(head)
    assert pad >= 0
    body = ""
    while len(body) < pad:
        body += "#" + "x" * min(76, max(pad - len(body) - 2, 0)) + "\n"
        if pad - len(body) == 1:
            body = body[:-1] + "#\n"
    return (head + body[:pad - 1] + "\n" if pad else head).encode()


class Base(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.addCleanup(self.td.cleanup)
        self.root = self.td.name
        os.makedirs(os.path.join(self.root, "plugins"))

    def write(self, pid, version, code, size, **kw):
        d = os.path.join(self.root, "plugins", pid)
        os.makedirs(d, exist_ok=True)
        data = plugin_source(pid, version, code, size, **kw)
        self.assertEqual(len(data), size)
        with open(os.path.join(d, pid + ".plugin"), "wb") as f:
            f.write(data)

    def build(self, prev=None, prev_v2=None, warnings=None):
        return bi.build(self.root, prev, "o/r", SHA, NOW, prev_v2, warnings)

    @staticmethod
    def by_id(index):
        return {p["id"]: p for p in index["plugins"]}


class BuildBoth(Base):
    def test_constants(self):
        self.assertEqual(bi.MAX_PLUGIN_BYTES, 2 * 1024 * 1024)
        self.assertEqual(bi.LEGACY_MAX_BYTES, 512 * 1024)

    def test_small_plugin_in_both_unchanged(self):
        self.write("small_one", "1.0.0", 1, 2 * KB)
        v1, v2 = self.build()
        self.assertEqual(v1, v2)
        self.assertEqual(v1["plugins"][0]["versions"][0]["minAppVersion"], "0.2.0")

    def test_exactly_legacy_limit_is_legacy(self):
        self.write("edge_one", "1.0.0", 1, bi.LEGACY_MAX_BYTES)
        v1, v2 = self.build()
        self.assertEqual(len(v1["plugins"]), 1)
        self.assertEqual(v2["plugins"][0]["versions"][0]["minAppVersion"], "0.2.0")

    def test_big_only_plugin_omitted_from_legacy(self):
        self.write("small_one", "1.0.0", 1, 2 * KB)
        self.write("big_one", "1.0.0", 1, bi.LEGACY_MAX_BYTES + 1)
        v1, v2 = self.build()
        self.assertEqual(list(self.by_id(v1)), ["small_one"])
        self.assertEqual(sorted(self.by_id(v2)), ["big_one", "small_one"])
        self.assertEqual(v1["removed"], [])
        for v in v1["plugins"][0]["versions"]:
            self.assertLessEqual(v["size"], bi.LEGACY_MAX_BYTES)

    def test_min_app_bumped_for_big_version(self):
        self.write("big_one", "1.0.0", 1, 600 * KB, min_app="0.2.0")
        _, v2 = self.build()
        self.assertEqual(v2["plugins"][0]["versions"][0]["minAppVersion"], "0.2.5")

    def test_higher_min_app_kept(self):
        self.write("big_one", "1.0.0", 1, 600 * KB, min_app="0.3.1")
        _, v2 = self.build()
        self.assertEqual(v2["plugins"][0]["versions"][0]["minAppVersion"], "0.3.1")

    def test_max_app_below_bumped_min_is_error(self):
        self.write("big_one", "1.0.0", 1, 600 * KB, min_app="0.2.0", max_app="0.2.3")
        with self.assertRaises(bi.ValidationError):
            self.build()

    def test_limit_2mib(self):
        self.write("big_one", "1.0.0", 1, bi.MAX_PLUGIN_BYTES)
        self.build()
        self.write("big_one", "1.0.1", 2, bi.MAX_PLUGIN_BYTES + 1)
        with self.assertRaises(bi.ValidationError):
            self.build()

    def test_validate_warns_for_big_plugin(self):
        self.write("big_one", "1.0.0", 1, 600 * KB)
        self.write("small_one", "1.0.0", 1, 2 * KB)
        w = []
        self.build(warnings=w)
        self.assertEqual(len(w), 1)
        self.assertIn("big_one", w[0])
        self.assertIn("0.2.5", w[0])

    def test_sequence_equal_and_monotonic(self):
        self.write("small_one", "1.0.0", 1, 2 * KB)
        v1, v2 = self.build()
        self.assertEqual(v1["sequence"], 1)
        self.assertEqual(v2["sequence"], 1)
        n1, n2 = self.build(v1, v2)
        self.assertEqual((n1["sequence"], n2["sequence"]), (2, 2))

    def test_sequence_uses_max_of_prevs(self):
        self.write("small_one", "1.0.0", 1, 2 * KB)
        v1, v2 = self.build()
        v1["sequence"], v2["sequence"] = 5, 7
        n1, n2 = self.build(v1, v2)
        self.assertEqual((n1["sequence"], n2["sequence"]), (8, 8))

    def test_history_carry_over_both(self):
        self.write("grow_one", "1.0.0", 1, 2 * KB)
        v1, v2 = self.build()
        self.write("grow_one", "1.1.0", 2, 600 * KB)
        v1, v2 = self.build(v1, v2)
        p1, p2 = self.by_id(v1)["grow_one"], self.by_id(v2)["grow_one"]
        self.assertEqual([v["versionCode"] for v in p1["versions"]], [1])
        self.assertEqual(p1["latest"], "1.0.0")
        self.assertEqual([v["versionCode"] for v in p2["versions"]], [2, 1])
        self.assertEqual(p2["latest"], "1.1.0")
        # a further small release: legacy keeps its history, v2 keeps the big one
        self.write("grow_one", "1.2.0", 3, 3 * KB)
        v1, v2 = self.build(v1, v2)
        self.assertEqual([v["versionCode"] for v in self.by_id(v1)["grow_one"]["versions"]], [3, 1])
        self.assertEqual([v["versionCode"] for v in self.by_id(v2)["grow_one"]["versions"]], [3, 2, 1])
        self.assertEqual(self.by_id(v1)["grow_one"]["latest"], "1.2.0")
        self.assertEqual(v1["sequence"], v2["sequence"])

    def test_big_only_then_small_appears_in_legacy(self):
        self.write("big_one", "1.0.0", 1, 600 * KB)
        v1, v2 = self.build()
        self.assertEqual(v1["plugins"], [])
        self.write("big_one", "1.0.1", 2, 100 * KB)
        v1, v2 = self.build(v1, v2)
        self.assertEqual([v["versionCode"] for v in self.by_id(v1)["big_one"]["versions"]], [2])

    def test_missing_prev_v2_uses_legacy_prev(self):
        self.write("small_one", "1.0.0", 1, 2 * KB)
        v1, _ = self.build()
        v1["sequence"] = 9
        self.write("small_one", "1.0.1", 2, 2 * KB)
        n1, n2 = self.build(v1, None)
        self.assertEqual((n1["sequence"], n2["sequence"]), (10, 10))
        self.assertEqual([v["versionCode"] for v in self.by_id(n2)["small_one"]["versions"]], [2, 1])
        self.assertEqual(n1["plugins"], n2["plugins"])

    def test_version_code_regression_checked_against_v2_history(self):
        self.write("big_one", "1.1.0", 5, 600 * KB)
        v1, v2 = self.build()
        self.write("big_one", "1.0.0", 4, 2 * KB)
        with self.assertRaises(bi.ValidationError):
            self.build(v1, v2)

    def test_removed_in_both(self):
        self.write("big_one", "1.0.0", 1, 600 * KB)
        self.write("small_one", "1.0.0", 1, 2 * KB)
        v1, v2 = self.build()
        import shutil
        shutil.rmtree(os.path.join(self.root, "plugins", "big_one"))
        shutil.rmtree(os.path.join(self.root, "plugins", "small_one"))
        n1, n2 = self.build(v1, v2)
        self.assertEqual(n1["removed"], ["big_one", "small_one"])
        self.assertEqual(n1["removed"], n2["removed"])


class CliBuild(Base):
    def run_build(self, *extra):
        out = os.path.join(self.root, "out")
        rc = bi.main(["build", "--root", self.root, "--repo", "o/r", "--sha", SHA,
                      "--out", os.path.join(out, "index.json")] + list(extra))
        self.assertEqual(rc, 0)
        return out

    def load(self, path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    def test_cli_writes_both_files_and_tolerates_missing_prev_v2(self):
        self.write("small_one", "1.0.0", 1, 2 * KB)
        self.write("big_one", "1.0.0", 1, 600 * KB)
        out = self.run_build("--prev", os.path.join(self.root, "nope.json"),
                             "--prev-v2", os.path.join(self.root, "nope-v2.json"))
        v1 = self.load(os.path.join(out, "index.json"))
        v2 = self.load(os.path.join(out, "index-v2.json"))
        self.assertEqual(len(v1["plugins"]), 1)
        self.assertEqual(len(v2["plugins"]), 2)
        self.assertEqual(v1["sequence"], v2["sequence"])

    def test_cli_prev_v2_derived_next_to_prev(self):
        self.write("small_one", "1.0.0", 1, 2 * KB)
        out = self.run_build()
        self.write("small_one", "1.0.1", 2, 2 * KB)
        out2 = os.path.join(self.root, "out")
        # rebuild with prev files in a separate dir
        prevdir = os.path.join(self.root, "prev")
        os.makedirs(prevdir)
        for n in ("index.json", "index-v2.json"):
            with open(os.path.join(out, n), "rb") as s, open(os.path.join(prevdir, n), "wb") as d:
                d.write(s.read())
        self.run_build("--prev", os.path.join(prevdir, "index.json"))
        v2 = self.load(os.path.join(out2, "index-v2.json"))
        self.assertEqual(v2["sequence"], 2)

    def test_sign_and_verify_both(self):
        try:
            import cryptography  # noqa: F401
        except ImportError:
            self.skipTest("cryptography not installed")
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import ed25519
        pem = ed25519.Ed25519PrivateKey.generate().private_bytes(
            serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption())
        keyfile = os.path.join(self.root, "k.pem")
        with open(keyfile, "wb") as f:
            f.write(pem)
        self.write("big_one", "1.0.0", 1, 600 * KB)
        out = self.run_build()
        for n in ("index.json", "index-v2.json"):
            p = os.path.join(out, n)
            self.assertEqual(bi.main(["sign", "--index", p, "--key", keyfile]), 0)
            self.assertEqual(bi.main(["verify", "--index", p, "--pubkey", keyfile]), 0)


if __name__ == "__main__":
    unittest.main()
