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


class Rng(object):
    """random() from a list, then 0.99; choice/randint take the first option."""
    def __init__(self, seq=()):
        self.seq = list(seq)

    def random(self):
        return self.seq.pop(0) if self.seq else 0.99

    def choice(self, xs):
        return xs[0]

    def randint(self, a, b):
        return a + 2 if a + 2 <= b else a

    def uniform(self, a, b):
        return a


class TestCommasAndTypos(unittest.TestCase):
    def test_commas(self):
        self.assertEqual(mod.drop_commas(u"ну да, слушай, давай", 30, Rng([0.1, 0.9])), u"ну да слушай, давай")
        self.assertEqual(mod.drop_commas(u"ну да, слушай", 0, Rng([0.0])), u"ну да, слушай")
        self.assertEqual(mod.drop_commas(u"было 1,5 литра", 100, Rng([0.0])), u"было 1,5 литра")
        self.assertEqual(mod.drop_commas(u"глянь https://a.b/x, ок", 100, Rng([0.0])), u"глянь https://a.b/x, ок")

    def test_typo_drops_a_middle_letter(self):
        out = mod.add_typo(u"иду в магазин", 100, Rng([0.0, 0.1]))
        self.assertEqual(out, u"иду в магзин")

    def test_typo_keeps_first_and_last_letter_and_short_words(self):
        for op in (0.1, 0.6, 0.9):
            out = mod.add_typo(u"магазин", 100, Rng([0.0, op]))
            self.assertNotEqual(out, u"магазин")
            self.assertEqual(out[0], u"м")
            self.assertEqual(out[-1], u"н")
        self.assertEqual(mod.add_typo(u"да ок, иду", 100, Rng([0.0, 0.1])), u"да ок, иду")
        self.assertEqual(mod.add_typo(u"@username", 100, Rng([0.0, 0.1])), u"@username")

    def test_typo_chance(self):
        self.assertEqual(mod.add_typo(u"магазин", 0, Rng([0.0])), u"магазин")
        self.assertEqual(mod.add_typo(u"магазин", 5, Rng([0.06])), u"магазин")

    def test_settings_on_the_style_page(self):
        toks = mod.Plugin.PAGES["style"].split()
        self.assertIn("comma_skip", toks)
        self.assertIn("typo_pct", toks)
        self.assertLessEqual(len(toks), 14)
        self.assertEqual(mod.COMMA_STEPS[mod.COMMA_DEFAULT], 30)
        self.assertEqual(mod.TYPO_STEPS[0], 0)


class TestRoughenInChat(Log):
    def test_default_drops_some_commas_after_the_ai(self):
        self.p.settings.pop("comma_skip", None)
        self.p._rng = Rng([0.1] * 50)
        CLIENT.ai_result = lambda m, **kw: u"да, слушай, давай"
        self.incoming(text=u"идём?")
        self.fire_timers()
        sent = [x[1] for x in CLIENT.sent if x[0] == DID]
        self.assertTrue(sent)
        self.assertNotIn(",", "".join(sent))
        self.assertIn(u"typos", "\n".join(c["system"] for c in CLIENT.ai_calls))   # the prompt still says no typos


if __name__ == "__main__":
    unittest.main()
