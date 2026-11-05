"""0.9.2: optional conversation plan per chat (#48). Fake Zephyr, no network, no real AI calls.

One line of the plan per day of talk. The current stage goes into the prompt as a soft rule (no extra AI call);
it moves forward on the next day of talk, or earlier when the person already talks about a later stage, never back.
"""
import unittest

from test_ai_autoreply import Base, CLIENT, mod

PLAN = u"""День 1: знакомство, откуда человек и чем занимается
День 2: общие интересы, музыка и фильмы
День 3: путешествия, поездки и отпуск"""


class TestParsing(unittest.TestCase):
    def test_stages(self):
        self.assertEqual(mod.plan_stages(PLAN), [u"знакомство, откуда человек и чем занимается",
                                                 u"общие интересы, музыка и фильмы", u"путешествия, поездки и отпуск"])
        self.assertEqual(mod.plan_stages(u"1. привет\n\n2) кино\nDay 3 - travel"), [u"привет", u"кино", u"travel"])
        self.assertEqual(mod.plan_stages(u"  \n"), [])

    def test_jump_needs_the_topic(self):
        st = mod.plan_stages(PLAN)
        self.assertEqual(mod.plan_jump(st, 0, u"как дела?"), 0)
        self.assertEqual(mod.plan_jump(st, 0, u"летом была поездка на море, такой отпуск классный"), 2)
        self.assertEqual(mod.plan_jump(st, 0, u"слушаю музыку, смотрю фильмы"), 1)
        self.assertEqual(mod.plan_jump(st, 2, u"слушаю музыку, смотрю фильмы"), 2)   # never back


class Chat(Base):
    def setUp(self):
        super().setUp()
        self.enable()
        self.p.settings.update(disclosure=False, owner_active="0")
        self.sk = self.p._sk(self.key())
        self.p.settings["plan_" + self.sk] = PLAN

    def system(self, text=u"привет", reply=u"привет"):
        CLIENT.ai_result = lambda m, **kw: reply
        n = len(CLIENT.ai_calls)
        self.clock[0] += 3600
        self.incoming(text=text)
        self.fire_timers()
        return CLIENT.ai_calls[n]["system"]

    def stage(self):
        return self.p._chats[self.key()].get("plan_i")

    def next_day(self):
        self.clock[0] += 24 * 3600


class TestPlanInChat(Chat):
    def test_first_stage_in_prompt(self):
        s = self.system()
        self.assertIn(u"stage 1 of 3: знакомство", s)
        self.assertIn(u"never force it", s)
        self.assertEqual(self.stage(), 0)

    def test_same_day_keeps_the_stage(self):
        self.system()
        self.assertIn(u"stage 1 of 3", self.system(u"как дела?"))

    def test_next_day_of_talk_moves_on(self):
        self.system()
        self.next_day()
        self.assertIn(u"stage 2 of 3", self.system())
        self.next_day()
        self.next_day()                                   # a pause of days counts as one more day of talk
        self.assertIn(u"stage 3 of 3", self.system())
        self.next_day()
        self.assertIn(u"stage 3 of 3", self.system())     # stays on the last stage

    def test_person_jumps_ahead(self):
        self.system()
        s = self.system(u"кстати, планирую поездку, хочу в отпуск в горы")
        self.assertIn(u"stage 3 of 3: путешествия", s)
        self.next_day()
        self.assertIn(u"stage 3 of 3", self.system(u"привет"))   # never back

    def test_changed_plan_starts_over(self):
        self.system()
        self.next_day()
        self.system()
        self.assertEqual(self.stage(), 1)
        self.p.settings["plan_" + self.sk] = u"знакомство\nспорт"
        self.assertIn(u"stage 1 of 2: знакомство", self.system())

    def test_no_plan_no_rule(self):
        self.p.settings["plan_" + self.sk] = ""
        self.assertNotIn(u"conversation plan", self.system())

    def test_no_extra_ai_call(self):
        n = len(CLIENT.ai_calls)
        self.system()
        self.assertEqual(len(CLIENT.ai_calls), n + 1)

    def test_short_reply_rules_still_apply(self):
        s = self.system()
        self.assertIn(mod.MIRROR_RULE, s)
        self.assertIn(u"Short replies as usual", s)


class TestPlanSettings(Chat):
    def test_row_on_the_lore_page_with_stage(self):
        self.assertIn("plan_{}", mod.Plugin.PAGES["lore"].split())
        self.assertLessEqual(len(mod.Plugin.PAGES["lore"].split()), 14)
        self.system()
        self.next_day()
        self.system()
        rows = self.p._rows(self.key())
        self.assertIn("plan_" + self.sk, rows)
        self.assertIn("2 / 3", rows["plan_" + self.sk].subtext)

    def test_removing_the_chat_clears_the_plan(self):
        self.p.chat_off(self.key(), remove=True)
        self.assertIsNone(self.p.settings.get("plan_" + self.sk))


if __name__ == "__main__":
    unittest.main()
