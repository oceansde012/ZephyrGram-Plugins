"""Memory refresh never blocks a reply; slow AI answers are visible in the decision log."""
from test_ai_memory_v039 import TestCompactMemory as MemBase
from test_ai_autoreply import CLIENT, DID, mod


class TestMemoryDoesNotDelayReplies(MemBase):
    def test_reply_path_returns_without_calling_the_summary_model(self):
        self.opt_in()
        block = self.p._memory_context(self.key(), 0, DID, messages=[{"role": "user", "content": "actual text 7"}],
                                       blocking=False)
        self.assertEqual(block, "")                              # nothing stored yet, and nothing awaited
        self.assertEqual([c for c in self.calls if c[1].get("system", "").startswith("Summarize only")], [])
        self.assertEqual(len(CLIENT.ui_queue), 1)                # the refresh is only scheduled

    def test_scheduled_refresh_fills_the_summary_for_the_next_answer(self):
        self.opt_in()
        self.p._memory_context(self.key(), 0, DID, messages=[{"role": "user", "content": "actual text 7"}], blocking=False)
        self.fire_timers()
        summaries = [c for c in self.calls if c[1].get("system", "").startswith("Summarize only")]
        self.assertEqual(len(summaries), 1)
        block = self.p._memory_context(self.key(), 0, DID, messages=[{"role": "user", "content": "actual text 7"}],
                                       blocking=False)
        self.assertIn("untrusted_chat_memory_json", block)

    def test_only_one_background_refresh_at_a_time(self):
        self.opt_in()
        for _ in range(3):
            self.p._memory_context(self.key(), 0, DID, messages=[{"role": "user", "content": "actual text 7"}], blocking=False)
        self.assertEqual(len(CLIENT.ui_queue), 1)

    def test_failing_summary_is_logged_once_per_half_hour(self):
        self.opt_in()
        CLIENT.ai_complete = lambda messages, **kw: (_ for _ in ()).throw(RuntimeError("down"))
        for _ in range(3):
            self.p._memory_attempts.clear()
            self.p._memory_context(self.key(), 0, DID, messages=[{"role": "user", "content": "actual text 7"}])
        notes = [d for d in self.p._decisions if d.get("r") == "memory_unavailable"]
        self.assertEqual(len(notes), 1)

    def test_full_reply_does_not_wait_for_the_summary(self):
        self.opt_in()
        self.p.settings["owner_active"] = "0"
        self.incoming(text="actual text 7?")
        self.fire_once()                                       # debounce: reply is produced right away
        answers = [c for c in self.calls if not c[1].get("system", "").startswith("Summarize only")]
        self.assertEqual(len(answers), 1)
        self.assertEqual(len(CLIENT.sent), 1)


class TestSlowAiIsLogged(MemBase):
    def test_slow_answer_leaves_a_log_entry(self):
        self.p.settings["owner_active"] = "0"
        orig = CLIENT.ai_complete

        def slow(messages, **kw):
            self.clock[0] += 25
            return orig(messages, **kw)
        CLIENT.ai_complete = slow
        self.incoming(text="actual text 9?")
        self.fire_timers()
        slow_notes = [d for d in self.p._decisions if str(d.get("r", "")).startswith("ai_slow_")]
        self.assertEqual(len(slow_notes), 1)
        self.assertIn("slow AI server", mod.reason_text("en", slow_notes[0]["r"]))
