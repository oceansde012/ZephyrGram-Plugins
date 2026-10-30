"""0.3.1 regression tests: silent paths, anti-annoyance defaults, short typing delay, banned words.

Run: python -m unittest discover -s tests -v
"""
import unittest

from test_ai_autoreply import Base, CLIENT, DID, mod, own_history

LONG_UK = ("Це перше речення досить довге, щоб воно точно не влізло в одну коротку репліку. "
           "Це друге речення теж не маленьке, тому його варто відправити окремо.")


class TestSilentPaths(Base):
    """Every path that used to drop a reply silently."""

    def setUp(self):
        Base.setUp(self)
        self.enable()
        CLIENT.history[:] = own_history()
        CLIENT.ai_result = lambda m, **kw: "та норм, ти як"

    def round(self, *texts):
        for t in texts:
            self.incoming(text=t)
        self.fire_timers()

    def decisions(self):
        return self.p.decisions_text()

    def test_private_auto_two_messages_one_reply_preset_debounce(self):
        # friend (cherish) scenario: private chat, Auto, default Balanced preset, nothing configured
        self.p.settings.pop("debounce", None)
        t0 = self.clock[0]
        self.round("привіт, як справи", "що робиш сьогодні")
        self.assertEqual(len(CLIENT.ai_calls), 1)
        self.assertEqual(len(CLIENT.sent), 1)
        self.assertEqual(CLIENT.ai_calls[0]["messages"][-1]["content"], "що робиш сьогодні")
        self.assertTrue(4.0 <= self.clock[0] - t0 <= 6.5, self.clock[0] - t0)
        self.assertIn("sent", self.decisions())

    def test_second_batch_answered_after_cooldown(self):
        self.round("привіт, як справи")
        self.round("а ти де зараз")
        self.assertEqual(len(CLIENT.sent), 2)

    def test_banned_words_regenerated_then_sent_anyway(self):
        CLIENT.ai_result = lambda m, **kw: "Звісно, я розумію, це дійсно важливо"
        self.round("привіт, як справи")
        self.assertEqual(len(CLIENT.ai_calls), 2)
        self.assertIn("banned", CLIENT.ai_calls[1]["system"])
        self.assertEqual(len(CLIENT.sent), 1)
        self.assertIn("ok_fallback", self.decisions())

    def test_banned_retry_can_succeed(self):
        replies = iter(["Безумовно, звісно", "та глянув уже"])
        CLIENT.ai_result = lambda m, **kw: next(replies)
        self.round("привіт, як справи")
        self.assertTrue(CLIENT.sent[0][1].endswith("та глянув уже"))

    def test_banned_helper(self):
        self.assertTrue(mod.banned_hits("Дійсно, варто зазначити"))
        self.assertTrue(mod.banned_hits("конечно, на самом деле"))
        self.assertEqual(mod.banned_hits("та норм, ти як"), [])
        self.assertEqual(mod.banned_hits("абв", ["абв"]), ["абв"])

    def test_wrong_language_regenerated(self):
        replies = iter(["你好，很高兴见到你", "привіт, ти як"])
        CLIENT.ai_result = lambda m, **kw: next(replies)
        self.round("привіт")
        self.assertTrue(CLIENT.sent[0][1].endswith("привіт, ти як"))
        self.assertIn("Ukrainian", CLIENT.ai_calls[0]["system"])
        self.assertEqual(mod.detect_lang("привет, что делаешь"), "Russian")
        self.assertEqual(mod.detect_lang("привіт"), "Ukrainian")

    def test_missing_date_is_not_dropped(self):
        m = self.msg(text="привіт, як справи")
        m["date"] = None
        self.assertIsNone(self.p.handle_incoming(0, m))
        self.fire_timers()
        self.assertEqual(len(CLIENT.sent), 1)

    def test_ack_skipped_unless_question(self):
        for t in ("ок", "дякую", "ага", "лол", "ахахах", "\U0001F44D", "ок дякую"):
            self.round(t)
            self.clock[0] += 5
        self.assertEqual(CLIENT.ai_calls, [])
        self.assertIn("acknowledgement", self.decisions())
        self.round("ок, а ти де?")
        self.assertEqual(len(CLIENT.sent), 1)
        self.clock[0] += 100
        self.round("дякую", "а завтра прийдеш")           # ack followed by a real message
        self.assertEqual(len(CLIENT.ai_calls), 2)

    def test_ack_helpers(self):
        self.assertTrue(mod.is_ack("Ок"))
        self.assertTrue(mod.is_ack("дякууую"))
        self.assertFalse(mod.is_ack("ок?"))
        self.assertFalse(mod.is_ack("ок давай завтра зустрінемось"))

    def test_owner_active_skip_then_resume(self):
        self.assertEqual(self.incoming(out=True, text="йо, зараз гляну"), "outgoing")
        self.round("привіт, як справи")
        self.assertEqual(CLIENT.ai_calls, [])
        self.assertIn("owner_active", self.decisions())
        self.clock[0] += 130
        self.round("ти де взагалі")
        self.assertEqual(len(CLIENT.sent), 1)

    def test_owner_active_from_history(self):
        CLIENT.history.append({"id": 900, "from_id": 1, "out": True, "date": int(self.clock[0]) - 20,
                               "text": "та ні, не треба", "is_bot": False})
        self.round("а чому?")
        self.assertEqual(CLIENT.sent, [])
        self.assertIn("owner_active", self.decisions())

    def test_plugin_own_messages_do_not_count_as_owner_active(self):
        self.round("привіт, як справи")
        self.assertEqual(len(CLIENT.sent), 1)
        CLIENT.history.append({"id": 950, "from_id": 1, "out": True, "date": int(self.clock[0]),
                               "text": CLIENT.sent[0][1], "is_bot": False})
        self.incoming(out=True, text=CLIENT.sent[0][1])          # hook echo of our own send
        self.clock[0] += 30
        self.round("а ти де зараз")
        self.assertEqual(len(CLIENT.sent), 2)

    def test_cooldown_min_20s_between_replies(self):
        self.round("привіт, як справи")
        t = self.clock[0]
        self.incoming(text="а ти де зараз")
        self.fire_timers()
        self.assertEqual(len(CLIENT.sent), 2)
        self.assertGreaterEqual(self.clock[0] - t, 15)

    def test_chat_hourly_cap_polite_stop(self):
        self.p.settings["chat_hourly"] = "2"
        self.p.settings["cooldown"] = "0"
        for i in range(4):
            self.round("питання номер %d тут" % i)
            self.clock[0] += 5
        texts = [x[1] for x in CLIENT.sent]
        self.assertEqual(len(CLIENT.ai_calls), 2)
        self.assertEqual(len(texts), 3)                            # 2 replies + one polite stop
        self.assertIn(mod.POLITE_STOP_TEXT, texts[2])
        self.assertIn("chat_hourly_cap", self.decisions())
        self.clock[0] += 3700
        CLIENT.ai_result = lambda m, **kw: "та все ок, а в тебе"
        self.round("а тепер що там нового")
        self.assertEqual(len(CLIENT.ai_calls), 3)

    def test_group_needs_question(self):
        CLIENT.info = {"id": DID, "title": "G", "type": "group", "is_bot": False}
        self.p.on_chat_added(DID, "G")
        self.round("всім привіт вчора було весело")
        self.assertEqual(CLIENT.ai_calls, [])
        self.assertIn("group_no_question", self.decisions())
        self.round("хто йде завтра?")
        self.assertEqual(len(CLIENT.sent), 1)

    def test_quiet_hours(self):
        self.p.settings["quiet_hours"] = "00:01-00:00"
        self.round("привіт, як справи")
        self.assertEqual(CLIENT.ai_calls, [])
        self.assertIn("quiet_hours", self.decisions())
        self.assertEqual(mod.parse_quiet_hours("23:00-08:00"), (1380, 480))
        self.assertIsNone(mod.parse_quiet_hours("nonsense"))

    def test_typing_delay_bounds_short_and_long(self):
        slept = []
        mod.time.sleep = lambda s: slept.append(s)
        self.round("привіт, як справи")
        self.assertTrue(0.4 <= sum(slept) <= 2.5 + 1e-9, slept)
        self.assertEqual(len(CLIENT.sent), 1)
        del slept[:]
        self.p.settings["cooldown"] = "0"
        CLIENT.ai_result = lambda m, **kw: LONG_UK
        self.round("а ти де зараз")
        self.assertEqual(len(CLIENT.sent), 3)                      # split in at most 2 parts
        self.assertLessEqual(sum(slept), 2.5 + 1e-9)
        self.p.settings["typing_cap"] = "0.5"
        del slept[:]
        self.clock[0] += 100
        CLIENT.ai_result = lambda m, **kw: "та нормально все, ти як сам"
        self.round("ну і де ти був")
        self.assertTrue(slept)
        self.assertLessEqual(sum(slept), 0.5 + 1e-9)

    def test_short_reply_never_split(self):
        CLIENT.ai_result = lambda m, **kw: "ага ща. зараз гляну, почекай трохи. ок"
        self.round("привіт, як справи")
        self.assertEqual(len(CLIENT.sent), 1)

    def test_exceptions_never_silent(self):
        CLIENT.ai_result = lambda m, **kw: RuntimeError("boom")
        self.round("привіт, як справи")
        self.assertIn("ai_failed", self.decisions())
        self.p.caps_ok = lambda key: 1 / 0
        self.clock[0] += 100
        self.round("а ти де зараз")
        self.assertIn("process_exception", self.decisions())

    def test_auto_disabled_chat_resumes(self):
        CLIENT.ai_result = lambda m, **kw: RuntimeError("boom")
        for i in range(mod.MAX_FAILURES):
            self.round("питання номер %d тут" % i)
            self.clock[0] += 30
        self.assertFalse(self.p.is_enabled(self.key()))
        CLIENT.ai_result = lambda m, **kw: "та норм, ти як"
        self.clock[0] += mod.AUTH_RESUME_SEC + 1
        self.round("ти тут ще?")
        self.assertEqual(len(CLIENT.sent), 1)

    def test_decisions_have_no_message_text_and_are_limited(self):
        for i in range(30):
            self.p._decide(self.key(), "skip", "reason %d" % i)
        self.round("секретний текст повідомлення?")
        txt = self.decisions()
        self.assertNotIn("секретний", txt)
        self.assertLessEqual(len(txt.splitlines()), 20)
        self.assertTrue(any("decision" in l for l in self.p.logs))
        p2 = mod.Plugin()
        p2.settings = dict(self.p.settings)
        p2.on_plugin_load()
        self.assertEqual(p2.decisions_text(), txt)

    def test_settings_have_preset_and_decisions(self):
        items = self.p.create_settings()
        keys = {getattr(i, "key", None): i for i in items}
        self.assertEqual(keys["preset"].default, 0)
        self.assertEqual(len(keys["preset"].items), 3)
        self.assertTrue(any("Recent decisions" in str(getattr(i, "text", "")) for i in items))
        self.p.settings["preset"] = 2                         # Quiet
        self.assertEqual(self.p._pnum("cooldown", 0, 3600), 60)

    def test_prompt_language_and_style(self):
        self.round("привіт")
        sysmsg = CLIENT.ai_calls[0]["system"]
        self.assertIn("Chinese", sysmsg)
        self.assertIn("Ukrainian", sysmsg)
        self.assertIn("звісно", sysmsg)
        self.assertIn("Chinese", mod.DEFAULT_PROMPT)

    def test_same_message_not_answered_twice(self):
        self.round("привіт, як справи")
        self.assertEqual(self.p.process(self.key(), [(self.n, 7, "привіт, як справи")]),
                         "already answered")

    def test_style_test_works(self):
        CLIENT.history[:] = [{"id": 10 + i, "from_id": 7, "out": False, "date": 100 + i,
                              "text": "питання %d" % i, "is_bot": False} for i in range(3)] + own_history()
        self.assertTrue(self.p.start_style_test(0, DID, "Alice"))
        self.assertEqual(CLIENT.sent, [])
        self.assertIn("питання 2", self.p.get_setting("style_test_result"))


if __name__ == "__main__":
    unittest.main()
