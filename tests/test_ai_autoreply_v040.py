"""0.4.0: reply to everyone, links, short messages, reviving a quiet chat, no stopping on late messages."""
from test_ai_autoreply import Base, CLIENT, DID, mod


class TestLinks(Base):
    def setUp(self):
        super().setUp()
        self.enable()

    def test_link_message_is_not_answered(self):
        for text in ("глянь https://example.com/x", "www.site.org", "t.me/abc", "тут site.com є"):
            self.assertEqual(self.incoming(text=text), "link", text)
        self.fire_timers()
        self.assertEqual(CLIENT.sent, [])

    def test_plain_text_is_answered(self):
        self.assertIsNone(self.incoming(text="привіт, як ти"))
        self.fire_timers()
        self.assertEqual(len(CLIENT.sent), 1)

    def test_switch_off_answers_links(self):
        self.p.settings["skip_links"] = False
        self.assertIsNone(self.incoming(text="глянь https://example.com"))


class TestReplyAll(Base):
    def test_off_by_default(self):
        self.assertIsNone(self.incoming(text="привіт"))
        self.assertFalse(self.p.is_enabled(self.key()))

    def test_new_private_chat_is_added_and_answered(self):
        self.p.settings["reply_all"] = True
        self.assertIsNone(self.incoming(text="привіт"))
        self.assertTrue(self.p.is_enabled(self.key()))
        self.assertEqual(self.p._chats[self.key()]["type"], "user")
        self.fire_timers()
        self.assertEqual(len(CLIENT.sent), 1)

    def test_bots_groups_and_channels_are_never_added(self):
        self.p.settings["reply_all"] = True
        CLIENT.info = {"id": DID, "title": "Bot", "type": "user", "is_bot": True}
        self.incoming(text="hi")
        self.assertFalse(self.p.is_enabled(self.key()))
        CLIENT.info = {"id": -5, "title": "G", "type": "group", "is_bot": False}
        self.p.handle_incoming(0, self.msg(text="hi", did=-5))
        self.assertFalse(self.p.is_enabled(self.p.chat_key(0, -5)))
        self.p.handle_incoming(0, self.msg(text="hi", is_bot=True, mid=900))
        self.assertFalse(self.p.is_enabled(self.key()))

    def test_paused_and_removed_chats_stay_as_left(self):
        self.p.settings["reply_all"] = True
        self.enable()
        self.p.chat_off(self.key(), remove=False)
        self.incoming(text="привіт")
        self.assertFalse(self.p.is_enabled(self.key()))
        self.p.chat_off(self.key(), remove=True)
        self.incoming(text="ще раз")
        self.assertNotIn(self.key(), self.p._read_chats())

    def test_explicit_add_after_removal_works(self):
        self.p.settings["reply_all"] = True
        self.enable()
        self.p.chat_off(self.key(), remove=True)
        self.enable()
        self.assertTrue(self.p.is_enabled(self.key()))

    def test_account_filter(self):
        self.p.settings["reply_all"] = True
        self.p.settings["all_accounts"] = "2"          # 1-based: only the second account
        self.p.handle_incoming(0, self.msg(text="hi"))
        self.assertFalse(self.p.is_enabled(self.p.chat_key(0, DID)))
        self.p.handle_incoming(1, self.msg(text="hi", mid=50))
        self.assertTrue(self.p.is_enabled(self.p.chat_key(1, DID)))


class TestShortMessages(Base):
    def setUp(self):
        super().setUp()
        self.enable()

    def test_prompt_asks_for_short_messages(self):
        self.incoming(text="що там")
        self.fire_timers()
        self.assertIn("SHORT separate chat messages", CLIENT.ai_calls[0]["system"])

    def test_lines_become_separate_messages(self):
        CLIENT.ai_result = lambda m, **kw: "не\nзавтра\nне встиг ще"
        self.incoming(text="ти щось робив?")
        self.fire_timers()
        texts = [s[1] for s in CLIENT.sent]
        self.assertEqual(len(texts), 3)
        self.assertTrue(texts[0].endswith("не") and texts[1] == "завтра" and texts[2] == "не встиг ще")

    def test_one_run_on_sentence_is_retried(self):
        long = " ".join(["слово"] * 30) + "."
        answers = [long, "ок\nзараз гляну"]
        CLIENT.ai_result = lambda m, **kw: answers.pop(0)
        self.incoming(text="ти де")
        self.fire_timers()
        self.assertEqual(len(CLIENT.ai_calls), 2)
        self.assertIn("short messages", CLIENT.ai_calls[1]["system"].lower())
        self.assertEqual(len(CLIENT.sent), 2)

    def test_max_parts(self):
        self.p.settings["max_parts"] = "2"
        CLIENT.ai_result = lambda m, **kw: "а\nб\nв\nг"
        self.incoming(text="x1")
        self.fire_timers()
        self.assertEqual(len(CLIENT.sent), 2)

    def test_switch_off_keeps_old_behaviour(self):
        self.p.settings["short_msgs"] = False
        CLIENT.ai_result = lambda m, **kw: "не\nзавтра"
        self.incoming(text="x2")
        self.fire_timers()
        self.assertNotIn("SHORT separate", CLIENT.ai_calls[0]["system"])


class TestLateMessageDoesNotStopChat(Base):
    def setUp(self):
        super().setUp()
        self.enable()

    def test_their_message_dated_before_our_last_part_is_answered(self):
        now = int(self.clock[0])
        self.p._remember_bot_text("перша частина")
        self.p._remember_bot_text("друга частина")
        CLIENT.history[:] = [
            {"id": 1, "out": False, "date": now - 30, "text": "привіт", "dialog_id": DID, "from_id": 7},
            {"id": 3, "out": True, "date": now - 2, "text": "перша частина", "dialog_id": DID},
            {"id": 4, "out": True, "date": now - 1, "text": "друга частина", "dialog_id": DID},
            {"id": 2, "out": False, "date": now - 3, "text": "а ще питання", "dialog_id": DID, "from_id": 7},
        ]
        self.p.settings["owner_active"] = "0"
        self.incoming(text="а ще питання", mid=2)
        self.fire_timers()
        self.assertEqual(len(CLIENT.sent), 1)

    def test_owner_message_after_theirs_still_silences_the_bot(self):
        now = int(self.clock[0])
        CLIENT.history[:] = [
            {"id": 1, "out": False, "date": now - 30, "text": "привіт", "dialog_id": DID, "from_id": 7},
            {"id": 5, "out": True, "date": now - 1, "text": "відповів сам", "dialog_id": DID},
        ]
        self.p.settings["owner_active"] = "0"
        self.incoming(text="привіт", mid=1)
        self.fire_timers()
        self.assertEqual(CLIENT.sent, [])


class TestRevive(Base):
    def setUp(self):
        super().setUp()
        self.enable()
        self.p.settings.update(revive=True, owner_active="0")
        self.now = int(self.clock[0])

    def history(self, last_out_age=1800, extra=()):
        n = self.now
        CLIENT.history[:] = [
            {"id": 1, "out": False, "date": n - last_out_age - 600, "text": "ну привіт", "dialog_id": DID, "from_id": 7},
            {"id": 2, "out": True, "date": n - last_out_age - 500, "text": "здоров", "dialog_id": DID},
            {"id": 3, "out": False, "date": n - last_out_age - 400, "text": "як справи", "dialog_id": DID, "from_id": 7},
            {"id": 4, "out": True, "date": n - last_out_age, "text": "нормально", "dialog_id": DID},
        ] + list(extra)

    def run_pass(self):
        n = self.p._revive_pass()
        self.fire_timers()
        return n

    def test_quiet_chat_gets_a_new_topic(self):
        self.history()
        CLIENT.ai_result = lambda m, **kw: "до речі\nа ти дивився новий сезон?"
        self.assertEqual(self.run_pass(), 1)
        self.assertEqual(len(CLIENT.sent), 2)
        self.assertIn("not answered for a while", CLIENT.ai_calls[-1]["messages"][-1]["content"])

    def test_off_by_default_and_not_too_soon_or_too_old(self):
        self.history()
        self.p.settings["revive"] = False
        self.assertEqual(self.run_pass(), 0)
        self.p.settings["revive"] = True
        self.history(last_out_age=60)
        self.assertEqual(self.run_pass(), 0)
        self.p._state(self.key()).revive_chk = 0
        self.history(last_out_age=5 * 3600)
        self.assertEqual(self.run_pass(), 0)
        self.assertEqual(CLIENT.sent, [])

    def test_their_turn_is_left_to_the_normal_path(self):
        self.history(extra=[{"id": 9, "out": False, "date": self.now - 1500, "text": "ало", "dialog_id": DID, "from_id": 7}])
        self.assertEqual(self.run_pass(), 0)

    def test_only_once_per_silence(self):
        self.history()
        self.assertEqual(self.run_pass(), 1)
        self.clock[0] += 400
        self.p._state(self.key()).revive_chk = 0
        self.now = int(self.clock[0])
        self.history()
        self.assertEqual(self.run_pass(), 0)           # they never answered the revival

    def test_groups_and_non_auto_modes_are_skipped(self):
        self.history()
        self.p.set_setting("mode_" + self.p._sk(self.key()), 1)
        self.assertEqual(self.run_pass(), 0)

    def test_needs_a_real_conversation(self):
        n = self.now
        CLIENT.history[:] = [{"id": 4, "out": True, "date": n - 1800, "text": "ку", "dialog_id": DID}]
        self.assertEqual(self.run_pass(), 0)
