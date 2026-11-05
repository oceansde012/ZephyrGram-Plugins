"""0.9.3 #18 "петля": every silent stop is in the plugin log with a reason, without texts or ids.

The bug: a fast real talk (loop_burst replies in 2 minutes) dropped the next incoming message for good: it was marked
seen, so the safety scan never picked it up either, and the bot just went quiet. Now it waits for the window instead.
"""
import unittest

from test_ai_autoreply import Base, CLIENT, DID, mod


class Log(Base):
    def setUp(self):
        super().setUp()
        self.enable()
        self.p.settings.update(disclosure=False, owner_active="0", human_timing=False, loop_burst="4")
        orig = mod.time.sleep
        mod.time.sleep = lambda s: None
        self.addCleanup(setattr, mod.time, "sleep", orig)
        CLIENT.ai_result = lambda m, **kw: u"ага"

    def st(self):
        return self.p._state(self.key())

    def decisions(self):
        return [l for l in self.p.logs if l.startswith("decision ")]


class TestBurstHold(Log):
    def burst(self):
        for _ in range(4):
            self.st().replies.append(self.clock[0] - 10)

    def test_burst_message_is_answered_later(self):
        self.burst()
        n = len(CLIENT.sent)
        self.assertIsNone(self.incoming(text=u"а ты где?"))
        self.assertTrue(any("reply_burst_hold" in l for l in self.decisions()))
        self.fire_timers()
        self.assertGreater(len(CLIENT.sent), n)
        self.assertTrue(self.clock[0] >= self.st().replies[0] + 0)

    def test_waits_until_the_window_frees(self):
        self.burst()
        start = self.clock[0]
        self.incoming(text=u"а ты где?")
        self.assertGreaterEqual(self.st().cooldown_until, start - 10 + mod.LOOP_BURST_SEC)

    def test_below_the_limit_no_hold(self):
        self.st().replies.append(self.clock[0] - 10)
        self.incoming(text=u"привет")
        self.assertFalse(any("reply_burst_hold" in l for l in self.decisions()))

    def test_identical_repeats_while_answering_still_count_as_a_loop(self):
        for _ in range(3):
            self.st().replies.append(self.clock[0] - 10)
        self.p.settings["loop_burst"] = "50"
        self.incoming(text="ping")
        self.incoming(text="ping")
        self.assertEqual(self.incoming(text="ping"), "repeated identical text")
        self.assertTrue(any("repeated_identical_text" in l for l in self.decisions()))


class TestLogHasNoIds(Log):
    def test_decision_lines_use_a_chat_tag(self):
        self.incoming(text=u"секретный текст")
        self.fire_timers()
        lines = self.decisions()
        self.assertTrue(lines)
        tag = self.p._ltag(self.key())
        for l in self.p.logs:
            self.assertNotIn(self.key(), l)
            self.assertNotIn(str(DID), l.replace(tag, ""))
            self.assertNotIn(u"секретный", l)
        self.assertTrue(all(tag in l for l in lines if "chat#" in l))
        self.assertEqual(tag, self.p._ltag(self.key()))
        self.assertNotEqual(tag, self.p._ltag("0:43"))

    def test_caps_and_cooldowns_logged(self):
        self.p.settings["daily_cap"] = "1"
        self.incoming(text=u"раз")
        self.fire_timers()
        self.clock[0] += 3600
        self.incoming(text=u"два")
        self.fire_timers()
        self.assertTrue(any("daily_cap_reached" in l for l in self.decisions()))

    def test_waiting_owner_is_logged(self):
        st = self.st()
        st.ask = {"n": 1}
        st.pending.append((1, 7, u"ау"))
        self.p.tick(self.key())
        self.assertTrue(any("waiting_owner_answer" in l for l in self.decisions()))
        self.assertTrue(st.pending)
        st.ask = None


class TestNewCodesHaveReasons(unittest.TestCase):
    def test_codes(self):
        for c in ("reply_burst_hold", "group_cooldown", "waiting_owner_answer"):
            self.assertIn(c, mod.R)


if __name__ == "__main__":
    unittest.main()
