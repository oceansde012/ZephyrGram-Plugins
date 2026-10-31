"""0.4.2: no 'read but never answered', retries of passing failures, owner lore and learned chat notes."""
from test_ai_autoreply import Base, CLIENT, DID, mod


class ReadMarks(object):
    def install(self):
        self.reads = []
        CLIENT.mark_read = lambda did, mid, account=None: self.reads.append((did, mid))

    def remove(self):
        if hasattr(CLIENT, "mark_read"):
            del CLIENT.mark_read


class TestReadOnlyWhenAnswering(Base, ReadMarks):
    def setUp(self):
        super().setUp()
        self.enable()
        self.install()
        self.p.settings["owner_active"] = "0"

    def tearDown(self):
        self.remove()

    def test_failed_ai_does_not_mark_read(self):
        CLIENT.ai_result = lambda m, **kw: RuntimeError("down")
        self.p.settings["cooldown"] = "0"
        self.incoming(text="привіт, ти тут?")
        self.fire_once()                                   # the debounce timer: processing fails, nothing answered
        self.assertEqual(self.reads, [])
        self.assertEqual(CLIENT.sent, [])

    def test_read_mark_comes_with_the_answer(self):
        self.incoming(text="привіт, ти тут?")
        self.fire_timers()
        self.assertEqual(len(CLIENT.sent), 1)
        self.assertEqual(len(self.reads), 1)

    def test_live_owner_takes_over_while_waiting_no_read(self):
        self.p.settings["human_timing"] = True
        key = self.key()

        def ai(messages, **kw):
            self.p._state(key).owner_ts = self.clock[0] + 50        # you answered yourself meanwhile
            return "ага"
        CLIENT.ai_result = ai
        self.incoming(text="привіт, ти тут?")
        self.fire_timers()
        self.assertEqual(CLIENT.sent, [])
        self.assertEqual(self.reads, [])


class TestRetries(Base):
    def setUp(self):
        super().setUp()
        self.enable()
        self.p.settings["owner_active"] = "0"
        self.p.settings["cooldown"] = "0"

    def test_message_survives_a_passing_ai_failure(self):
        results = [RuntimeError("down"), RuntimeError("down")]
        CLIENT.ai_result = lambda m, **kw: results.pop(0) if results else "ось і я"
        self.incoming(text="привіт, ти тут?")
        for _ in range(6):
            self.clock[0] += 60
            self.fire_timers()
        self.assertEqual(len(CLIENT.sent), 1)
        self.assertTrue(CLIENT.sent[0][1].endswith("ось і я"))

    def test_gives_up_after_the_retry_limit(self):
        CLIENT.ai_result = lambda m, **kw: RuntimeError("down")
        self.p.settings["fails"] = 0
        self.incoming(text="привіт, ти тут?")
        for _ in range(12):
            self.clock[0] += 120
            self.fire_timers()
        self.assertEqual(CLIENT.sent, [])
        calls = len(CLIENT.ai_calls)
        self.clock[0] += 600
        self.fire_timers()
        self.assertEqual(len(CLIENT.ai_calls), calls)       # no endless loop

    def test_next_message_is_answered_after_a_failed_one(self):
        results = [RuntimeError("down")] * 3
        CLIENT.ai_result = lambda m, **kw: results.pop(0) if results else "добре"
        self.incoming(text="одне питання тут")
        for _ in range(8):
            self.clock[0] += 120
            self.fire_timers()
        self.clock[0] += 100
        self.incoming(text="а друге питання де")
        self.fire_timers()
        self.assertTrue(any(s[1].endswith("добре") for s in CLIENT.sent))


class TestLore(Base):
    def setUp(self):
        super().setUp()
        self.enable()
        self.sk = self.p._sk(self.key())

    def system(self):
        self.incoming(text="розкажи про себе щось")
        self.fire_timers()
        return CLIENT.ai_calls[-1]["system"]

    def test_no_lore_block_when_empty(self):
        self.assertNotIn("OWNER LORE", self.system())

    def test_global_chat_and_learned_lore_reach_the_prompt(self):
        self.p.settings["lore"] = "Я Влад, працюю в ДСНС, люблю Counter-Strike"
        self.p.settings["lore_" + self.sk] = "Cherish тестує мого бота"
        self.p.settings["learned_" + self.sk] = "- любить котів"
        system = self.system()
        self.assertIn("OWNER LORE", system)
        self.assertIn("працюю в ДСНС", system)
        self.assertIn("тестує мого бота", system)
        self.assertIn("NOTES LEARNED FROM THIS CHAT", system)
        self.assertIn("любить котів", system)

    def test_lore_is_used_without_humanize_and_in_commands_too(self):
        self.p.settings["humanize"] = False
        self.p.settings["lore"] = "Я Влад"
        self.assertIn("Я Влад", self.system())

    def test_removed_chat_forgets_lore_and_notes(self):
        self.p.settings["lore_" + self.sk] = "x"
        self.p.settings["learned_" + self.sk] = "- y"
        self.p.chat_off(self.key(), remove=True)
        self.assertIsNone(self.p.settings.get("lore_" + self.sk))
        self.assertIsNone(self.p.settings.get("learned_" + self.sk))


class TestParseNotes(Base):
    def test_filters_sensitive_and_limits(self):
        raw = ("- любить кішок\n- пароль від пошти 1234\n- працює в ДСНС\n- номер картки 4111111111111111\n"
               "- пише на @someone_name\n- любить кішок\nне нота\n- ok")
        self.assertEqual(mod.parse_notes(raw), [u"любить кішок", u"працює в ДСНС"])

    def test_none_and_garbage(self):
        self.assertEqual(mod.parse_notes("NONE"), [])
        self.assertIsNone(mod.parse_notes(""))
        self.assertIsNone(mod.parse_notes("просто текст без списку"))

    def test_at_most_twelve_and_clipped(self):
        raw = "\n".join("- факт номер %d" % i + "x" * 200 for i in range(30))
        notes = mod.parse_notes(raw)
        self.assertEqual(len(notes), 12)
        self.assertTrue(all(len(n) <= mod.LEARN_NOTE_CHARS for n in notes))


class TestLearning(Base):
    def setUp(self):
        super().setUp()
        self.enable()
        self.sk = self.p._sk(self.key())
        now = int(self.clock[0])
        CLIENT.history[:] = [
            {"id": i, "out": bool(i % 2), "date": now - 600 + i, "text": "повідомлення %d" % i,
             "dialog_id": DID, "from_id": 7} for i in range(1, 13)]

    def test_off_by_default(self):
        CLIENT.ai_result = lambda m, **kw: "- любить котів"
        self.p._learn_notes(self.key(), self.p._state(self.key()))
        self.assertEqual(CLIENT.ai_calls, [])
        self.assertFalse(self.p.settings.get("learned_" + self.sk))

    def test_notes_are_stored_and_sanitised(self):
        self.p.settings["lore_learn"] = True
        CLIENT.ai_result = lambda m, **kw: "- любить котів\n- пароль 12345678\n- вчиться на програміста"
        self.p._learn_notes(self.key(), self.p._state(self.key()))
        self.assertEqual(self.p.settings["learned_" + self.sk], "- любить котів\n- вчиться на програміста")
        user = CLIENT.ai_calls[-1]["messages"][0]["content"]
        self.assertIn("Other:", user)
        self.assertIn("Owner:", user)
        self.assertIn("Existing notes", user)

    def test_failed_or_garbage_answer_keeps_old_notes(self):
        self.p.settings["lore_learn"] = True
        self.p.settings["learned_" + self.sk] = "- старе"
        CLIENT.ai_result = lambda m, **kw: "вибач, не можу"
        self.p._learn_notes(self.key(), self.p._state(self.key()))
        self.assertEqual(self.p.settings["learned_" + self.sk], "- старе")

    def test_runs_after_enough_messages_only(self):
        self.p.settings["lore_learn"] = True
        st = self.p._state(self.key())
        self.p._learn_tick(self.key(), st, 3)
        self.assertFalse(st.learn_busy)
        self.p._learn_tick(self.key(), st, mod.LEARN_EVERY)
        self.assertTrue(st.learn_busy)
        self.assertTrue(CLIENT.ui_queue)
