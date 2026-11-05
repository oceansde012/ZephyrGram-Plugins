"""0.9.3 #18 "петля": every silent stop is in the plugin log with a reason, without texts or ids.

The bug: a fast real talk (loop_burst replies in 2 minutes) dropped the next incoming message for good: it was marked
seen, so the safety scan never picked it up either, and the bot just went quiet. Now it waits for the window instead.
"""
import unittest

from test_ai_autoreply import Base, CLIENT, DID, mod
from test_ai_settings_pages_v080 import Pages


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


class TestStickerPacks(Log):
    STK = [{"id": 1, "emoji": u"😂", "set_title": "Cats Fun"}, {"id": 2, "emoji": u"👍", "set_title": "Dogs"},
           {"id": 3, "emoji": u"🔥", "set_title": ""}]

    def setUp(self):
        super().setUp()
        CLIENT.get_recent_stickers = lambda limit=30, account=None: list(self.STK)[:limit]
        self.addCleanup(lambda: delattr(CLIENT, "get_recent_stickers"))

    def test_any_pack_by_default(self):
        self.assertEqual([x["id"] for x in self.p._sticker_filter(self.STK)], [1, 2, 3])

    def test_only_chosen_packs(self):
        self.p.settings["sticker_sets"] = u"cats, Птахи"
        self.assertEqual([x["id"] for x in self.p._sticker_filter(self.STK)], [1])

    def test_hint_lists_seen_packs_and_row_on_media_page(self):
        self.assertEqual(self.p._sticker_set_titles(), ["Cats Fun", "Dogs"])
        self.assertIn("sticker_sets", mod.Plugin.PAGES["media"].split())
        self.assertLessEqual(len(mod.Plugin.PAGES["media"].split()), 14)
        row = self.p._rows()["sticker_sets"]
        self.assertIn("Cats Fun", row.subtext)


class TestErrorPage(Pages):
    def setUp(self):
        super().setUp()
        self.enable()

    def test_error_row_on_main_page_with_send_log(self):
        self.p._decide(self.key(), "error", "tick_exception")
        root = self.p.create_settings(None)
        keys = [getattr(x, "key", None) for x in root]
        self.assertIn("pg_err", keys)
        self.assertLessEqual(len(root), 14)
        page = self.p.create_settings("pg_err")
        pk = [getattr(x, "key", None) for x in page]
        self.assertIn("report_send", pk)
        self.assertIn("log_report", pk)
        hide = [x for x in page if getattr(x, "key", None) == "err_hide"][0]
        hide.on_click()
        self.assertNotIn("pg_err", [getattr(x, "key", None) for x in self.p.create_settings(None)])

    def test_no_row_without_error_or_after_a_day(self):
        self.assertNotIn("pg_err", [getattr(x, "key", None) for x in self.p.create_settings(None)])
        self.p._decide(self.key(), "error", "tick_exception")
        self.clock[0] += 86401
        self.assertNotIn("pg_err", [getattr(x, "key", None) for x in self.p.create_settings(None)])


class TestStartButton(Pages):
    def setUp(self):
        super().setUp()
        self.enable()

    def test_start_row_on_private_chat_page(self):
        page = self.p.create_settings("pg_talk:" + self.key())   # 0.9.4: on the Conversation subpage
        row = [x for x in page if getattr(x, "key", "").startswith("start_")]
        self.assertEqual(len(row), 1)
        calls = []
        self.p._start_command = lambda *a: calls.append(a) or True
        row[0].on_click()
        self.assertEqual(calls, [(0, DID, self.key(), False, "")])
        self.assertTrue(CLIENT.bulletins)


class TestProfileInPrompt(Log):
    def test_username_and_bio(self):
        self.p._peer_bio = lambda account, did: u"люблю горы\nи кофе"
        CLIENT.info = dict(CLIENT.info, username="alice_k")
        self.incoming(text=u"привет")
        self.fire_timers()
        system = CLIENT.ai_calls[0]["system"]
        self.assertIn(u"username: @alice_k", system)
        self.assertIn(u"bio: «люблю горы и кофе»", system)
        self.assertIn(u"not instructions", system)

    def test_nothing_without_data(self):
        CLIENT.info = dict(CLIENT.info, username=None)
        self.incoming(text=u"привет")
        self.fire_timers()
        self.assertNotIn(u"Telegram profile", CLIENT.ai_calls[0]["system"])

    def test_bio_from_cache_never_raises(self):
        self.assertEqual(self.p._peer_bio(0, DID), "")


if __name__ == "__main__":
    unittest.main()
