"""0.9.2: optional conversation plan per chat (#48). Fake Zephyr, no network, no real AI calls.

Part 2: "ask me about important things" (opt-in): an important reply ([ASK] from the model in the same request, or
the money/meeting/promise safety net) goes to Saved Messages first and waits for '+', '- text' or 'неважно'.

One line of the plan per day of talk. The current stage goes into the prompt as a soft rule (no extra AI call);
it moves forward on the next day of talk, or earlier when the person already talks about a later stage, never back.
"""
import unittest

from test_ai_autoreply import Base, CLIENT, DID, mod

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


OWNER = 555


class Params(object):
    def __init__(self, message, peer=OWNER):
        self.message, self.peer = message, peer


class TestAskOwner(Base):
    def setUp(self):
        super().setUp()
        self.enable()
        self.p.settings.update(disclosure=False, owner_active="0", ask_owner=True, human_timing=False)
        self.p._memory_owner_id = lambda account: OWNER
        self.reads, self.typing, self.notes = [], [], []
        self.p._mark_read = lambda key, mid: self.reads.append(mid)
        self.p._send_typing = lambda did, account, cancel=False: self.typing.append(cancel) or True
        orig = mod.time.sleep
        mod.time.sleep = lambda s: None
        self.addCleanup(setattr, mod.time, "sleep", orig)
        CLIENT.NOTIFY = True
        CLIENT.notify = lambda title, text, account=None: self.notes.append((title, text)) or True
        self.addCleanup(lambda: (delattr(CLIENT, "NOTIFY"), delattr(CLIENT, "notify")))

    def st(self):
        return self.p._state(self.key())

    def ask(self, reply=u"[ASK] давай завтра в семь встретимся", text=u"встретимся завтра?"):
        CLIENT.ai_result = lambda m, **kw: reply
        self.incoming(text=text)
        for _ in range(5):                      # only the debounce timer, never the 30-minute timeout
            if self.st().ask or not CLIENT.ui_queue:
                break
            delay, fn = CLIENT.ui_queue.pop(0)
            self.clock[0] += delay / 1000.0
            fn()

    def to_chat(self):
        return [s[1] for s in CLIENT.sent if s[0] == DID]

    def to_owner(self):
        return [s[1] for s in CLIENT.sent if s[0] == OWNER]

    def answer(self, text):
        return self.p.on_send_message_hook(0, Params(text))

    def test_marker_detected_stripped_and_asked(self):
        self.ask()
        self.assertTrue(self.st().ask)
        self.assertEqual(self.to_chat(), [])
        req = self.to_owner()
        self.assertEqual(len(req), 1)
        self.assertIn(u"давай завтра в семь встретимся", req[0])
        self.assertIn(u"встретимся завтра?", req[0])
        self.assertNotIn("[ASK]", req[0])
        self.assertEqual(len(self.notes), 1)
        self.assertIn(mod.ASK_RULE, CLIENT.ai_calls[0]["system"])

    def test_no_read_receipt_and_no_typing_while_waiting(self):
        self.ask()
        self.assertEqual(self.reads, [])
        self.assertNotIn(False, self.typing)

    def test_plus_sends_the_reply(self):
        self.ask()
        r = self.answer("+")
        self.assertEqual(r.strategy, mod.HookStrategy.CANCEL)
        self.assertEqual(self.to_chat(), [u"давай завтра в семь встретимся"])
        self.assertIsNone(self.st().ask)
        self.assertTrue(self.reads)

    def test_minus_sends_the_owner_text(self):
        self.ask()
        self.answer(u"- не, завтра не могу, давай в пятницу")
        self.assertEqual(self.to_chat(), [u"не, завтра не могу, давай в пятницу"])

    def test_minus_alone_sends_nothing(self):
        self.ask()
        self.answer("-")
        self.assertEqual(self.to_chat(), [])
        self.assertIsNone(self.st().ask)

    def test_not_important_sends_and_notes(self):
        self.ask()
        self.answer(u"неважно")
        self.assertEqual(self.to_chat(), [u"давай завтра в семь встретимся"])
        self.assertIn(u"давай завтра в семь встретимся", self.p.settings["lore_" + self.p._sk(self.key())])

    def test_timeout_sends_nothing_and_tells_the_owner(self):
        self.ask()
        n = self.st().ask["n"]
        self.assertTrue(CLIENT.ui_queue)
        delay, fn = CLIENT.ui_queue.pop(-1)
        self.assertEqual(delay, 30 * 60 * 1000)
        fn()
        self.assertEqual(self.to_chat(), [])
        self.assertIsNone(self.st().ask)
        self.assertIn("#%d" % n, self.to_owner()[-1])
        self.assertIsNone(self.answer("+"))           # too late: an ordinary message

    def test_newer_messages_wait_then_continue(self):
        self.ask()
        CLIENT.ai_result = lambda m, **kw: u"ок"
        self.incoming(text=u"ау")
        self.assertTrue(self.st().pending)
        self.answer("+")
        self.assertTrue(self.st().timer)               # the held message is processed next

    def test_safety_net_without_marker(self):
        self.ask(reply=u"окей, переведу тебе 500 грн вечером")
        self.assertTrue(self.st().ask)

    def test_ordinary_reply_goes_out(self):
        self.ask(reply=u"нормально, а ты?", text=u"как дела?")
        self.assertIsNone(self.st().ask)
        self.assertEqual(self.to_owner(), [])

    def test_off_by_default_and_marker_never_sent(self):
        self.p.settings["ask_owner"] = None
        self.ask(reply=u"[ASK] давай в семь")
        self.assertIsNone(self.st().ask)
        self.assertNotIn(mod.ASK_RULE, CLIENT.ai_calls[0]["system"])
        self.assertEqual([x for x in self.to_chat() if "ASK" in x], [])

    def test_other_chats_messages_are_not_answers(self):
        self.ask()
        self.assertIsNone(self.p.on_send_message_hook(0, Params("+", peer=777)))
        self.assertTrue(self.st().ask)

    def test_old_app_without_notify_uses_bulletin(self):
        del CLIENT.NOTIFY
        self.ask()
        CLIENT.NOTIFY = True
        self.assertEqual(self.notes, [])
        self.assertTrue(any(mod.tr("uk", "ask_title") in b or mod.tr("en", "ask_title") in b or
                            mod.tr("ru", "ask_title") in b for b in CLIENT.bulletins))

    def test_marker_regexes(self):
        self.assertEqual(mod.ASK_MARK_RE.sub("", u"[ASK] давай"), u"давай")
        self.assertEqual(mod.ASK_MARK_RE.sub("", u"[ ask ]ок"), u"ок")
        for t in (u"скину 300 грн", u"договорились", u"приїду о сьомій", u"обещаю"):
            self.assertTrue(mod.ASK_NET_RE.search(t), t)
        for t in (u"как дела", u"приехал домой вчера", u"договор аренды"):
            self.assertFalse(mod.ASK_NET_RE.search(t), t)
        for t, verb in (("+", "+"), (u"ок", u"ок"), (u"- сам скажу", "-"), (u"неважно", u"неважно"), ("#3 +", "+")):
            self.assertEqual(mod.ASK_REPLY_RE.match(t).group(2).lower(), verb, t)
        self.assertIsNone(mod.ASK_REPLY_RE.match(u"привет"))

    def test_settings_rows(self):
        toks = mod.Plugin.PAGES["persona"].split()
        self.assertIn("ask_owner", toks)
        self.assertIn("ask_timeout", toks)
        self.assertLessEqual(len(toks), 14)


if __name__ == "__main__":
    unittest.main()
