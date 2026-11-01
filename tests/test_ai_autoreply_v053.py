"""0.5.2 cost control: bounded request size, one model per kind of task, cheap background helpers with daily limits,
incremental chat memory (on by default in private chats), usage counters in the log. Fake Zephyr, no network."""
from pathlib import Path
import json
import time
import uuid

from test_ai_autoreply import Base, CLIENT, DID, all_settings, chats_screen, mod, screen


def total_chars(call):
    return len(call.get("system") or "") + sum(len(str(m.get("content") or "")) for m in call["messages"])


class Fakes(Base):
    """A listed private chat, a recording AI and (optionally) a working memory store."""

    def setUp(self):
        super().setUp()
        self.enable()
        self.sk = self.p._sk(self.key())
        self.p.settings.update(owner_active="0", cooldown="0", typing_delay=False, stickers=False)
        self.calls = []
        self.summaries = []                     # answers of the fake summarizer, in order (default: a fixed one)
        self.original_ai = CLIENT.ai_complete
        self.original_history = CLIENT.get_recent_messages
        CLIENT.ai_complete = self.complete
        CLIENT.get_recent_messages = lambda did, limit=20, account=None: list(CLIENT.history)[-limit:]

    def tearDown(self):
        CLIENT.ai_complete = self.original_ai
        CLIENT.get_recent_messages = self.original_history
        super().tearDown()

    def complete(self, messages, **kwargs):
        call = dict(kwargs, messages=messages)
        self.calls.append(call)
        fail = kwargs.get("model") in getattr(self, "failing", ())
        if fail:
            raise RuntimeError("model down")
        if str(kwargs.get("system", "")).startswith("Summarize only"):
            return self.summaries.pop(0) if self.summaries else json.dumps({"summary": "Alice likes cats."})
        if "STICKER CANDIDATES" in str(messages[-1].get("content")):
            return '{"use_sticker": false}'
        if str(kwargs.get("system", "")).startswith("You keep short notes") or "Existing notes" in str(messages[-1].get("content")):
            return "- likes cats"
        return "ну норм"

    def with_memory(self, owner=111):
        self.root = Path(__file__).resolve().parents[1] / "out" / "test-v053" / uuid.uuid4().hex
        self.root.mkdir(parents=True)
        self.p.data_dir = str(self.root)
        self.p._memory_owner_id = lambda account: owner if account == 0 else None
        return self.p._memory_for_owner(0, owner)

    def rows(self, n, start=1, size=40, did=DID):
        return [{"id": i, "date": 1000 + i, "text": ("msg %d " % i) + "x" * max(0, size - 8), "out": bool(i % 2),
                 "from_id": 111 if i % 2 else 7, "dialog_id": did, "account": 0} for i in range(start, start + n)]

    def summary_calls(self):
        return [c for c in self.calls if str(c.get("system", "")).startswith("Summarize only")]

    def reply_calls(self):
        return [c for c in self.calls if not str(c.get("system", "")).startswith("Summarize only")]

    def reply(self, text="а що там?"):
        self.incoming(text=text, mid=10000 + self.n)                # ids above the fake history rows
        self.fire_timers()


class TestModelPerTask(Fakes):
    def test_model_for_each_kind(self):
        self.assertEqual(self.p._model_for("reply"), "")
        self.assertEqual(self.p._model_for("memory"), "")
        self.p.settings["model"] = "smart"
        for kind in ("reply", "command", "revive", "test", "memory", "learn", "sticker"):
            self.assertEqual(self.p._model_for(kind), "smart", kind)      # empty cheap model = the main one
        self.p.settings["model_cheap"] = " cheap "
        for kind in ("memory", "learn", "sticker"):
            self.assertEqual(self.p._model_for(kind), "cheap", kind)
        for kind in ("reply", "command", "revive", "test"):
            self.assertEqual(self.p._model_for(kind), "smart", kind)

    def test_replies_use_the_smart_model_and_helpers_the_cheap_one(self):
        self.p.settings.update(model="smart", model_cheap="cheap", lore_learn=True)
        self.reply()
        self.assertEqual({c.get("model") for c in self.reply_calls()}, {"smart"})
        CLIENT.history[:] = self.rows(12)
        self.p._learn_notes(self.key(), self.p._state(self.key()))
        self.assertEqual(self.calls[-1].get("model"), "cheap")
        self.assertEqual(self.p.settings.get("learned_" + self.sk), "- likes cats")

    def test_sticker_picker_gets_the_cheap_model_and_a_bounded_prompt(self):
        self.p.settings.update(model="smart", model_cheap="cheap", stickers=True, sticker_pct="100")
        saved = {n: getattr(CLIENT, n, None) for n in ("get_recent_stickers", "send_sticker")}
        CLIENT.get_recent_stickers = lambda limit=30, account=None: [
            {"id": i, "emoji": u"😂", "set_title": "set %d " % i + "y" * 300} for i in range(1, 61)]
        CLIENT.send_sticker = lambda *a, **k: True
        try:
            c = self.p._chats[self.key()]
            self.p._maybe_sticker(c, DID, 0, [(1, 7, u"ахах " * 400)] * 8, [u"ха"], False, key=self.key())
        finally:
            for n, v in saved.items():
                if v is None:
                    delattr(CLIENT, n)
                else:
                    setattr(CLIENT, n, v)
        picker = [c for c in self.calls if "STICKER CANDIDATES" in str(c["messages"][-1]["content"])]
        self.assertEqual(len(picker), 1)
        self.assertEqual(picker[0]["model"], "cheap")
        self.assertLessEqual(len(picker[0]["messages"][0]["content"]), 4000)

    def test_failing_cheap_model_falls_back_to_the_main_one_and_pauses(self):
        store = self.with_memory()
        self.p.settings.update(model="smart", model_cheap="cheap")
        self.failing = ("cheap",)
        CLIENT.history[:] = self.rows(42)
        self.assertIn("untrusted_chat_memory_json", self.p._memory_context(self.key(), 0, DID))
        self.assertEqual([c["model"] for c in self.summary_calls()], ["cheap", "smart"])
        self.assertEqual(store.get_summary(0, DID, enabled=True)["summary"], "Alice likes cats.")
        self.assertEqual(sum(1 for d in self.p._decisions if d.get("r") == "cheap_model_failed"), 1)
        # while paused, background work goes straight to the main model (no wasted request)
        self.assertEqual(self.p._helper_models("memory"), ["smart"])
        self.clock[0] += mod.CHEAP_FAIL_PAUSE + 1
        self.assertEqual(self.p._helper_models("memory"), ["cheap", "smart"])
        stats = self.p._ai_stats()
        self.assertEqual(stats["k"]["memory"][0], 2)                  # both requests are counted

    def test_helper_errors_never_break_a_reply(self):
        self.with_memory()
        self.p.settings.update(model_cheap="cheap", stickers=True, sticker_pct="100")

        def ai(messages, **kwargs):
            self.calls.append(dict(kwargs, messages=messages))
            if kwargs.get("model") == "cheap" or str(kwargs.get("system", "")).startswith("Summarize only"):
                raise RuntimeError("helper down")
            return "ну норм"
        CLIENT.ai_complete = ai
        CLIENT.history[:] = self.rows(42)
        self.reply()
        self.assertEqual(len(CLIENT.sent), 1)
        self.assertTrue(self.p.is_enabled(self.key()))


class TestRequestSize(Fakes):
    def huge_setup(self):
        self.p.settings.update(default_prompt="ВЛАСНІ ПРАВИЛА " * 8000, lore="про мене " * 2000,
                               context_chars="48000", context_n="100")
        self.p.settings["lore_" + self.sk] = "чат " * 2000
        self.p.settings["learned_" + self.sk] = "- нотатка\n" * 500
        self.p.get_profile = lambda *a, **k: {"examples": ["приклад мого стилю " * 12 for _ in range(40)],
                                              "style": {}}
        now = int(self.clock[0])
        CLIENT.history[:] = [dict(r, date=now - 5000 + r["id"]) for r in self.rows(100, size=3000)]

    def test_no_request_ever_exceeds_the_limit(self):
        self.huge_setup()
        for limit, expected in (("", mod.PROMPT_MAX_DEFAULT), ("8000", 8000), ("999999", mod.PROMPT_MAX_HARD)):
            self.calls[:] = []
            self.p.settings["prompt_max"] = limit
            self.clock[0] += 100
            self.reply("ЗАПИТАННЯ ПОЧАТОК " + "z" * 30000 + " КІНЕЦЬ?")
            self.assertTrue(self.reply_calls(), limit)
            for call in self.reply_calls():
                self.assertLessEqual(total_chars(call), expected, limit)
            last = self.reply_calls()[-1]["messages"][-1]["content"]
            self.assertTrue(last.startswith("ЗАПИТАННЯ ПОЧАТОК") and last.endswith("КІНЕЦЬ?"), limit)

    def test_plain_mode_and_commands_are_bounded_too(self):
        self.huge_setup()
        self.p.settings.update(humanize=False, prompt_max="10000")
        self.reply("питання?")
        self.assertTrue(self.reply_calls())
        self.assertTrue(all(total_chars(c) <= 10000 for c in self.reply_calls()))
        self.p.settings["humanize"] = True
        self.calls[:] = []
        self.p.run_command(0, DID, self.key(), True, "привітай")
        self.assertTrue(self.calls)
        self.assertTrue(all(total_chars(c) <= 10000 for c in self.calls))

    def test_owner_prompt_is_capped_inside_one_request(self):
        self.p.settings["default_prompt"] = "rule\n" * 5000
        system = self.p.build_system(self.key(), {})
        self.assertLess(len(system), 4000 + 4000)
        self.assertIn("Extra instructions from the owner", system)

    def test_system_prompt_shrinks_examples_first_and_is_logged(self):
        self.huge_setup()
        self.p.settings["prompt_max"] = "12000"
        self.reply()
        system = self.reply_calls()[0]["system"]
        self.assertLessEqual(len(system), int((12000 - mod.RETRY_RESERVE) * mod.SYSTEM_SHARE) + 10)
        self.assertIn(mod.HUMAN_PROMPT[:60], system)                   # the rules stay
        self.assertTrue(any(d.get("r") == "prompt_trimmed" for d in self.p._decisions))

    def test_typical_request_fits_the_default_budget_without_trimming(self):
        """Measures the real system prompt: 24 typical style examples, lore, notes, a group label and the language
        rule stay far below the system share of the default budget, so typical replies are never trimmed."""
        ex = [u"ну так, я вже вдома, завтра напишу нормально" for _ in range(24)]
        self.p.settings.update(lore=u"Я Влад, працюю в ДСНС, люблю Counter-Strike і котів. " * 4)
        self.p.settings["learned_" + self.sk] = u"- любить котів\n- вчиться на програміста"
        profile = {"examples": ex, "style": mod.compute_style(ex)}
        system = (self.p.build_system(self.key(), profile) + "\n\n" + self.p._lore_block(self.key())
                  + "\n\n" + mod.lang_rule("Ukrainian"))
        self.assertLess(len(system), 8000)
        self.assertLess(len(system), (mod.PROMPT_MAX_DEFAULT - mod.RETRY_RESERVE) * mod.SYSTEM_SHARE)
        self.p.get_profile = lambda *a, **k: profile
        now = int(self.clock[0])
        CLIENT.history[:] = [dict(r, date=now - 500 + r["id"]) for r in self.rows(40, size=60)]
        self.reply()
        call = self.reply_calls()[0]
        self.assertLess(total_chars(call), 12000)                     # ~4k tokens for a typical reply
        self.assertIn("STYLE EXAMPLES ONLY", call["system"])
        self.assertEqual(call["system"].count("\n- " + ex[0]), 24)
        self.assertFalse(any(d.get("r") == "prompt_trimmed" for d in self.p._decisions))

    def test_current_batch_first_then_memory_then_newest_history(self):
        store = self.with_memory()
        self.assertTrue(store.set_summary(0, DID, "ПАМ'ЯТЬ: " + "факт\n" * 1500, 0, enabled=True))
        self.p.settings.update(prompt_max="12000")
        now = int(self.clock[0])
        CLIENT.history[:] = [dict(r, date=now - 500 + r["id"]) for r in self.rows(60, size=400)]
        self.reply("ПОТОЧНЕ " + "q" * 1500)
        call = self.reply_calls()[0]
        self.assertLessEqual(total_chars(call), 12000)
        self.assertIn("ПАМ'ЯТЬ", call["system"])                       # memory goes before history
        self.assertEqual(call["messages"][-1]["content"], "ПОТОЧНЕ " + "q" * 1500)
        texts = [m["content"] for m in call["messages"][:-1]]
        self.assertTrue(texts and texts[-1].startswith("msg 60"))      # the newest history survives, the oldest goes
        self.assertFalse(any(t.startswith("msg 1 ") for t in texts))

    def test_requests_are_counted(self):
        self.reply()
        stats = self.p._ai_stats()
        n, chars, top = stats["k"]["reply"]
        self.assertEqual(n, len(self.reply_calls()))
        self.assertEqual(chars, sum(total_chars(c) for c in self.reply_calls()))
        self.assertEqual(top, max(total_chars(c) for c in self.reply_calls()))
        self.assertEqual(self.p._ai_ring[-1]["chat"], self.key())


class TestHelperLimits(Fakes):
    def test_global_daily_limit_stops_helpers_but_not_replies(self):
        self.with_memory()
        self.p.settings["helper_daily"] = "1"
        CLIENT.history[:] = self.rows(42)
        self.assertTrue(self.p._memory_context(self.key(), 0, DID))
        with self.assertRaises(mod.HelperSkipped):
            self.p._helper_complete("sticker", self.key(), [{"role": "user", "content": "x"}], "s")
        self.p.settings["lore_learn"] = True
        self.p._learn_notes(self.key(), self.p._state(self.key()))
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(sum(1 for d in self.p._decisions if d.get("r") == "helper_daily_cap"), 1)
        self.reply()
        self.assertEqual(len(CLIENT.sent), 1)
        self.p.settings["helper_daily"] = "0"
        with self.assertRaises(mod.HelperSkipped):
            self.p._helper_complete("memory", self.key(), [{"role": "user", "content": "x"}], "s")

    def test_limits_reset_on_a_new_day_and_yesterday_is_kept(self):
        self.p._track("memory", self.key(), 5000)
        self.assertEqual(self.p._ai_stats()["m"][self.key()], 1)
        self.clock[0] += 86400 * 2
        s = self.p._ai_stats()
        self.assertEqual(s["k"], {})
        self.assertEqual(s["m"], {})
        self.assertEqual(s["prev"]["k"]["memory"], [1, 5000, 5000])

    def test_per_chat_memory_limit(self):
        self.with_memory()
        self.p.settings["memory_daily"] = "1"
        CLIENT.history[:] = self.rows(42)
        self.assertTrue(self.p._memory_context(self.key(), 0, DID))
        CLIENT.history[:] = self.rows(80)
        self.clock[0] += 3600
        self.p._memory_context(self.key(), 0, DID)
        self.assertEqual(len(self.summary_calls()), 1)
        self.assertTrue(any(d.get("r") == "memory_daily_cap" for d in self.p._decisions))

    def test_helper_input_is_bounded(self):
        with self.assertRaises(ValueError):
            self.p._helper_complete("learn", self.key(), [{"role": "user", "content": "x" * mod.HELPER_MAX_CHARS}], "s")
        self.assertEqual(self.calls, [])

    def test_broken_counters_never_raise(self):
        self.p.settings["ai_stats"] = "{broken"
        self.p._track("reply", self.key(), 10)
        self.assertEqual(self.p._ai_stats()["k"]["reply"], [1, 10, 10])
        self.p.settings["ai_stats"] = json.dumps({"day": self.p._day(), "k": {"reply": "x"}, "m": []})
        self.assertIsNone(self.p._helper_reserve("memory", self.key(), 10))


class TestMemoryDefault(Fakes):
    def test_on_in_private_chats_off_switches_and_groups(self):
        self.assertTrue(self.p._memory_flag(self.key()))
        self.p.settings["memory_" + self.sk] = False                 # the chat's own off switch wins
        self.assertFalse(self.p._memory_flag(self.key()))
        self.p.settings["memory_" + self.sk] = None
        self.p.settings["memory_auto"] = False
        self.assertFalse(self.p._memory_flag(self.key()))
        self.p.settings["memory_" + self.sk] = True                  # explicit consent works without the default
        self.assertTrue(self.p._memory_flag(self.key()))
        gkey = "0:-100"
        self.p._chats[gkey] = {"enabled": True, "account": 0, "dialog_id": -100, "type": "group"}
        self.p.settings["memory_auto"] = True
        self.assertFalse(self.p._memory_flag(gkey))                  # groups: only with their own switch
        self.p.settings["memory_" + self.p._sk(gkey)] = True
        self.assertTrue(self.p._memory_flag(gkey))
        self.p._chats[self.key()]["enabled"] = False
        self.assertFalse(self.p._memory_flag(self.key()))

    def test_default_consent_reads_only_the_reply_context_for_the_first_summary(self):
        self.with_memory()
        CLIENT.history[:] = self.rows(100)
        self.p._memory_context(self.key(), 0, DID)
        ids = [r["id"] for r in json.loads(self.summary_calls()[0]["messages"][0]["content"])["messages"]]
        self.assertEqual((min(ids), max(ids)), (61, 88))              # newest 40 minus the newest 12

    def test_explicit_consent_may_read_older_history(self):
        self.with_memory()
        self.p.settings["memory_" + self.sk] = True
        CLIENT.history[:] = self.rows(100)
        self.p._memory_context(self.key(), 0, DID)
        ids = [r["id"] for r in json.loads(self.summary_calls()[0]["messages"][0]["content"])["messages"]]
        self.assertEqual((min(ids), max(ids)), (1, 88))

    def test_settings_screen_shows_the_effective_default(self):
        self.p._open_key = self.key()
        row = next(i for i in chats_screen(self.p) if getattr(i, "key", None) == "memory_" + self.sk)
        self.assertTrue(row.default)
        self.p.settings["memory_auto"] = False
        row = next(i for i in chats_screen(self.p) if getattr(i, "key", None) == "memory_" + self.sk)
        self.assertFalse(row.default)

    def test_stored_values_are_untouched(self):
        self.p.settings["memory_" + self.sk] = False
        self.with_memory()
        CLIENT.history[:] = self.rows(42)
        self.reply()
        self.fire_timers()
        self.assertIs(self.p.settings["memory_" + self.sk], False)
        self.assertNotIn("memory_auto", self.p.settings)
        self.assertEqual(self.summary_calls(), [])

    def test_unavailable_memory_replies_as_before(self):
        self.p.data_dir = None
        self.p._memory_owner_id = lambda account: 111
        self.reply()
        self.assertEqual(len(CLIENT.sent), 1)
        self.assertNotIn("COMPACT CHAT MEMORY", self.reply_calls()[0]["system"])


class TestIncrementalMemory(Fakes):
    def setUp(self):
        super().setUp()
        self.store = self.with_memory()
        self.p.settings["memory_" + self.sk] = True

    def record(self):
        return self.store.get_summary(0, DID, enabled=True)

    def test_update_triggers(self):
        CLIENT.history[:] = self.rows(42)
        self.p._memory_context(self.key(), 0, DID)
        self.assertEqual(self.record()["through_id"], 30)
        CLIENT.history[:] = self.rows(42 + mod.MEM_NEW_MIN - 1)
        self.clock[0] += 3600
        self.p._memory_context(self.key(), 0, DID)
        self.assertEqual(len(self.summary_calls()), 1)               # too few new messages
        CLIENT.history[:] = self.rows(42 + mod.MEM_NEW_MIN)
        self.p._memory_context(self.key(), 0, DID)
        self.assertEqual(len(self.summary_calls()), 2)
        payload = json.loads(self.summary_calls()[-1]["messages"][0]["content"])
        self.assertEqual(payload["previous_summary"], "Alice likes cats.")
        self.assertEqual(min(r["id"] for r in payload["messages"]), 31)
        self.assertEqual(self.record()["through_id"], 30 + mod.MEM_NEW_MIN)

    def test_idle_trigger_with_few_new_messages(self):
        CLIENT.history[:] = self.rows(42)
        self.p._memory_context(self.key(), 0, DID)
        CLIENT.history[:] = self.rows(42 + mod.MEM_IDLE_MIN)
        self.clock[0] += 3600
        self.p._memory_context(self.key(), 0, DID)
        self.assertEqual(len(self.summary_calls()), 1)
        self.clock[0] = time.time() + mod.MEM_IDLE_SEC + 60           # the stored summary is old now
        self.p._memory_context(self.key(), 0, DID)
        self.assertEqual(len(self.summary_calls()), 2)

    def test_long_gap_is_chained_and_bounded(self):
        CLIENT.history[:] = self.rows(100, size=600)
        self.p._memory_context(self.key(), 0, DID)
        calls = self.summary_calls()
        self.assertGreater(len(calls), 1)
        self.assertLessEqual(len(calls), mod.MEM_CHAIN)
        for c in calls:
            payload = json.loads(c["messages"][0]["content"])
            self.assertLessEqual(len(json.dumps(dict(payload, previous_summary=""), ensure_ascii=False)),
                                 mod.MEM_INPUT_MSGS + 40)
            self.assertLessEqual(total_chars(c), mod.HELPER_MAX_CHARS)
        ids = [r["id"] for c in calls for r in json.loads(c["messages"][0]["content"])["messages"]]
        self.assertEqual(ids, sorted(set(ids)))                     # each message once, oldest first
        self.assertEqual(self.record()["through_id"], max(ids))
        self.assertEqual(self.record()["revision"], len(calls))

    def test_gap_beyond_the_app_window_is_marked(self):
        self.assertTrue(self.store.set_summary(0, DID, "old facts", 5, enabled=True))
        CLIENT.history[:] = self.rows(100, start=500)
        self.p._memory_context(self.key(), 0, DID)
        payload = json.loads(self.summary_calls()[0]["messages"][0]["content"])
        self.assertTrue(payload.get("gap_before"))
        self.assertIn("gap_before", self.summary_calls()[0]["system"])
        self.assertTrue(any(d.get("r") == "memory_gap" for d in self.p._decisions))

    def test_summary_parsing_and_caps(self):
        self.assertEqual(mod.parse_summary('```json\n{"summary": "a"}\n```'), "a")
        self.assertEqual(mod.parse_summary('Here: {"summary": "b"} ok'), "b")
        self.assertEqual(len(mod.parse_summary(json.dumps({"summary": "line\n" * 5000}))), mod.MEM_SUMMARY_MAX - 1)
        for bad in ("", "nope", '{"summary": ""}', '{"summary": 5}', "[]"):
            with self.assertRaises(ValueError):
                mod.parse_summary(bad)
        self.summaries = [json.dumps({"summary": "важливе\n" + "деталь " * 2000})]
        CLIENT.history[:] = self.rows(42)
        block = self.p._memory_context(self.key(), 0, DID)
        self.assertLessEqual(len(self.record()["summary"]), mod.MEM_SUMMARY_MAX)
        self.assertGreater(len(self.record()["summary"]), mod.MEM_INJECT_MAX)
        self.assertLess(len(block), mod.MEM_INJECT_MAX + 700)        # only the first part goes into a reply
        self.assertIn("важливе", block)
        self.assertEqual(self.p._memory_block(self.record(), max_chars=300), "")

    def test_covered_history_is_not_sent_raw_again(self):
        self.assertTrue(self.store.set_summary(0, DID, "Alice likes cats.", 70, enabled=True))
        now = int(self.clock[0])
        CLIENT.history[:] = [dict(r, date=now - 500 + r["id"]) for r in self.rows(100)]
        self.reply("питання")
        call = self.reply_calls()[0]
        self.assertIn("Alice likes cats.", call["system"])
        texts = [m["content"] for m in call["messages"]]
        self.assertFalse(any(t.startswith("msg 65 ") for t in texts))  # covered by the summary and old
        self.assertTrue(any(t.startswith("msg 72 ") for t in texts))   # newer than the summary: raw (71 is ours: leading)
        self.assertEqual(texts[-1], "питання")
        self.assertLessEqual(len(texts), 40)

    def test_reply_never_waits_and_silent_chats_still_update(self):
        CLIENT.history[:] = self.rows(42)
        self.p._memory_context(self.key(), 0, DID, blocking=False)
        self.assertEqual(self.summary_calls(), [])
        self.fire_timers()
        self.assertEqual(len(self.summary_calls()), 1)
        # the owner answers himself for a while: no reply, but the messages still reach the memory
        CLIENT.history[:] = self.rows(42 + mod.MEM_NEW_MIN)
        self.clock[0] += 3600
        for i in range(mod.MEM_SEEN_KICK):
            self.p._handle_dict(0, DID, dict(self.msg(text="я сам %d" % i, out=True)))
        self.fire_timers()
        self.assertEqual(len(self.summary_calls()), 2)
        self.assertEqual(CLIENT.sent, [])

    def test_revoked_consent_during_background_update(self):
        CLIENT.history[:] = self.rows(42)

        def late(messages, **kwargs):
            self.p.settings["memory_" + self.sk] = False
            return json.dumps({"summary": "must not be stored"})
        CLIENT.ai_complete = late
        self.assertEqual(self.p._memory_context(self.key(), 0, DID), "")
        self.assertIsNone(self.record())


class TestVisibility(Fakes):
    def test_report_shows_sizes_models_and_daily_counts(self):
        self.p.settings.update(model="smart", model_cheap="cheap")
        self.reply()
        self.p._track("memory", self.key(), 9000)
        text, _n = self.p.build_report()
        self.assertIn("cost: model=smart model_cheap=cheap", text)
        self.assertIn("prompt_max=24000 ch (~8.0k tok)", text)
        self.assertIn("AI requests today", text)
        self.assertIn("memory 1 ~3.0k tok", text)
        self.assertRegex(text, r"AI requests in window \(size = what was sent\): reply \d")
        self.assertRegex(text, r"AI  reply\s+\d+ ch ~\S+ tok")
        self.assertNotIn("а що там", text)                            # still no message texts

    def test_admin_log_command_contains_the_cost_lines(self):
        self.reply()
        self.p._run_admin(0, DID, self.key(), "log", "")
        self.assertIn("AI requests today", CLIENT.clipboard[-1])

    def test_limits_section_counter_and_new_settings_in_their_sections(self):
        self.reply()
        keys = lambda sid: [getattr(i, "key", None) for i in screen(self.p, sid)]
        self.assertIn("model_cheap", keys("prompts"))
        self.assertIn("prompt_max", keys("limits"))
        self.assertIn("helper_daily", keys("limits"))
        self.assertIn("memory_auto", keys("media"))
        self.assertIn("memory_daily", keys("media"))
        notes = [str(getattr(i, "text", "")) for i in screen(self.p, "limits")]
        self.assertTrue(any(n.startswith("Today: %d reply requests" % len(self.reply_calls())) for n in notes))

    def test_three_languages(self):
        for k in ("model_s", "model_cheap", "model_cheap_s", "prompt_max", "prompt_max_s", "helper_daily",
                  "helper_daily_s", "usage_today", "memory_auto", "memory_auto_s", "memory_daily", "memory_daily_s",
                  "memory_consent"):
            self.assertEqual(len(mod.S[k]), 3, k)
            self.assertTrue(all(mod.S[k]), k)
        for k in ("memory_updated", "memory_gap", "memory_daily_cap", "memory_full", "helper_daily_cap",
                  "cheap_model_failed", "prompt_trimmed", "sticker_why_helper_cap"):
            self.assertEqual(len(mod.R[k]), 3, k)
            self.assertTrue(all(mod.R[k]), k)
        self.assertEqual(mod.S["usage_today"][1].count("%"), mod.S["usage_today"][0].count("%"))
        self.assertEqual(mod.S["usage_today"][2].count("%"), mod.S["usage_today"][0].count("%"))

    def test_token_estimate(self):
        self.assertEqual(mod.approx_tokens(0), "0")
        self.assertEqual(mod.approx_tokens(300), "100")
        self.assertEqual(mod.approx_tokens(24000), "8.0k")


if __name__ == "__main__":
    import unittest
    unittest.main(verbosity=2)
