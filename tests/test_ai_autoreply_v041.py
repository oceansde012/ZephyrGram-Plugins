"""0.4.0 review fixes: revive vs. running replies, reply-all edge cases, max_parts, media in the revive check."""
import json

from test_ai_autoreply import Base, CLIENT, DID, mod


class TestReviveKeepsReplyFlags(Base):
    def setUp(self):
        super().setUp()
        self.enable()
        self.p.settings.update(revive=True, owner_active="0")

    def test_revive_does_not_clear_inflight_of_a_running_reply(self):
        st = self.p._state(self.key())
        st.inflight = True                       # a normal reply is being processed right now
        st.revive_busy = True
        self.p._revive_run(self.key())
        self.assertTrue(st.inflight)
        self.assertFalse(st.revive_busy)
        self.assertEqual(CLIENT.ai_calls, [])

    def test_disabled_chat_still_keeps_flags(self):
        st = self.p._state(self.key())
        st.inflight = True
        self.p.chat_off(self.key(), remove=False)
        self.p._revive_run(self.key())
        self.assertTrue(st.inflight)

    def test_no_second_parallel_reply(self):
        # tick holds inflight; a revival fires meanwhile; a new message must wait for the running reply
        st = self.p._state(self.key())
        st.inflight = True
        self.p._revive_run(self.key())
        self.assertIsNone(self.incoming(text="ще одне"))
        self.fire_timers()
        self.assertEqual(CLIENT.ai_calls, [])    # still waits for the running request
        self.assertTrue(st.pending)


class TestReviveMediaReply(Base):
    def setUp(self):
        super().setUp()
        self.enable()
        self.p.settings.update(revive=True, owner_active="0")

    def test_sticker_reply_counts_as_an_answer(self):
        n = int(self.clock[0])
        CLIENT.history[:] = [
            {"id": 1, "out": False, "date": n - 2400, "text": "ну привіт", "dialog_id": DID, "from_id": 7},
            {"id": 2, "out": True, "date": n - 2300, "text": "здоров", "dialog_id": DID},
            {"id": 3, "out": False, "date": n - 2200, "text": "як справи", "dialog_id": DID, "from_id": 7},
            {"id": 4, "out": True, "date": n - 1800, "text": "нормально", "dialog_id": DID},
            {"id": 5, "out": False, "date": n - 1700, "text": "", "has_media": True, "dialog_id": DID, "from_id": 7},
        ]
        self.assertEqual(self.p._revive_pass(), 0)
        self.fire_timers()
        self.assertEqual(CLIENT.sent, [])

    def test_text_history_for_the_prompt_has_no_media_rows(self):
        n = int(self.clock[0])
        CLIENT.history[:] = [
            {"id": 1, "out": False, "date": n - 2400, "text": "ну привіт", "dialog_id": DID, "from_id": 7},
            {"id": 6, "out": False, "date": n - 2350, "text": "", "has_media": True, "dialog_id": DID, "from_id": 7},
            {"id": 3, "out": False, "date": n - 2200, "text": "як справи", "dialog_id": DID, "from_id": 7},
            {"id": 4, "out": True, "date": n - 1800, "text": "нормально", "dialog_id": DID},
        ]
        self.assertEqual(self.p._revive_pass(), 1)
        self.fire_timers()
        self.assertTrue(CLIENT.sent)
        contents = [m["content"] for m in CLIENT.ai_calls[-1]["messages"]]
        self.assertNotIn("[media]", " ".join(contents))
        self.assertNotIn("", contents)


class TestReviveDisclosure(Base):
    def test_disclosure_prefix_is_not_repeated_after_a_revival(self):
        self.enable()
        self.p.settings.update(revive=True, owner_active="0", disclosure=True)
        n = int(self.clock[0])
        CLIENT.history[:] = [
            {"id": 1, "out": False, "date": n - 2400, "text": "ну привіт", "dialog_id": DID, "from_id": 7},
            {"id": 3, "out": False, "date": n - 2200, "text": "як справи", "dialog_id": DID, "from_id": 7},
            {"id": 4, "out": True, "date": n - 1800, "text": "нормально", "dialog_id": DID},
        ]
        CLIENT.ai_result = lambda m, **kw: "до речі, ти дивився матч"
        self.assertEqual(self.p._revive_pass(), 1)
        self.fire_timers()
        self.assertTrue(CLIENT.sent[0][1].startswith(mod.ROBOT))
        self.p._load_chats()                     # any later reload from the store
        self.assertTrue(self.p._chats[self.key()].get("disclosed"))


class TestReplyAllEdges(Base):
    def setUp(self):
        super().setUp()
        self.p.settings["reply_all"] = True

    def test_info_fallback_failure_does_not_raise_and_is_not_cached(self):
        def broken(did, **kw):
            if kw:
                raise TypeError("old app")
            raise RuntimeError("not ready")
        CLIENT.get_dialog_info = broken
        try:
            self.assertIsNone(self.incoming(text="привіт"))     # must not raise
            self.assertFalse(self.p.is_enabled(self.key()))
        finally:
            CLIENT.get_dialog_info = lambda did, account=None: dict(CLIENT.info)
        self.clock[0] += 5
        self.assertIsNone(self.incoming(text="ти тут?"))
        self.assertTrue(self.p.is_enabled(self.key()))

    def test_missing_info_is_asked_again(self):
        CLIENT.get_dialog_info = lambda did, account=None: None
        try:
            self.incoming(text="привіт")
            self.assertFalse(self.p.is_enabled(self.key()))
        finally:
            CLIENT.get_dialog_info = lambda did, account=None: dict(CLIENT.info)
        self.clock[0] += 5
        self.incoming(text="ало")
        self.assertTrue(self.p.is_enabled(self.key()))

    def test_bot_refusal_is_still_cached(self):
        CLIENT.info = {"id": DID, "title": "Bot", "type": "user", "is_bot": True}
        self.incoming(text="hi")
        CLIENT.info = {"id": DID, "title": "Alice", "type": "user", "is_bot": False}
        self.incoming(text="hi again")
        self.assertFalse(self.p.is_enabled(self.key()))

    def test_service_and_empty_messages_do_not_add(self):
        m = self.msg(text="")
        m["is_service"] = True
        self.p.handle_incoming(0, m)
        self.p.handle_incoming(0, self.msg(text="   "))
        self.assertFalse(self.p.is_enabled(self.key()))

    def test_old_catch_up_message_does_not_add(self):
        self.p.handle_incoming(0, self.msg(text="привіт", age=3 * 24 * 3600))
        self.assertFalse(self.p.is_enabled(self.key()))
        self.p.handle_incoming(0, self.msg(text="привіт"))
        self.assertTrue(self.p.is_enabled(self.key()))

    def test_removed_chat_stays_skipped_with_a_long_skip_list(self):
        self.p.settings["all_skip"] = json.dumps(["0:%d" % (9000000 + i) for i in range(500)])
        self.enable()
        self.p.chat_off(self.key(), remove=True)
        skip = json.loads(self.p.settings["all_skip"])
        self.assertIn(self.key(), skip)
        self.assertEqual(len(skip), 500)
        self.assertEqual(skip[-1], self.key())
        self.incoming(text="я знову тут")
        self.assertNotIn(self.key(), self.p._read_chats())

    def test_skip_list_keeps_order_and_drops_on_add(self):
        self.p.settings["all_skip"] = json.dumps(["0:5", "0:%d" % DID, "0:1"])
        self.enable()
        self.assertEqual(json.loads(self.p.settings["all_skip"]), ["0:5", "0:1"])


class TestMergedLines(Base):
    def setUp(self):
        super().setUp()
        self.enable()

    def test_merged_lines_keep_their_break(self):
        self.assertEqual(mod.split_reply("не\nзавтра\nне встиг ще", 2), ["не\nзавтра", "не встиг ще"])
        self.p.settings["max_parts"] = "2"
        CLIENT.ai_result = lambda m, **kw: "не\nзавтра\nне встиг ще"
        self.incoming(text="ти щось робив?")
        self.fire_timers()
        texts = [s[1] for s in CLIENT.sent]
        self.assertEqual(len(texts), 2)
        self.assertTrue(texts[0].endswith("не\nзавтра"))
        self.assertNotIn("не завтра", " ".join(texts))

    def test_merged_short_lines_are_not_a_long_sentence(self):
        self.p.settings["max_parts"] = "2"
        line = " ".join(["слово"] * 11)
        CLIENT.ai_result = lambda m, **kw: "\n".join([line] * 4)
        self.incoming(text="розкажи")
        self.fire_timers()
        self.assertEqual(len(CLIENT.ai_calls), 1)   # no retry for 'long': every line is a short sentence
        self.assertEqual(len(CLIENT.sent), 2)


class TestMaxPartsHardLimit(Base):
    def setUp(self):
        super().setUp()
        self.enable()
        self.p.settings.update(human_timing=True, split2_pct="100", owner_active="0")

    def test_one_part_stays_one_message_in_live_timing(self):
        self.p.settings["max_parts"] = "1"
        CLIENT.ai_result = lambda m, **kw: "Сьогодні я вдома цілий день. Завтра поїду до мами на дачу."
        self.incoming(text="що робиш")
        self.fire_timers()
        self.assertEqual(len(CLIENT.sent), 1)

    def test_two_parts_allowed_still_split(self):
        self.p.settings["max_parts"] = "2"
        CLIENT.ai_result = lambda m, **kw: "Сьогодні я вдома цілий день. Завтра поїду до мами на дачу."
        self.incoming(text="що робиш")
        self.fire_timers()
        self.assertEqual(len(CLIENT.sent), 2)


if __name__ == "__main__":
    import unittest
    unittest.main()
