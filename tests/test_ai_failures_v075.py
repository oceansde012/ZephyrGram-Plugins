"""0.7.5: a slow or unreachable AI server never switches a chat off; the real reason is written to the journal;
a failed second try keeps the first reply. Fake Zephyr, no network."""
from test_ai_autoreply import Base, CLIENT, mod


class FakeAiError(RuntimeError):
    def __init__(self, message, code=0):
        super().__init__(message)
        self.code = code


class TestTransientFailures(Base):
    def setUp(self):
        super().setUp()
        self.enable()
        self.p.settings["owner_active"] = "0"
        self.p.settings["cooldown"] = "0"

    def round(self, text):
        self.incoming(text=text)
        self.fire_timers()

    def test_timeouts_never_disable_the_chat(self):
        CLIENT.ai_result = lambda m, **kw: FakeAiError("timeout", 5)
        for i in range(mod.MAX_FAILURES + 3):
            self.round("m%d" % i)
        self.assertEqual(CLIENT.sent, [])
        self.assertTrue(self.p.is_enabled(self.key()))

    def test_misconfiguration_still_disables(self):
        CLIENT.ai_result = lambda m, **kw: FakeAiError("no server", 1)
        for i in range(mod.MAX_FAILURES):
            self.round("m%d" % i)
        self.assertFalse(self.p.is_enabled(self.key()))

    def test_journal_shows_code_and_seconds(self):
        CLIENT.ai_result = lambda m, **kw: FakeAiError("timeout", 5)
        self.round("привіт, ти тут?")
        reasons = [d.get("r") for d in self.p._decisions]
        self.assertTrue(any(r.startswith("ai_err_5_") for r in reasons), reasons)
        text = mod.reason_text("ru", [r for r in reasons if r.startswith("ai_err_5_")][0])
        self.assertIn("нет ответа вовремя", text)

    def test_failed_second_try_keeps_the_first_reply(self):
        answers = [u'ну ок давай "" not possible in tool', FakeAiError("timeout", 5)]
        CLIENT.ai_result = lambda m, **kw: answers.pop(0) if answers else "ага"
        self.round("привіт, ти тут?")
        self.assertEqual(len(CLIENT.sent), 1)
        self.assertNotIn("tool", CLIENT.sent[0][1])


if __name__ == "__main__":
    import unittest
    unittest.main()
