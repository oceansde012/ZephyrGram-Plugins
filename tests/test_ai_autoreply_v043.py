"""0.4.3: '.ai start' adds the chat and greets; the bot never copies earlier messages."""
from test_ai_autoreply import Base, CLIENT, DID, mod


class TestStart(Base):
    def run_start(self, text=".ai start"):
        res = self.p.on_send_message_hook(0, type("P", (), {"message": text, "peer": DID})())
        return res

    def test_parse(self):
        for word in ("start", "старт", "welcome", "привітання", "приветствие"):
            self.assertEqual(self.p.parse_admin(".ai " + word), ("start", ""), word)
        self.assertIsNone(self.p.parse_admin(".ai start now"))

    def test_start_adds_chat_and_writes_first_message(self):
        CLIENT.ai_result = lambda m, **kw: "здоров, як воно"
        res = self.run_start()
        self.assertEqual(res.strategy, 1)                      # the command itself is not sent
        self.assertTrue(self.p.is_enabled(self.key()))
        self.assertEqual(self.p._chat_mode(self.key()), mod.MODE_AUTO)
        self.assertEqual(len(CLIENT.sent), 1)
        self.assertTrue(CLIENT.sent[0][1].endswith("здоров, як воно"))

    def test_start_in_ongoing_chat_uses_the_history_and_does_not_copy_it(self):
        now = int(self.clock[0])
        CLIENT.history[:] = [{"id": 1, "out": True, "date": now - 60, "text": "привіт, як справи сьогодні",
                              "dialog_id": DID}]
        answers = ["привіт, як справи сьогодні", "до речі, ти вже бачила новий патч?"]
        CLIENT.ai_result = lambda m, **kw: answers.pop(0)
        self.run_start()
        self.assertEqual(len(CLIENT.sent), 1)
        self.assertTrue(CLIENT.sent[0][1].endswith("до речі, ти вже бачила новий патч?"))
        self.assertEqual(len(CLIENT.ai_calls), 2)
        self.assertIn("Do not repeat", CLIENT.ai_calls[1]["system"])

    def test_start_refused_in_groups_and_bots(self):
        CLIENT.info = {"id": -5, "title": "G", "type": "group", "is_bot": False}
        self.run_start()
        self.assertFalse(self.p.is_enabled(self.p.chat_key(0, DID)))
        self.assertEqual(CLIENT.sent, [])


class TestNoCopy(Base):
    def setUp(self):
        super().setUp()
        self.enable()
        self.p.settings["owner_active"] = "0"

    def test_reply_that_copies_their_message_is_retried(self):
        answers = ["ну що там у тебе нового", "та нормально все, працюю"]
        CLIENT.ai_result = lambda m, **kw: answers.pop(0)
        self.incoming(text="ну що там у тебе нового")
        self.fire_timers()
        self.assertEqual(len(CLIENT.ai_calls), 2)
        self.assertTrue(CLIENT.sent[-1][1].endswith("та нормально все, працюю"))

    def test_only_copies_are_not_sent(self):
        CLIENT.ai_result = lambda m, **kw: "ну що там у тебе нового"
        self.incoming(text="ну що там у тебе нового")
        self.fire_timers()
        self.assertEqual(CLIENT.sent, [])

    def test_short_answers_are_not_treated_as_copies(self):
        CLIENT.ai_result = lambda m, **kw: "ти де"
        self.incoming(text="ти де")
        self.fire_timers()
        self.assertEqual(len(CLIENT.sent), 1)
