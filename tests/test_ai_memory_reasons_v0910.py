"""ai_autoreply 0.9.10: plain-language reasons for refused memory calls, one status place, on/off switch, no 'Neon' in the UI."""
import unittest
from test_ai_autoreply import CLIENT, DID, mod
from test_ai_style_memory_v096 import StyleBase

KEYS = ("mem_server_title", "mem_server_note", "mem_toast_fail", "mem_r_not_owned", "mem_r_other_account", "mem_r_unauthorized",
        "mem_r_disabled", "mem_r_nokey", "mem_r_starting", "mem_r_network", "mem_r_limit", "mem_r_old", "mem_r_perm",
        "cloud_title", "cloud_consent", "cloud_enable", "cloud_off", "cloud_delete", "style_title", "style_consent",
        "style_enable", "style_off", "style_delete", "cloud_unavailable", "style_unavailable")


class TestTexts(unittest.TestCase):
    def test_every_language_has_every_new_text_and_no_neon(self):
        for lang in ("en", "uk", "ru"):
            for k in KEYS:
                text = mod.tr(lang, k)
                self.assertTrue(text and text != k, (lang, k))
                self.assertNotIn("Neon", text, (lang, k))

    def test_not_linked_text_matches_the_agreed_wording(self):
        self.assertEqual(mod.tr("ru", "mem_r_not_owned"),
                         u"Ключ ИИ-сервера не привязан к вашему аккаунту Telegram. Попросите владельца сервера привязать его.")

    def test_short_blocks(self):
        for lang in ("en", "uk", "ru"):
            for k in ("cloud_consent", "style_consent", "mem_server_note"):
                self.assertLessEqual(len(mod.tr(lang, k)), 260, (lang, k))


class TestReasons(StyleBase):
    CASES = {"memory_token_not_owned": "mem_r_not_owned", "memory_account_mismatch": "mem_r_other_account",
             "memory_disabled": "mem_r_disabled", "memory_unavailable": "mem_r_starting", "memory_network_error": "mem_r_network",
             "memory_timeout": "mem_r_network", "memory_not_configured": "mem_r_nokey", "memory_rate_limited": "mem_r_limit",
             "memory_not_supported": "mem_r_old", "memory_not_authorized": "mem_r_unauthorized"}

    def test_reason_key_per_server_code(self):
        for code, want in self.CASES.items():
            self.assertEqual(self.p._mem_reason_key(RuntimeError(code)), want, code)
        self.assertEqual(self.p._mem_reason_key(PermissionError("x")), "mem_r_perm")
        self.assertEqual(self.p._mem_reason_key(RuntimeError("boom")), "")
        self.assertEqual(self.p._mem_reason_key(ValueError("memory_something_new")), "")

    def test_style_enable_failure_shows_reason_once_and_short_toast(self):
        def status(account, timeout=10):
            raise RuntimeError("memory_token_not_owned")
        CLIENT.memory_style_status = status
        key = self.key(); CLIENT.bulletins[:] = []
        self.p._style_action(key, "enable"); self.fire_timers()
        self.assertEqual(self.p._style_notes[key], self.p.t("mem_r_not_owned"))
        self.assertFalse(self.p._style_state(key)["enabled"])
        self.assertEqual(CLIENT.bulletins[-1], self.p.t("mem_toast_fail"))
        self.assertNotIn(self.p.t("mem_r_not_owned"), CLIENT.bulletins)

    def test_cloud_enable_failure_refines_vague_403_with_the_style_status(self):
        def status(account, timeout=10):
            raise RuntimeError("memory_not_authorized")
        CLIENT.ai_memory_status = status
        def style_status(account, timeout=10):
            raise RuntimeError("memory_token_not_owned")
        CLIENT.memory_style_status = style_status
        key = self.key(); CLIENT.bulletins[:] = []
        self.p._cloud_action(key, 0, "enable"); self.fire_timers()
        self.assertEqual(self.p._cloud_notes[(key, 0)], self.p.t("mem_r_not_owned"))
        self.assertEqual(CLIENT.bulletins[-1], self.p.t("mem_toast_fail"))

    def test_cloud_enable_failure_without_style_probe_keeps_vague_reason(self):
        def status(account, timeout=10):
            raise RuntimeError("memory_not_authorized")
        CLIENT.ai_memory_status = status
        CLIENT.MEMORY_STYLE = False
        key = self.key()
        self.p._cloud_action(key, 0, "enable"); self.fire_timers()
        self.assertEqual(self.p._cloud_notes[(key, 0)], self.p.t("mem_r_unauthorized"))

    def test_unknown_error_falls_back_to_the_short_generic_text(self):
        def status(account, timeout=10):
            raise RuntimeError("weird")
        CLIENT.ai_memory_status = status
        key = self.key()
        self.p._cloud_action(key, 0, "enable"); self.fire_timers()
        self.assertEqual(self.p._cloud_notes[(key, 0)], self.p.t("cloud_unavailable"))

    def test_success_toast_is_the_short_status(self):
        key = self.key(); CLIENT.bulletins[:] = []
        self.p._style_action(key, "enable"); self.fire_timers()
        self.assertEqual(CLIENT.bulletins[-1], self.p.t("style_on_status"))


class TestScreen(StyleBase):
    def labels(self):
        return {getattr(i, "key", None): getattr(i, "text", "") for i in self.p._cloud_settings(self.key())}

    def test_one_switch_shows_state_and_delete_is_two_tap(self):
        sk = self.p._sk(self.key())
        before = self.labels()
        self.assertEqual(before["style_enable_" + sk], self.p.t("style_enable"))
        self.assertEqual(before["cloud_enable_" + sk], self.p.t("cloud_enable"))
        self.assertNotIn("style_off_" + sk, before); self.assertNotIn("cloud_off_" + sk, before)
        self.style_on()
        self.assertEqual(self.labels()["style_enable_" + sk], self.p.t("style_off"))
        item = [i for i in self.p._cloud_settings(self.key()) if getattr(i, "key", None) == "cloud_delete_" + sk][0]
        CLIENT.bulletins[:] = []
        item.on_click()
        self.assertEqual(CLIENT.bulletins, [self.p.t("tap_again")])
        self.assertTrue(self.p._cloud_state(self.key(), 0).get("deletePending") is not True)

    def test_toggle_runs_off_when_on_and_enable_when_off(self):
        sk = self.p._sk(self.key()); calls = []
        self.p._style_action = lambda k, a: calls.append(a)
        item = [i for i in self.p._cloud_settings(self.key()) if getattr(i, "key", None) == "style_enable_" + sk][0]
        item.on_click(); self.assertEqual(calls, ["enable"])
        self.p._style_active = lambda k, record=None: True
        item = [i for i in self.p._cloud_settings(self.key()) if getattr(i, "key", None) == "style_enable_" + sk][0]
        item.on_click(); self.assertEqual(calls, ["enable", "off"])

    def test_screen_has_no_neon_and_names_the_two_memories(self):
        texts = " ".join(str(getattr(i, "text", "")) for i in self.p._cloud_settings(self.key()))
        self.assertNotIn("Neon", texts)
        self.assertIn(self.p.t("style_title"), texts); self.assertIn(self.p.t("cloud_title"), texts)
        self.assertLessEqual(len(self.p._cloud_settings(self.key())), 14)
