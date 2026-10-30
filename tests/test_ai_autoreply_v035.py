"""0.3.5 tests: on_app_event('settings_changed') reload, reload-merge-save, app_locale for the Auto UI language.

Run: python -m unittest discover -s tests -v
"""
import json
import unittest
from types import SimpleNamespace

from test_ai_autoreply import Base, CLIENT, DID, mod

OTHER = 555


def put_chats(p, chats):
    p.settings["chats"] = json.dumps(chats)


def entry(did, enabled=True, **kw):
    d = {"enabled": enabled, "account": 0, "dialog_id": did, "title": "T%d" % did, "type": "user", "fails": 0}
    d.update(kw)
    return d


class TestSettingsChanged(Base):
    def test_string_event_reloads_chats_and_keeps_runtime_state(self):
        self.enable()
        key = self.key() if hasattr(self, "key") else self.p.chat_key(0, DID)
        st = self.p._state(key)
        st.cooldown_until = 123.0
        st.pending.append((1, 7, "hi"))
        self.p._lang_cache[key] = (1.0, "Russian")
        ext = json.loads(self.p.settings["chats"])
        ext[self.p.chat_key(0, OTHER)] = entry(OTHER)
        put_chats(self.p, ext)
        self.p.settings["mode_" + self.p._sk(self.p.chat_key(0, OTHER))] = 1
        self.assertNotIn(self.p.chat_key(0, OTHER), self.p._chats)
        self.p.on_app_event("settings_changed")
        self.assertIn(self.p.chat_key(0, OTHER), self.p._chats)
        self.assertEqual(self.p._chat_mode(self.p.chat_key(0, OTHER)), mod.MODE_DRAFT)
        self.assertIs(self.p._state(key), st)                # debounce/cooldown state preserved
        self.assertEqual(st.cooldown_until, 123.0)
        self.assertEqual(len(st.pending), 1)
        self.assertEqual(self.p._lang_cache, {})

    def test_enum_like_event_and_other_events(self):
        put_chats(self.p, {self.p.chat_key(0, OTHER): entry(OTHER)})
        self.p.on_app_event("START")
        self.p.on_app_event(SimpleNamespace(name="PAUSE"))
        self.assertNotIn(self.p.chat_key(0, OTHER), self.p._chats)
        self.p.on_app_event(SimpleNamespace(name="settings_changed"))
        self.assertIn(self.p.chat_key(0, OTHER), self.p._chats)
        put_chats(self.p, {})
        self.p.on_app_event(SimpleNamespace(value="settings_changed"))
        self.assertEqual(self.p._chats, {})

    def test_external_disable_and_master_take_effect(self):
        self.enable()
        key = self.p.chat_key(0, DID)
        ext = json.loads(self.p.settings["chats"])
        ext[key]["enabled"] = False
        put_chats(self.p, ext)
        self.p.on_app_event("settings_changed")
        self.assertFalse(self.p.is_enabled(key))

    def test_bad_stored_value_does_not_raise(self):
        self.p.settings["chats"] = "not json"
        self.p.on_app_event("settings_changed")
        self.assertEqual(self.p._chats, {})


class TestMergeSave(Base):
    def test_plugin_save_keeps_newer_external_changes(self):
        self.enable()
        key = self.p.chat_key(0, DID)
        okey = self.p.chat_key(0, OTHER)
        ext = json.loads(self.p.settings["chats"])
        ext[okey] = entry(OTHER, title="External")
        ext[key]["enabled"] = False               # the core screen paused our chat; plugin has not been told
        put_chats(self.p, ext)
        self.p._fail(key, "boom")                 # the plugin's own mutation: only 'fails'
        stored = json.loads(self.p.settings["chats"])
        self.assertIn(okey, stored)
        self.assertEqual(stored[okey]["title"], "External")
        self.assertFalse(stored[key]["enabled"])
        self.assertEqual(stored[key]["fails"], 1)
        self.assertEqual(self.p._chats, stored)

    def test_new_chat_added_by_plugin_keeps_external_chats(self):
        okey = self.p.chat_key(0, OTHER)
        put_chats(self.p, {okey: entry(OTHER)})
        self.enable()
        stored = json.loads(self.p.settings["chats"])
        self.assertEqual(set(stored), {okey, self.p.chat_key(0, DID)})

    def test_externally_removed_chat_is_not_resurrected(self):
        self.enable()
        key = self.p.chat_key(0, DID)
        put_chats(self.p, {})
        self.p._fail(key, "boom")
        self.assertEqual(json.loads(self.p.settings["chats"]), {})

    def test_off_remove_and_pause_merge(self):
        self.enable()
        key = self.p.chat_key(0, DID)
        okey = self.p.chat_key(0, OTHER)
        ext = json.loads(self.p.settings["chats"])
        ext[okey] = entry(OTHER)
        put_chats(self.p, ext)
        self.p.chat_off(key, False)
        stored = json.loads(self.p.settings["chats"])
        self.assertFalse(stored[key]["enabled"])
        self.assertTrue(stored[okey]["enabled"])
        self.p.chat_off(key, True)
        self.assertEqual(set(json.loads(self.p.settings["chats"])), {okey})


class TestAppLocale(Base):
    def setUp(self):
        Base.setUp(self)
        self.p.settings["ui_lang"] = 0

    def tearDown(self):
        if hasattr(CLIENT, "app_locale"):
            del CLIENT.app_locale

    def test_uses_app_locale(self):
        for code in ("uk", "ru", "en"):
            CLIENT.app_locale = lambda c=code: c
            self.assertEqual(self.p.lang(), code)

    def test_older_app_or_bad_value_falls_back(self):
        self.assertFalse(hasattr(CLIENT, "app_locale"))
        orig = mod.detect_ui_lang
        mod.detect_ui_lang = lambda: None
        try:
            self.assertEqual(self.p.lang(), "uk")
            CLIENT.app_locale = lambda: "de"
            self.assertEqual(self.p.lang(), "uk")

            def boom():
                raise RuntimeError("x")
            CLIENT.app_locale = boom
            self.assertEqual(self.p.lang(), "uk")
        finally:
            mod.detect_ui_lang = orig

    def test_explicit_setting_wins(self):
        CLIENT.app_locale = lambda: "ru"
        self.p.settings["ui_lang"] = 3
        self.assertEqual(self.p.lang(), "en")


if __name__ == "__main__":
    unittest.main()
