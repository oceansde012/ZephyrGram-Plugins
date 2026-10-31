"""0.4.7: without a timing preset every part still takes as long as it takes to type; big parts are rewritten."""
from test_ai_autoreply import Base, CLIENT, DID, mod


class TestNoInstantBigMessages(Base):
    def setUp(self):
        super().setUp()
        self.enable()
        self.p.settings["owner_active"] = "0"
        self.p.settings["disclosure"] = False
        self.sleeps = []
        mod.time.sleep = lambda s: self.sleeps.append(s)

    def marks(self):
        marks, original = [], CLIENT.send_text

        def send(did, text, reply_to=None, **kw):
            marks.append(sum(self.sleeps))
            return original(did, text, reply_to)
        CLIENT.send_text = send
        return marks, original

    def test_three_big_parts_are_not_sent_in_a_row(self):
        big = ("а " * 90).strip()                         # ~180 chars each, under the 'big' limit
        CLIENT.ai_result = lambda m, **kw: "\n".join([big, big, big])
        marks, original = self.marks()
        try:
            self.incoming(text="розкажи щось")
            self.fire_timers()
        finally:
            CLIENT.send_text = original
        self.assertEqual(len(marks), 3)
        self.assertGreaterEqual(marks[1] - marks[0], 5.0)     # ~180 chars at 35 ms = 6.3 s
        self.assertGreaterEqual(marks[2] - marks[1], 5.0)

    def test_short_parts_stay_quick(self):
        CLIENT.ai_result = lambda m, **kw: "ок\nзараз гляну"
        marks, original = self.marks()
        try:
            self.incoming(text="де ти")
            self.fire_timers()
        finally:
            CLIENT.send_text = original
        self.assertEqual(len(marks), 2)
        self.assertLessEqual(marks[1] - marks[0], 3.0)

    def test_explicit_typing_cap_is_still_a_total_budget(self):
        self.p.settings["typing_cap"] = "1"
        big = ("а " * 90).strip()
        CLIENT.ai_result = lambda m, **kw: "\n".join([big, big])
        self.incoming(text="розкажи щось")
        self.fire_timers()
        self.assertLessEqual(sum(self.sleeps), 1.0 + 1e-9)

    def test_typing_delay_switch_still_turns_pauses_off(self):
        self.p.settings["typing_delay"] = False
        CLIENT.ai_result = lambda m, **kw: "перше\nдруге"
        self.incoming(text="де ти")
        self.fire_timers()
        self.assertEqual(self.sleeps, [])

    def test_a_reply_with_a_huge_message_is_rewritten_once(self):
        huge = "слово " * 60                                # 360 chars in one line
        answers = [huge.strip(), "ок\nзараз гляну"]
        CLIENT.ai_result = lambda m, **kw: answers.pop(0)
        self.incoming(text="де ти")
        self.fire_timers()
        self.assertEqual(len(CLIENT.ai_calls), 2)
        self.assertIn("under about 120 characters", CLIENT.ai_calls[1]["system"])
        self.assertEqual([s[1] for s in CLIENT.sent], ["ок", "зараз гляну"])
