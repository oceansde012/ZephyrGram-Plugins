"""0.9.4: Conversation subpage of a chat: "How to talk from now on" (#11, a temporary rule for N days), "Study this
chat" (#12), "Write every day" (#15, one first message a day through the reviving path) and a sample chat for the
style (#13). Fake Zephyr, no network, no real AI calls."""
import time
import unittest

from test_ai_autoreply import Base, CLIENT, DID, mod
from test_ai_settings_pages_v080 import Pages


class Chat(Base):
    def setUp(self):
        super().setUp()
        self.enable()
        self.p.settings.update(disclosure=False, owner_active="0", human_timing=False)
        orig = mod.time.sleep
        mod.time.sleep = lambda s: None
        self.addCleanup(setattr, mod.time, "sleep", orig)
        self.sk = self.p._sk(self.key())
        CLIENT.ai_result = lambda m, **kw: u"ага"

    def system(self, text=u"привет"):
        n = len(CLIENT.ai_calls)
        self.clock[0] += 3600
        self.incoming(text=text)
        self.fire_timers()
        return CLIENT.ai_calls[n]["system"]


class TestVector(Chat):
    def test_rule_in_prompt_then_removed_after_its_days(self):
        self.p.settings["vector_" + self.sk] = u"больше флирта"
        self.assertIn(u"больше флирта", self.system())
        self.assertEqual(self.p._vector_left(self.key()), 3)
        self.clock[0] += 3 * 86400
        self.assertNotIn(u"больше флирта", self.system())
        self.assertEqual(self.p.settings["vector_" + self.sk], "")
        self.assertNotIn("vector_ts", self.p._chats[self.key()])

    def test_days_setting(self):
        self.p.settings["vector_" + self.sk] = u"меньше вопросов"
        self.p.settings["vector_days_" + self.sk] = 0          # 1 day
        self.assertIn(u"меньше вопросов", self.system())
        self.clock[0] += 86400
        self.assertNotIn(u"меньше вопросов", self.system())

    def test_editing_restarts_the_count(self):
        self.p.settings["vector_" + self.sk] = u"на ты"
        self.system()
        self.clock[0] += 2 * 86400
        self.p._vector_cb(self.key())(u"на вы")
        self.p.settings["vector_" + self.sk] = u"на вы"
        self.clock[0] += 2 * 86400
        self.assertIn(u"на вы", self.system())

    def test_no_rule_no_text(self):
        self.assertNotIn("asked to change how you talk", self.system())


class TestLearnNow(Chat):
    def test_studies_style_and_facts_with_progress(self):
        CLIENT.history[:] = [{"id": i, "from_id": 7 if i % 2 else 1, "out": not i % 2,
                              "date": int(self.clock[0] - 1000 + i), "text": u"сообщение номер %d про кино" % i,
                              "is_bot": False, "reply_to": None, "dialog_id": DID} for i in range(1, 21)]
        CLIENT.ai_result = lambda m, **kw: u"- любит кино\n- живёт в Киеве"
        CLIENT.bulletins[:] = []
        self.p._learn_now_cb(self.key())()
        self.assertEqual(self.p.settings["learned_" + self.sk], u"- любит кино\n- живёт в Киеве")
        self.assertEqual(CLIENT.bulletins[0], self.p.t("bl_learn_1"))
        self.assertIn(self.p.t("bl_learn_2"), CLIENT.bulletins)
        self.assertEqual(CLIENT.bulletins[-1], self.p.t("bl_learn_done", 10, 2))
        self.assertFalse(self.p._state(self.key()).learn_busy)

    def test_busy_guard(self):
        self.p._state(self.key()).learn_busy = True
        CLIENT.bulletins[:] = []
        self.p._learn_now_cb(self.key())()
        self.assertEqual(CLIENT.bulletins, [self.p.t("bl_learn_busy")])


class TestDaily(Chat):
    def setUp(self):
        super().setUp()
        self.p.settings["daily_" + self.sk] = True
        lt = time.localtime(self.clock[0])
        self.midnight = self.clock[0] - (lt.tm_hour * 3600 + lt.tm_min * 60 + lt.tm_sec)
        self.clock[0] = self.midnight + 22 * 3600 + 30 * 60      # 22:30, after the window
        self.runs = []
        self.p._revive_run = lambda key, manual=False, instr=None: self.runs.append((key, manual, instr))

    def old_talk(self):
        CLIENT.history[:] = [{"id": 1, "from_id": 7, "out": False, "date": int(self.midnight - 5000), "text": "hey",
                              "is_bot": False, "reply_to": None, "dialog_id": DID}]

    def test_once_a_day_in_the_window(self):
        self.old_talk()
        self.p._daily_pass()                                  # 22:30: today's window is over
        self.assertEqual(self.runs, [])
        self.clock[0] = self.midnight + 86400 + 21 * 3600 + 30   # next day 21:00:30, after any target
        self.p._daily_pass()
        self.fire_timers()
        self.assertEqual(len(self.runs), 1)
        self.assertTrue(self.runs[0][1])
        self.assertIs(self.runs[0][2], mod.DAILY_INSTR)
        t = self.p._chats[self.key()]["daily_t"] - (self.midnight + 86400)
        self.assertTrue(9 * 3600 <= t <= 21 * 3600)
        self.p._state(self.key()).revive_busy = False
        self.clock[0] += 1200
        self.p._daily_pass()
        self.fire_timers()
        self.assertEqual(len(self.runs), 1)                   # only once that day

    def test_not_before_the_random_time(self):
        self.old_talk()
        self.clock[0] = self.midnight + 86400 + 8 * 3600
        self.p._daily_pass()
        self.assertEqual(self.runs, [])

    def test_skips_when_you_already_talked_today(self):
        self.clock[0] = self.midnight + 86400 + 21 * 3600 + 30
        CLIENT.history[:] = [{"id": 1, "from_id": 7, "out": False, "date": int(self.clock[0] - 600), "text": "hey",
                              "is_bot": False, "reply_to": None, "dialog_id": DID}]
        self.p._daily_pass()
        self.fire_timers()
        self.assertEqual(self.runs, [])
        self.assertTrue(self.p._chats[self.key()]["daily_done"])

    def test_quiet_hours_and_limit(self):
        self.old_talk()
        self.clock[0] = self.midnight + 86400 + 21 * 3600 + 30
        self.p.settings["quiet_hours"] = "20:00-23:00"
        self.p._daily_pass()
        self.assertEqual(self.runs, [])
        self.p.settings["quiet_hours"] = ""
        self.p._revive_marks[self.key()] = [self.clock[0] - 100]
        self.p.settings["revive_daily"] = "1"
        self.p._daily_pass()
        self.assertEqual(self.runs, [])

    def test_off_by_default_and_scan_runs_for_it(self):
        self.p.settings["daily_" + self.sk] = None
        self.assertFalse(self.p._daily_any())
        self.p.settings["scan"] = False
        self.p.settings["revive"] = False
        self.assertFalse(self.p._scan_enabled())
        self.p.settings["daily_" + self.sk] = True
        self.assertTrue(self.p._scan_enabled())

    def test_daily_text_goes_through_reviving(self):
        del self.p._revive_run
        self.old_talk()
        CLIENT.history.append({"id": 2, "from_id": 1, "out": True, "date": int(self.midnight - 4000), "text": "ok",
                               "is_bot": False, "reply_to": None, "dialog_id": DID})
        CLIENT.history.append({"id": 3, "from_id": 7, "out": False, "date": int(self.midnight - 3000), "text": "bye",
                               "is_bot": False, "reply_to": None, "dialog_id": DID})
        CLIENT.ai_result = lambda m, **kw: u"доброе утро"
        self.p._revive_run(self.key(), True, mod.DAILY_INSTR)
        self.assertIn(mod.DAILY_INSTR, str(CLIENT.ai_calls[-1]["messages"]))
        self.assertTrue(CLIENT.sent)


class TestStyleSample(Chat):
    def test_sample_chat_examples_lead(self):
        other = self.p.chat_key(0, 77)
        texts = {DID: [u"привет, это мой чат номер один"] * 1, 77: [u"йо бро чё как дела %d" % i for i in range(30)]}

        def own(account, did, limit=100):
            return list(texts.get(did, []))
        self.p._own_texts = own
        self.p._style_src_cb(self.key())(77, "Bro")
        self.assertEqual(self.p.settings["style_src_" + self.sk], other)
        ex = self.p.get_profile(self.key(), 0, DID)["examples"]
        self.assertIn(u"йо бро чё как дела 29", ex)
        self.assertIn(self.p.t("bl_style_src", "Bro"), CLIENT.bulletins)
        self.p._set_style_src(self.key(), None, "")
        self.assertNotIn(u"йо бро чё как дела 29", self.p.get_profile(self.key(), 0, DID)["examples"])

    def test_other_account_refused(self):
        CLIENT.current_account = lambda: 1
        self.addCleanup(setattr, CLIENT, "current_account", lambda: 0)
        self.p._style_src_cb(self.key())(77, "Bro")
        self.assertFalse(self.p.settings.get("style_src_" + self.sk))
        self.assertIn(self.p.t("bl_style_src_acc"), CLIENT.bulletins)


class TestTalkPage(Pages):
    def test_rows_and_limits(self):
        self.enable()
        self.p.settings["ui_mode"] = 1
        sk = self.p._sk(self.key())
        talk = self.page("pg_talk:" + self.key())
        for k in ("start_", "refresh_", "learn_now_", "test_", "react_", "vector_", "vector_days_", "daily_",
                  "style_src_pick_"):
            self.assertIn(k + sk, talk)
        self.assertLessEqual(len(self.p.create_settings("pg_chat:" + self.key())), 14)
        self.assertLessEqual(len(self.p.create_settings("pg_talk:" + self.key())), 14)

    def test_removing_the_chat_clears_the_new_settings(self):
        self.enable()
        sk = self.p._sk(self.key())
        self.p.settings.update({"vector_" + sk: "x", "daily_" + sk: True, "style_src_" + sk: "0:77"})
        self.p.chat_off(self.key(), remove=True)
        for k in ("vector_", "daily_", "style_src_"):
            self.assertIsNone(self.p.settings.get(k + sk))


class TestCodes(unittest.TestCase):
    def test_reasons(self):
        for c in ("daily_due", "daily_talked_today", "daily_limit", "vector_expired", "chat_studied"):
            self.assertIn(c, mod.R)


if __name__ == "__main__":
    unittest.main()
