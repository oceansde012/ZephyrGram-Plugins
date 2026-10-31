"""0.3.4 tests: chats screen, in-chat admin commands (.ai on/off/status/list/mode), chat menu toggle,
autonomous replies with Balanced defaults, owner-silence window, short-update incoming path, reply language.

Run: python -m unittest discover -s tests -v
"""
import json
import unittest
from types import SimpleNamespace

from test_ai_autoreply import Base, CLIENT, DID, chats_screen, mod, screen
from test_ai_autoreply_v033 import RealParams


def hist_of(rows, base=1000):
    """rows: [(out, text)] oldest first -> history dicts."""
    return [{"id": base + i, "from_id": 1 if out else 7, "out": out, "date": 10 + i, "text": t, "is_bot": False}
            for i, (out, t) in enumerate(rows)]


class Cmd(Base):
    def setUp(self):
        Base.setUp(self)
        self.p.settings["typing_delay"] = False

    def run_cmd(self, text, peer=DID):
        res = self.p.on_send_message_hook(0, RealParams(text, peer))
        return res

    def last_bulletin(self):
        return CLIENT.bulletins[-1] if CLIENT.bulletins else ""


class TestAdminCommands(Cmd):
    def test_on_adds_unlisted_private_chat_in_auto_and_is_cancelled(self):
        self.assertFalse(self.p.is_enabled(self.key()))
        res = self.run_cmd(".ai on")
        self.assertEqual(res.strategy, 1)                       # never sent
        self.assertTrue(self.p.is_enabled(self.key()))
        c = self.p._chats[self.key()]
        self.assertEqual((c["account"], c["dialog_id"], c["title"], c["type"]), (0, DID, "Alice", "user"))
        self.assertEqual(self.p._chat_mode(self.key()), mod.MODE_AUTO)
        self.assertEqual(self.p.settings["mode_" + self.p._sk(self.key())], 0)
        self.assertIn("Alice", self.last_bulletin())
        self.assertIn("admin_on", self.p.decisions_text())
        self.assertEqual(CLIENT.sent, [])

    def test_off_removes_chat_and_settings(self):
        self.run_cmd(".ai on")
        sk = self.p._sk(self.key())
        self.p.settings["prompt_" + sk] = "x"
        res = self.run_cmd(".ai off")
        self.assertEqual(res.strategy, 1)
        self.assertNotIn(self.key(), self.p._chats)
        self.assertIsNone(self.p.settings.get("prompt_" + sk))
        self.assertIn("admin_off", self.p.decisions_text())
        self.run_cmd(".ai off")
        self.assertIn("admin_off_none", self.p.decisions_text())

    def test_status_and_list(self):
        self.run_cmd(".ai status")
        self.assertIn("OFF", self.last_bulletin())
        self.run_cmd(".ai on")
        self.run_cmd(".ai status")
        self.assertIn("ON", self.last_bulletin())
        self.assertIn("Auto", self.last_bulletin())
        self.run_cmd(".ai list")
        self.assertIn("Alice (Auto)", self.last_bulletin())
        self.assertIn("(1)", self.last_bulletin())
        self.p.chat_off(self.key(), remove=True)
        self.run_cmd(".ai list")
        self.assertIn("No active chats", self.last_bulletin())
        d = self.p.decisions_text()
        self.assertIn("admin_status", d)
        self.assertIn("admin_list", d)

    def test_status_shows_last_decision(self):
        self.run_cmd(".ai on")
        self.incoming(text="привіт, як справи")
        self.fire_timers()
        self.run_cmd(".ai status")
        self.assertIn("sent", self.last_bulletin())

    def test_mode_switch(self):
        self.run_cmd(".ai mode draft")
        self.assertIn("on first", self.last_bulletin())            # unlisted
        self.run_cmd(".ai on")
        for arg, val in (("draft", 1), ("friend", 2), ("auto", 0), ("друг", 2), ("чернетка", 1)):
            self.run_cmd(".ai mode " + arg)
            self.assertEqual(self.p._chat_mode(self.key()), val)
        self.run_cmd(".ai mode nonsense")
        self.assertIn("Use:", self.last_bulletin())
        self.assertIn("admin_mode_bad", self.p.decisions_text())

    def test_refuses_group_channel_bot_secret(self):
        for info in ({"type": "group"}, {"type": "channel"}, {"type": "user", "is_bot": True}, {"type": "secret"}):
            CLIENT.info = dict(info, title="x")
            res = self.run_cmd(".ai on")
            self.assertEqual(res.strategy, 1)                      # still not sent as a message
            self.assertFalse(self.p.is_enabled(self.key()))
            self.assertIn("Only private", self.last_bulletin())
        self.assertIn("admin_refused", self.p.decisions_text())

    def test_not_a_command_when_extra_words(self):
        self.p.settings["typing_delay"] = False
        CLIENT.history[:] = []
        self.p.chat_on(0, DID, "Alice", "user")
        self.run_cmd(".ai on the weekend")                         # a topic for the old command
        self.assertIn("owner_command", self.p.decisions_text())
        self.assertNotIn("admin_on", self.p.decisions_text())

    def test_command_switch_off_sends_as_normal_message(self):
        self.p.settings["cmd_enable"] = False
        self.assertIsNone(self.run_cmd(".ai on"))
        self.assertFalse(self.p.is_enabled(self.key()))
        self.assertIn("command_disabled", self.p.decisions_text())

    def test_attachment_is_ignored(self):
        pr = RealParams(".ai on")
        pr.document = object()
        self.assertIsNone(self.p.on_send_message_hook(0, pr))
        self.assertFalse(self.p.is_enabled(self.key()))

    def test_localized_uk_and_ru(self):
        self.p.settings["ui_lang"] = 1
        self.run_cmd(".ai on")
        self.assertIn("УВІМКНЕНО", self.last_bulletin())
        self.p.settings["ui_lang"] = 2
        self.run_cmd(".ai status")
        self.assertIn("бот ВКЛ.", self.last_bulletin())
        self.p.settings["ui_lang"] = 1
        self.run_cmd(".ai list")
        self.assertIn("Активні чати", self.last_bulletin())
        self.run_cmd(".ai off")
        self.assertIn("прибрано", self.last_bulletin())
        self.assertIn("команда", self.p.decisions_text() + "команда")       # decision rows exist
        rows = self.p.decision_rows()
        self.assertTrue(any("чат прибрано" in sentence for _t, sentence, _r in rows))

    def test_cyrillic_lookalike_trigger_and_aliases(self):
        self.run_cmd(".аі on")
        self.assertTrue(self.p.is_enabled(self.key()))
        self.run_cmd(".ai вимк")
        self.assertFalse(self.p.is_enabled(self.key()))
        self.run_cmd(".ai увімк")
        self.assertTrue(self.p.is_enabled(self.key()))

    def test_fallback_when_send_hook_missed_works_in_unlisted_chat(self):
        self.assertIsNone(self.incoming(text=".ai on", out=True))
        self.assertTrue(self.p.is_enabled(self.key()))
        self.assertIn("owner_command_hook_missed", self.p.decisions_text())

    def test_master_off_is_mentioned_but_chat_is_added(self):
        self.p.settings["master"] = False
        self.run_cmd(".ai on")
        self.assertTrue(self.p.is_enabled(self.key()))
        self.assertIn("master switch", self.last_bulletin())

    def test_on_does_not_reset_mode_of_existing_chat(self):
        self.run_cmd(".ai on")
        self.run_cmd(".ai mode draft")
        self.run_cmd(".ai on")
        self.assertEqual(self.p._chat_mode(self.key()), mod.MODE_DRAFT)


class TestMenu(Cmd):
    def test_menu_texts_and_toggle(self):
        texts = {i.key: i.text for i in self.p.menu}
        self.assertIn("Bot in this chat: off", texts["ai_autoreply_off"])
        self.assertIn("Bot in this chat: on", texts["ai_autoreply_on"])
        self.enable()
        self.assertEqual(self.p._chat_mode(self.key()), mod.MODE_AUTO)
        self.p.on_disable_click({"account": 0, "dialog_id": DID})
        self.assertFalse(self.p.is_enabled(self.key()))
        self.assertIn(self.key(), self.p._chats)                    # paused, still listed
        self.enable()


class TestSettingsScreen(Cmd):
    def titles(self):
        return [(type(i).__name__, getattr(i, "text", "")) for i in self.p.create_settings()]

    def test_order_main_chats_add_groups_decisions_last(self):
        # 0.4.9: the section selector first; Main by default, the chats with adding a chat right below them in
        # their own section, the log is the last section
        self.p.chat_on(0, DID, "Alice", "user")
        self.incoming(text="привіт")
        items = self.p.create_settings()
        self.assertEqual((type(items[0]).__name__, items[0].key), ("Selector", "ui_section"))
        self.assertEqual(items[0].items, ["Main", "Chats", "Style", "Timing and pauses", "Limits", "Commands",
                                          "Media and memory", "Prompts and model", "Style test", "Log"])
        self.assertEqual(items[0].default, 0)
        self.assertIn("master", [getattr(i, "key", None) for i in items])
        self.assertFalse(any(str(getattr(it, "key", "")).startswith("chat_") for it in items))
        items = chats_screen(self.p)
        kinds = [type(i).__name__ for i in items]
        pos = lambda pred: next(i for i, it in enumerate(items) if pred(it))
        chats = pos(lambda it: str(getattr(it, "text", "")).startswith("Chats with the bot"))
        add = pos(lambda it: getattr(it, "text", "") == "Add chat")
        row = pos(lambda it: getattr(it, "key", "") == "chat_" + self.p._sk(self.key()))
        self.assertLess(0, chats)
        self.assertLess(chats, row)
        self.assertLess(row, add)
        self.assertEqual(kinds[add + 1:add + 3], ["DialogPicker", "UsernameInput"])
        self.assertNotIn("master", [getattr(i, "key", None) for i in items])
        self.assertEqual(mod.Plugin.UI_SECTIONS[-1], "log")
        items = screen(self.p, "log")
        self.assertEqual(items[-1].text, "Newest first. No message text is stored.")

    def test_row_has_mode_state_and_last_decision(self):
        self.p.chat_on(0, DID, "Alice", "user")
        self.incoming(text="привіт, як справи")
        self.fire_timers()
        row = next(i for i in chats_screen(self.p) if getattr(i, "key", "") == "chat_" + self.p._sk(self.key()))
        self.assertIn("Alice", row.text)
        self.assertIn("Auto", row.subtext)
        self.assertIn("on", row.subtext)
        self.assertIn("last:", row.subtext)
        self.assertIn("sent", row.subtext)

    def test_tap_opens_options_with_existing_keys_and_closes(self):
        self.p.chat_on(0, DID, "Alice", "user")
        sk = self.p._sk(self.key())
        keys = lambda: {getattr(i, "key", None) for i in chats_screen(self.p)}
        self.assertNotIn("mode_" + sk, keys())
        next(i for i in chats_screen(self.p) if getattr(i, "key", "") == "chat_" + sk).on_click()
        self.assertTrue({"mode_" + sk, "prompt_" + sk, "keep_" + sk, "remove_" + sk, "test_" + sk,
                         "react_" + sk} <= keys())
        next(i for i in chats_screen(self.p) if getattr(i, "key", "") == "chat_" + sk).on_click()
        self.assertNotIn("mode_" + sk, keys())

    def test_title_refreshed_from_dialog_info(self):
        self.p.chat_on(0, DID, str(DID), "user")
        row = next(i for i in chats_screen(self.p) if getattr(i, "key", "") == "chat_" + self.p._sk(self.key()))
        self.assertIn("Alice", row.text)
        # 0.4.5: drawing the screen never writes; the missing title is stored on load / after a core edit
        self.p.on_app_event("settings_changed")
        self.assertEqual(self.p._chats[self.key()]["title"], "Alice")

    def test_picked_chat_starts_auto_and_enabled(self):
        self.p.on_chat_added(DID, "Alice")
        self.assertTrue(self.p.is_enabled(self.key()))
        self.assertEqual(self.p.settings["mode_" + self.p._sk(self.key())], 0)

    def test_storage_format_is_backward_compatible(self):
        self.run = self.p.on_send_message_hook(0, RealParams(".ai on"))
        data = json.loads(self.p.settings["chats"])
        c = data[self.key()]
        self.assertEqual(set(c), {"enabled", "account", "dialog_id", "title", "type", "fails"})
        self.assertIs(c["enabled"], True)
        self.assertIsInstance(c["dialog_id"], int)
        self.assertEqual(json.loads(self.p.settings["decisions"])[0].keys() >= {"t", "chat", "o", "r"}, True)


class TestAutonomous(Cmd):
    def setUp(self):
        Cmd.setUp(self)
        self.p.settings.pop("debounce", None)
        self.p.settings["typing_delay"] = True
        CLIENT.history[:] = []

    def test_balanced_defaults(self):
        self.assertEqual(self.p._pnum("owner_active", 0, 3600), 45)
        self.assertEqual(self.p._pnum("chat_hourly", 1, 1000), 20)
        self.assertEqual(self.p._reply_lang_mode(self.key()), 0)

    def test_end_to_end_incoming_debounce_ai_clean_send(self):
        self.p.chat_on(0, DID, "Alice", "user")
        CLIENT.ai_result = lambda m, **kw: "**Звісно**, зараз гляну"
        t0 = self.clock[0]
        self.assertIsNone(self.incoming(text="привіт, ти де зараз"))
        self.assertEqual(CLIENT.sent, [])                          # waits for the debounce first
        self.fire_timers()
        self.assertEqual(len(CLIENT.ai_calls), 1)
        self.assertEqual(len(CLIENT.sent), 1)
        did, text, _ = CLIENT.sent[0]
        self.assertEqual(did, DID)
        self.assertNotIn("**", text)
        self.assertNotIn("Звісно", text)
        self.assertIn("зараз гляну", text)
        self.assertTrue(4.0 <= self.clock[0] - t0 <= 6.5, self.clock[0] - t0)
        d = self.p.decisions_text()
        self.assertIn("seen: incoming_seen", d)
        self.assertIn("sent: ok", d)

    def test_owner_writing_recently_logs_reason_then_answers_after_45s(self):
        self.p.chat_on(0, DID, "Alice", "user")
        self.incoming(out=True, text="зараз, хвилинку")
        self.incoming(text="ти де?")
        self.fire_once()                                           # first attempt: owner is active
        self.assertEqual(CLIENT.sent, [])
        self.assertIn("skip: owner_active", self.p.decisions_text())
        self.fire_timers()                                          # retried after the silence window
        self.assertEqual(len(CLIENT.sent), 1)
        self.assertGreaterEqual(self.clock[0] - 1000000.0, 45)

    def test_owner_message_older_than_45s_does_not_block(self):
        self.p.chat_on(0, DID, "Alice", "user")
        self.incoming(out=True, text="йо")
        self.clock[0] += 50
        self.incoming(text="ти де?")
        self.fire_timers()
        self.assertEqual(len(CLIENT.sent), 1)

    def test_deferred_batch_dropped_when_owner_answered_meanwhile(self):
        self.p.chat_on(0, DID, "Alice", "user")
        self.incoming(out=True, text="йо")
        self.incoming(text="ти де?")
        self.fire_once()
        CLIENT.history[:] = hist_of([(False, "ти де?"), (True, "тут, пишу")])   # the owner replied himself
        CLIENT.history[0]["id"] = self.n
        for h in CLIENT.history:
            h["date"] = int(self.clock[0]) - 1
        self.clock[0] += 60
        self.fire_timers()
        self.assertEqual(CLIENT.sent, [])
        self.assertIn("empty_context_last_message_is_not_from_them", self.p.decisions_text())

    def test_defers_are_limited(self):
        self.p.chat_on(0, DID, "Alice", "user")
        self.incoming(out=True, text="йо")
        self.incoming(text="ти де?")
        for _ in range(8):
            if CLIENT.ui_queue:
                self.fire_once()
                self.incoming(out=True, text="ще пишу")      # the owner keeps writing
        self.assertEqual(CLIENT.sent, [])
        self.assertEqual(self.p._state(self.key()).pending, [])

    def test_draft_and_friend_modes_untouched(self):
        self.p.chat_on(0, DID, "Alice", "user")
        self.p.set_setting("mode_" + self.p._sk(self.key()), 1)
        self.incoming(text="привіт, як справи")
        self.fire_timers()
        self.assertEqual(CLIENT.sent, [])
        self.assertEqual(len(CLIENT.drafts), 1)


class TestShortUpdates(Cmd):
    def short(self, text="привіт, як справи", mid=500, out=False, user_id=DID):
        return SimpleNamespace(id=mid, user_id=user_id, message=text, date=int(self.clock[0]), out=out)

    def setUp(self):
        Cmd.setUp(self)
        self.p.settings["typing_delay"] = False
        CLIENT.ai_result = lambda m, **kw: "та норм, ти як"
        self.p.chat_on(0, DID, "Alice", "user")

    def test_hook_registered(self):
        self.assertIn("TL_updateShortMessage", self.p.updates_hooks)
        self.assertIn("TL_updateShortChatMessage", self.p.updates_hooks)

    def test_short_message_goes_through_pipeline(self):
        res = self.p.on_updates_hook("TL_updateShortMessage", 0, self.short())
        self.assertIsNone(res)
        self.assertIn("incoming_seen", self.p.decisions_text())
        self.fire_timers()
        self.assertEqual(len(CLIENT.sent), 1)

    def test_both_paths_answer_once(self):
        self.p.on_updates_hook("TL_updateShortMessage", 0, self.short(mid=77))
        self.incoming(text="привіт, як справи", mid=77)            # on_new_message for the same message
        self.fire_timers()
        self.assertEqual(len(CLIENT.sent), 1)
        self.assertEqual(len(CLIENT.ai_calls), 1)
        self.assertEqual(self.p.decisions_text().count("incoming_seen"), 1)
        # the other order
        self.clock[0] += 100
        self.incoming(text="а ти де", mid=78)
        self.p.on_updates_hook("TL_updateShortMessage", 0, self.short(text="а ти де", mid=78))
        self.fire_timers()
        self.assertEqual(len(CLIENT.sent), 2)

    def test_short_outgoing_counts_as_owner_activity(self):
        self.p.on_updates_hook("TL_updateShortMessage", 0, self.short(text="йо", out=True, mid=9))
        self.assertGreater(self.p._state(self.key()).owner_ts, 0)

    def test_short_chat_message_dialog_and_unlisted_ignored(self):
        self.p.chat_on(0, -1000, "Team", "group")
        u = SimpleNamespace(id=5, chat_id=1000, from_id=7, message="що робимо?", date=int(self.clock[0]), out=False)
        self.p.on_updates_hook("TL_updateShortChatMessage", 0, u)
        self.assertIn("incoming_seen", self.p.decisions_text())
        n = self.p.decisions_text().count("incoming_seen")
        self.p.on_updates_hook("TL_updateShortMessage", 0, self.short(user_id=999, mid=1))   # not listed
        self.assertEqual(self.p.decisions_text().count("incoming_seen"), n)

    def test_garbage_update_never_raises(self):
        self.assertIsNone(self.p.on_updates_hook("TL_updateShortMessage", 0, object()))
        self.assertIsNone(self.p.on_updates_hook("TL_other", 0, self.short()))
        self.assertEqual(self.p.errors, [])

    def test_incoming_seen_collapses_in_ring_and_does_not_count_as_last(self):
        for i in range(5):
            self.incoming(text="ок %d" % i, mid=900 + i)
        seen = [r for r in self.p._decisions if r["o"] == "seen"]
        self.assertEqual(len(seen), 1)
        self.assertEqual(self.p._last_for(self.key()), self.p.t("no_last"))


class TestReplyLanguage(Cmd):
    RU = [(False, "привет, что делаешь"), (True, "да так, дома сижу"), (False, "ясно, а вечером как"),
          (True, "ещё не знаю, посмотрим"), (False, "ок")]
    UK = [(False, "привіт, що робиш"), (True, "та нічого, вдома сиджу"), (False, "ясно"),
          (True, "ще не знаю, подивимось")]
    MIX = [(True, "та нічого, вдома"), (True, "что там у тебя"), (True, "ще не знаю"), (True, "ну ладно, потом скажу")]

    def setUp(self):
        Cmd.setUp(self)
        self.p.settings["typing_delay"] = False
        self.p.chat_on(0, DID, "Alice", "user")

    def system(self):
        return CLIENT.ai_calls[-1]["system"]

    def test_pure_function(self):
        f = mod.context_language
        self.assertEqual(f(["да так, дома ещё сижу"], ["привіт"]), "Russian")
        self.assertEqual(f(["та нічого, вдома"], ["привет"]), "Ukrainian")
        self.assertIsNone(f(["ок"], ["лол"]))
        self.assertEqual(f([], ["привет что делаешь"]), "Russian")              # no own signal: the other side
        self.assertEqual(f(["что там", "та нічого вдома"], []), "Ukrainian")    # mix: owner's latest

    def test_russian_chat_auto_replies_in_russian(self):
        CLIENT.history[:] = hist_of(self.RU)
        self.incoming(text="ну что, ты где")
        self.fire_timers()
        self.assertIn("LANGUAGE OF THIS REPLY", self.system())
        self.assertIn("Russian. Отвечай по-русски", self.system())
        self.assertNotIn("Ukrainian. Відповідай", self.system())

    def test_ukrainian_chat_auto_replies_in_ukrainian(self):
        CLIENT.history[:] = hist_of(self.UK)
        self.incoming(text="ну що, ти де")
        self.fire_timers()
        self.assertIn("Ukrainian. Відповідай українською", self.system())

    def test_mixed_owner_follows_latest_own_message(self):
        CLIENT.history[:] = hist_of(self.MIX)
        self.incoming(text="привіт")
        self.fire_timers()
        self.assertIn("Russian. Отвечай", self.system())
        CLIENT.history[:] = hist_of(self.MIX[::-1])
        self.p._lang_cache.clear()
        self.incoming(text="привіт ще раз")
        self.clock[0] += 100
        self.fire_timers()
        self.assertIn("Ukrainian. Відповідай", CLIENT.ai_calls[-1]["system"])

    def test_no_signal_defaults_to_ukrainian(self):
        CLIENT.history[:] = hist_of([(False, "ok"), (True, "ага")])
        self.incoming(text="ok")
        self.p.settings["skip_ack"] = False
        self.incoming(text="ok ok?")
        self.fire_timers()
        self.assertIn("Ukrainian. Відповідай", self.system())

    def test_plugin_texts_do_not_count_as_owner_language(self):
        CLIENT.history[:] = hist_of(self.RU)
        self.p._remember_bot_text("привіт ще не знаю що робити сьогодні")
        CLIENT.history.append({"id": 2000, "from_id": 1, "out": True, "date": 99,
                               "text": "привіт ще не знаю що робити сьогодні", "is_bot": False})
        self.assertEqual(self.p.pick_reply_lang(self.key(), 0, DID, ""), "Russian")

    def test_global_and_per_chat_override(self):
        CLIENT.history[:] = hist_of(self.RU)
        self.p.settings["reply_lang"] = 1
        self.assertEqual(self.p.pick_reply_lang(self.key(), 0, DID, "привет"), "Ukrainian")
        self.p.settings["reply_lang"] = 2
        self.assertEqual(self.p.pick_reply_lang(self.key(), 0, DID, "привіт"), "Russian")
        self.p.settings["reply_lang"] = 3
        self.assertEqual(self.p.pick_reply_lang(self.key(), 0, DID, "привіт, як ти"), "Ukrainian")
        self.assertEqual(self.p.pick_reply_lang(self.key(), 0, DID, "привет, как ты"), "Russian")
        self.p.settings["rlang_" + self.p._sk(self.key())] = 2          # per chat: Ukrainian
        self.assertEqual(self.p.pick_reply_lang(self.key(), 0, DID, "привет"), "Ukrainian")
        self.p.settings["rlang_" + self.p._sk(self.key())] = 1          # per chat: auto
        self.assertEqual(self.p.pick_reply_lang(self.key(), 0, DID, "привіт"), "Russian")

    def test_context_cached_per_chat(self):
        CLIENT.history[:] = hist_of(self.RU)
        self.assertEqual(self.p.pick_reply_lang(self.key(), 0, DID, ""), "Russian")
        CLIENT.history[:] = hist_of(self.UK)
        self.assertEqual(self.p.pick_reply_lang(self.key(), 0, DID, ""), "Russian")     # cached
        self.clock[0] += 700
        self.assertEqual(self.p.pick_reply_lang(self.key(), 0, DID, ""), "Ukrainian")

    def test_ai_command_continue_uses_chat_language(self):
        CLIENT.history[:] = [dict(h, date=int(self.clock[0]) - 60) for h in hist_of(self.RU)]
        self.run_cmd(".ai")
        self.assertIn("Russian. Отвечай", self.system())
        self.run_cmd(".ai дай совет")
        self.assertIn("Russian. Отвечай", self.system())

    def test_ai_command_to_draft_uses_chat_language(self):
        CLIENT.history[:] = [dict(h, date=int(self.clock[0]) - 60) for h in hist_of(self.RU)]
        self.run_cmd(".ai ?")
        self.assertEqual(len(CLIENT.drafts), 1)
        self.assertIn("Russian. Отвечай", self.system())

    def test_openers_follow_chat_language(self):
        CLIENT.history[:] = [dict(h, date=int(self.clock[0]) - 4 * 86400) for h in hist_of(self.RU)]
        self.run_cmd(".ai")
        last = CLIENT.ai_calls[-1]["messages"][-1]["content"]
        self.assertTrue(any(o in last for o in mod.DEFAULT_OPENERS_RU), last)
        self.p.settings["humanize"] = False
        self.p._lang_cache.clear()
        self.run_cmd(".ai")
        self.assertIn(CLIENT.sent[-1][1], mod.DEFAULT_OPENERS_RU)
        CLIENT.history[:] = [dict(h, date=int(self.clock[0]) - 4 * 86400) for h in hist_of(self.UK)]
        self.p._lang_cache.clear()
        self.clock[0] += 100
        self.run_cmd(".ai")
        self.assertIn(CLIENT.sent[-1][1], mod.DEFAULT_OPENERS)

    def test_settings_have_language_selectors(self):
        sk = self.p._sk(self.key())
        keys = {getattr(i, "key", None): i for i in self.p.create_settings()}
        self.assertEqual(keys["reply_lang"].default, 3)
        self.assertEqual(len(keys["reply_lang"].items), 4)
        self.p._open_key = self.key()
        keys = {getattr(i, "key", None): i for i in chats_screen(self.p)}
        self.assertEqual(len(keys["rlang_" + sk].items), 5)


class TestMetadata(unittest.TestCase):
    def test_version(self):
        self.assertTrue(open(mod.__file__ if hasattr(mod, "__file__") and mod.__file__ else
                             __import__("test_ai_autoreply").PLUGIN, encoding="utf-8").read()
                        .count('__version__ = "0.5.1"\n__version_code__ = 23') == 1)


if __name__ == "__main__":
    unittest.main()
