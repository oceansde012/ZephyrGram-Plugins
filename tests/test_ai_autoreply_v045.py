"""0.4.5: the app's Auto-reply tab (ZephyrAutoReplyStore, Java) and the plugin stay in sync."""
import json

from test_ai_autoreply import Base, CLIENT, DID, mod, all_settings, chats_screen

OTHER = 43


def java_view(settings):
    """What ZephyrAutoReplyStore.load() sees: every value is the JSON text of the Python value; "chats" is a JSON
    string holding a JSON object; mode_<sk> is read as a number or a numeric string, missing = 0."""
    raw = {k: json.dumps(v) for k, v in settings.items() if v is not None}
    out = {}
    chats = json.loads(raw.get("chats", "null"))
    if isinstance(chats, str):
        chats = json.loads(chats) if chats else {}
    for key, c in (chats or {}).items():
        sk = key.replace(":", "_").replace("-", "n")
        mode = json.loads(raw["mode_" + sk]) if ("mode_" + sk) in raw else 0
        keep = json.loads(raw["keep_" + sk]) if ("keep_" + sk) in raw else None
        out[key] = {"enabled": c.get("enabled") is True, "account": c.get("account"), "dialog_id": c.get("dialog_id"),
                    "title": c.get("title"), "type": c.get("type"), "mode": int(mode), "keep": keep,
                    "auto_off": "auto_off_ts" in c}
    return out


class FakeBridge(object):
    """PluginSettingsModel.getRaw / putRawIf over the test store (JSON text like on the device)."""

    def __init__(self, plugin, on_read=None):
        self.p, self.on_read, self.refused = plugin, on_read, 0

    def _raw(self, key):
        return json.dumps(self.p.settings[key]) if self.p.settings.get(key) is not None else None

    def getRaw(self, pid, key):
        raw = self._raw(key)
        if self.on_read:
            self.on_read(key)
        return raw

    def putRawIf(self, pid, key, expected, new):
        if self._raw(key) != expected:
            self.refused += 1
            return False
        self.p.settings[key] = json.loads(new)
        return True


class SyncBase(Base):
    def setUp(self):
        super(SyncBase, self).setUp()
        self.p.settings["owner_active"] = "0"

    def sk(self, did=DID):
        return self.p._sk(self.p.chat_key(0, did))

    def stored(self, did=DID):
        return java_view(self.p.settings).get(self.p.chat_key(0, did))

    def core_write(self, mutate, event=False):
        """A write of the app's tab: whole "chats" rewritten in one go (optionally followed by settings_changed)."""
        chats = json.loads(self.p.settings.get("chats") or "{}")
        mutate(chats)
        self.p.settings["chats"] = json.dumps(chats)
        if event:
            self.p.on_app_event("settings_changed")

    def fail_out(self):
        for _ in range(mod.MAX_FAILURES):
            self.p._fail(self.key(), "boom")


class TestKeepMirror(SyncBase):
    def test_error_pause_and_resume_keep_the_switch_in_sync(self):
        self.enable()
        self.fail_out()
        s = self.stored()
        self.assertEqual((s["enabled"], s["keep"], s["auto_off"]), (False, False, True))
        self.clock[0] += mod.AUTH_RESUME_SEC + 1
        self.incoming(text="hi again")
        s = self.stored()
        self.assertEqual((s["enabled"], s["keep"], s["auto_off"]), (True, True, False))

    def test_drawing_the_settings_screen_writes_nothing(self):
        self.p.chat_on(0, DID, str(DID), "user")             # title still unknown -> shown from dialog info
        self.fail_out()
        self.p._open_key = self.key()
        before = dict(self.p.settings)
        texts = [getattr(i, "text", "") for i in all_settings(self.p)]
        self.assertIn("▾ Alice", texts)
        self.assertEqual(self.p.settings, before)

    def test_legacy_mismatch_repaired_on_load(self):
        self.enable()
        self.p.settings["keep_" + self.sk()] = False          # written by an older version
        p2 = mod.Plugin()
        p2.settings = self.p.settings
        p2.on_plugin_load()
        self.assertTrue(self.p.settings["keep_" + self.sk()])


class TestOwnerOffWins(SyncBase):
    def test_owner_pause_during_failing_request_is_not_resumed(self):
        self.enable()
        self.p._commit(self.key(), set={"fails": mod.MAX_FAILURES - 1})
        # the owner pauses the chat on the tab while a request is running ...
        self.core_write(lambda c: c[self.key()].update(enabled=False), event=True)
        self.p.settings["keep_" + self.sk()] = False
        self.p._fail(self.key(), "boom")                      # ... and that request fails
        self.assertFalse(self.stored()["auto_off"])
        self.clock[0] += mod.AUTH_RESUME_SEC + 1
        self.incoming(text="hello")
        self.assertFalse(self.stored()["enabled"])
        self.assertEqual(CLIENT.sent, [])

    def test_switch_off_after_error_pause_stays_off(self):
        self.enable()
        self.fail_out()
        cb = self.p._keep_cb(self.key())
        cb(True)
        cb(False)
        self.clock[0] += mod.AUTH_RESUME_SEC + 1
        self.incoming(text="hello")
        self.assertFalse(self.stored()["enabled"])
        self.assertFalse(self.p.is_enabled(self.key()))

    def test_stale_cache_does_not_resume_a_chat_the_owner_switched_off(self):
        self.enable()
        self.fail_out()
        self.clock[0] += mod.AUTH_RESUME_SEC + 1
        # the tab switched it off (auto_off_ts dropped); settings_changed has not arrived yet
        self.core_write(lambda c: c[self.key()].pop("auto_off_ts"))
        self.incoming(text="hello")
        self.assertFalse(self.stored()["enabled"])


class TestLostUpdates(SyncBase):
    def test_core_write_between_read_and_write_is_kept(self):
        self.enable()
        armed = [True]

        def core_edit(key):
            if key == "chats" and armed[0]:
                armed[0] = False
                self.core_write(lambda c: c.update({"0:777": {"enabled": True, "account": 0, "dialog_id": 777,
                                                             "title": "Bob", "type": "user", "fails": 0}}))
        self.p._bridge = FakeBridge(self.p, on_read=core_edit)
        real_get = self.p.get_setting

        def get_setting(k, d=None):                            # an app without the bridge reads like this
            v = real_get(k, d)
            core_edit(k)
            return v
        self.p.get_setting = get_setting
        self.p._commit(self.key(), set={"fails": 3})
        view = java_view(self.p.settings)
        self.assertIn("0:777", view)                            # the tab's new chat survived
        self.assertEqual(json.loads(self.p.settings["chats"])[self.key()]["fails"], 3)
        self.assertEqual(self.p._bridge.refused, 1)
        self.assertIn("0:777", self.p._chats)

    def test_all_skip_merge(self):
        self.p.settings["all_skip"] = json.dumps(["0:1"])
        armed = [True]

        def core_edit(key):
            if key == "all_skip" and armed[0]:
                armed[0] = False
                self.p.settings["all_skip"] = json.dumps(["0:1", "0:2"])
        self.p._bridge = FakeBridge(self.p, on_read=core_edit)
        self.p._skip_add("0:3")
        self.assertEqual(json.loads(self.p.settings["all_skip"]), ["0:1", "0:2", "0:3"])

    def test_broken_bridge_falls_back_to_plain_write(self):
        class Broken(object):
            def getRaw(self, *a):
                raise RuntimeError("no")

            def putRawIf(self, *a):
                raise RuntimeError("no")
        self.p._bridge = Broken()
        self.enable()
        self.assertTrue(self.stored()["enabled"])


class TestRunningReplies(SyncBase):
    def test_core_edit_of_another_chat_does_not_cancel_this_reply(self):
        self.enable()
        self.enable(did=OTHER)

        def complete(messages, **kw):
            self.p.settings["mode_" + self.sk(OTHER)] = mod.MODE_DRAFT          # the tab changes the other chat
            self.core_write(lambda c: c[self.p.chat_key(0, OTHER)].update(enabled=False), event=True)
            return "hello back"
        CLIENT.ai_result = complete
        self.incoming(text="hello")
        self.fire_timers()
        self.assertEqual(len(CLIENT.sent), 1)
        self.assertIn("core_mode_draft", self.p.decisions_text())

    def test_core_edit_of_this_chat_still_cancels_it(self):
        self.enable()

        def complete(messages, **kw):
            self.p.settings["mode_" + self.sk()] = mod.MODE_DRAFT
            self.p.on_app_event("settings_changed")
            return "hello back"
        CLIENT.ai_result = complete
        self.incoming(text="hello")
        self.fire_timers()
        self.assertEqual(CLIENT.sent, [])
        self.assertIn("disabled_meanwhile", self.p.decisions_text())

    def test_mode_change_while_batch_pending_uses_new_mode(self):
        self.enable()
        self.incoming(text="hello")                            # debounce timer pending
        self.assertTrue(self.p._state(self.key()).timer)
        self.p.settings["mode_" + self.sk()] = mod.MODE_DRAFT
        self.p.on_app_event("settings_changed")
        self.fire_timers()
        self.assertEqual(CLIENT.sent, [])
        self.assertEqual(len(CLIENT.drafts), 1)
        st = self.p._state(self.key())
        self.assertEqual((st.timer, st.inflight, st.pending), (False, False, []))

    def test_pause_while_batch_pending_then_resume_answers_next_message(self):
        self.enable()
        self.incoming(text="hello")
        self.core_write(lambda c: c[self.key()].update(enabled=False), event=True)
        self.fire_timers()
        self.assertEqual(CLIENT.sent, [])
        self.core_write(lambda c: c[self.key()].update(enabled=True), event=True)
        self.clock[0] += 100
        self.incoming(text="hello again")
        self.fire_timers()
        self.assertEqual(len(CLIENT.sent), 1)


class TestBothSides(SyncBase):
    def test_off_sees_chat_added_on_the_tab(self):
        self.core_write(lambda c: c.update({self.key(): {"enabled": True, "account": 0, "dialog_id": DID,
                                                         "title": "Alice", "type": "user", "fails": 0}}))
        self.p.on_disable_click({"account": 0, "dialog_id": DID})   # no settings_changed yet
        s = self.stored()
        self.assertEqual((s["enabled"], s["keep"]), (False, False))
        self.assertFalse(self.p.is_enabled(self.key()))

    def test_reply_all_addition_in_java_format(self):
        self.p.settings["reply_all"] = True
        self.incoming(text="hello")
        s = self.stored()
        self.assertEqual(s, {"enabled": True, "account": 0, "dialog_id": DID, "title": "Alice", "type": "user",
                             "mode": 0, "keep": True, "auto_off": False})

    def test_remove_then_readd_from_the_tab(self):
        self.enable()
        self.p.settings["mode_" + self.sk()] = mod.MODE_DRAFT
        self.p.chat_off(self.key(), remove=True)
        self.assertIsNone(self.stored())
        self.assertIsNone(self.p.settings.get("keep_" + self.sk()))
        self.assertIsNone(self.p.settings.get("mode_" + self.sk()))
        self.assertIn(self.key(), self.p._all_skip())
        # the tab adds it again (ZephyrAutoReplyStore.upsert: entry + keep_ + all_skip without the key)
        self.core_write(lambda c: c.update({self.key(): {"enabled": True, "account": 0, "dialog_id": DID,
                                                         "title": "Alice", "type": "user", "fails": 0}}))
        self.p.settings["keep_" + self.sk()] = True
        self.p.settings["all_skip"] = json.dumps([])
        self.p.on_app_event("settings_changed")
        self.assertTrue(self.p.is_enabled(self.key()))
        self.assertEqual(self.stored()["mode"], 0)

    def test_settings_mode_selector_is_logged(self):
        self.enable()
        self.p._open_key = self.key()
        sel = next(i for i in chats_screen(self.p) if getattr(i, "key", "") == "mode_" + self.sk())
        self.p.settings["mode_" + self.sk()] = mod.MODE_COMMAND     # PluginSettingsModel.setValue, then on_change
        sel.on_change(mod.MODE_COMMAND)
        self.assertIn("settings_mode_friend", self.p.decisions_text())
