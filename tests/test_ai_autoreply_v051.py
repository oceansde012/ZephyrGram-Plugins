"""0.4.9: the plugin asks the app to keep the CPU awake while it has real work (timers stand still while asleep)."""
from test_ai_autoreply import Base, CLIENT, DID, mod


class TestKeepAwake(Base):
    def setUp(self):
        super().setUp()
        self.enable()
        self.calls = []
        CLIENT.keep_awake = lambda seconds: self.calls.append(float(seconds))
        self.p.settings["owner_active"] = "0"

    def tearDown(self):
        if hasattr(CLIENT, "keep_awake"):
            del CLIENT.keep_awake

    def test_incoming_message_holds_the_cpu_for_debounce_and_the_ai_call(self):
        self.incoming(text="привіт, ти тут?")
        self.assertTrue(self.calls and max(self.calls) >= 45)           # debounce timer scheduled
        before = len(self.calls)
        self.fire_timers()
        self.assertGreater(len(self.calls), before)
        self.assertTrue(any(c >= 150 for c in self.calls))              # while the AI writes the answer
        self.assertEqual(len(CLIENT.sent), 1)

    def test_every_request_is_bounded(self):
        self.incoming(text="привіт, ти тут?")
        self.fire_timers()
        self.assertTrue(all(1.0 <= c <= 180.0 for c in self.calls), self.calls)

    def test_long_pauses_between_parts_are_covered(self):
        self.p.settings["short_msgs"] = True
        CLIENT.ai_result = lambda m, **kw: "перше\n" + ("а " * 90).strip()
        self.incoming(text="розкажи щось")
        self.fire_timers()
        self.assertTrue(any(c >= 15 for c in self.calls))

    def test_idle_scan_does_not_hold_the_cpu(self):
        self.p._scan_all("periodic")
        self.p._scan_tick()
        self.assertEqual(self.calls, [])

    def test_old_apps_without_the_call_work_as_before(self):
        del CLIENT.keep_awake
        self.incoming(text="привіт, ти тут?")
        self.fire_timers()
        self.assertEqual(len(CLIENT.sent), 1)

    def test_a_failing_call_never_breaks_the_answer(self):
        def boom(seconds):
            raise RuntimeError("no wake lock")
        CLIENT.keep_awake = boom
        self.incoming(text="привіт, ти тут?")
        self.fire_timers()
        self.assertEqual(len(CLIENT.sent), 1)
