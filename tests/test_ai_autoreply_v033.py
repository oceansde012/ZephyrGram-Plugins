"""0.3.3 tests: the .ai command works with the params the real input field sends; every attempt is logged;
fallback for outgoing '.ai' that reached the chat; chat menu item.

Run: python -m unittest discover -s tests -v
"""
import unittest

from test_ai_autoreply import Base, CLIENT, DID, mod, own_history


class RealParams(object):
    """What ChatActivityEnterView builds for plain text: animation data, entities, no media."""
    def __init__(self, message, peer=DID):
        self.message, self.peer = message, peer
        self.sendAnimationData = object()
        self.mediaWebPage = object()
        self.entities = []
        self.replyToMsg = None
        self.photo = self.document = self.location = self.poll = self.game = None
        self.invoice = self.user = self.todo = self.retryMessageObject = None
        self.videoEditedInfo = self.richMessage = None
        self.path = None


class TestV033(Base):
    def setUp(self):
        Base.setUp(self)
        self.enable()
        CLIENT.history[:] = own_history()
        CLIENT.ai_result = lambda m, **kw: "та норм, ти як"
        self.p.settings["typing_delay"] = False

    def hook(self, text, peer=DID):
        return self.p.on_send_message_hook(0, RealParams(text, peer))

    def test_real_input_field_params_are_intercepted(self):
        res = self.hook(".ai")
        self.assertIsNotNone(res)
        self.assertEqual(res.strategy, 1)
        self.assertEqual(len(CLIENT.sent), 1)

    def test_attachment_is_ignored_and_logged(self):
        pr = RealParams(".ai")
        pr.document = object()
        self.assertIsNone(self.p.on_send_message_hook(0, pr))
        self.assertIn("command_ignored_media", self.p.decisions_text())

    def test_disabled_and_not_listed_are_logged(self):
        self.p.settings["cmd_enable"] = False
        self.assertIsNone(self.hook(".ai"))
        self.assertIn("command_disabled", self.p.decisions_text())
        self.p.settings["cmd_enable"] = True
        self.assertIsNone(self.hook(".ai", 555))
        self.assertIn("chat_not_listed", self.p.decisions_text())

    def test_plain_text_is_not_logged(self):
        self.assertIsNone(self.hook("привіт"))
        self.assertNotIn("command", self.p.decisions_text())

    def test_outgoing_fallback_runs_command_once(self):
        self.incoming(text=".ai", out=True)
        self.assertEqual(len(CLIENT.sent), 1)
        self.assertIn("owner_command_hook_missed", self.p.decisions_text())
        self.incoming(text=".ai", out=True)                       # within 30 s: not repeated
        self.assertEqual(len(CLIENT.sent), 1)

    def test_outgoing_fallback_skipped_when_hook_saw_it(self):
        self.hook(".ai")
        n = len(CLIENT.sent)
        self.incoming(text=".ai", out=True)
        self.assertEqual(len(CLIENT.sent), n)

    def test_outgoing_normal_text_unaffected(self):
        self.incoming(text="привіт", out=True)
        self.assertEqual(CLIENT.sent, [])

    def test_menu_item(self):
        ctx = {"account": 0, "dialog_id": DID}
        self.assertTrue(self.p.cond_show_cmd(ctx))
        self.assertFalse(self.p.cond_show_cmd({"account": 0, "dialog_id": 999}))
        self.p.on_cmd_click(ctx)
        self.assertEqual(len(CLIENT.sent), 1)
        self.assertIn("owner_command", self.p.decisions_text())


if __name__ == "__main__":
    unittest.main()
