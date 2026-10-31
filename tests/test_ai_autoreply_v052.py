"""0.5.1 tests: the owner answered in the middle of a batch -> the bot takes his message into account.

Run: python -m unittest discover -s tests -v
"""
import unittest

from test_ai_autoreply import CLIENT, DID, mod
from test_ai_autoreply_v036 import LiveBase


class TestOwnerAnsweredFirst(LiveBase):
    def row(self, mid, out, text):
        return {"id": mid, "from_id": 0 if out else 7, "out": out, "date": int(self.clock[0]), "text": text,
                "is_service": False}

    def test_only_newer_messages_are_answered(self):
        self.enable()
        self.p.handle_incoming(0, self.msg(text=u"де ти був вчора", mid=101))
        self.clock[0] += 1
        self.p.handle_incoming(0, self.msg(text=u"вдома, спав", out=True, mid=102))
        self.clock[0] += 1
        self.p.handle_incoming(0, self.msg(text=u"а сьогодні що робиш", mid=103))
        CLIENT.history[:] = [self.row(101, False, u"де ти був вчора"), self.row(102, True, u"вдома, спав"),
                             self.row(103, False, u"а сьогодні що робиш")]
        self.fire_timers()
        self.assertEqual(len(CLIENT.sent), 1)
        ctx = CLIENT.ai_calls[0]["messages"]
        texts = [m["content"] for m in ctx]
        self.assertIn(u"вдома, спав", texts)                       # his message is part of the conversation
        self.assertEqual(texts[-1], u"а сьогодні що робиш")        # only the open message is answered
        self.assertIn("owner_replied_partial", self.p.decisions_text().replace(" ", "_"))
        self.assertIn(101, self.p._state(self.key()).answered)
        self.assertIn(u"already answered their earlier messages", CLIENT.ai_calls[0]["system"])

    def test_everything_answered_by_owner_stays_silent(self):
        self.enable()
        self.p.handle_incoming(0, self.msg(text=u"глянь це", mid=201))
        self.clock[0] += 1
        self.p.handle_incoming(0, self.msg(text=u"вже відписав сам", out=True, mid=202))
        CLIENT.history[:] = [self.row(201, False, u"глянь це"), self.row(202, True, u"вже відписав сам")]
        self.fire_timers()
        self.assertEqual(CLIENT.sent, [])
        self.assertIn("owner_replied", self.p.decisions_text().replace(" ", "_"))


if __name__ == "__main__":
    unittest.main()
