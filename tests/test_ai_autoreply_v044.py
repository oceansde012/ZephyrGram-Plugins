"""0.4.4: diagnostic report (last hour) for the developer; deeper decision log written with a throttle."""
import json

from test_ai_autoreply import Base, CLIENT, DID, all_settings, mod

SECRET_IN = "zxqvortlemon plumbaxion"
SECRET_OWNER = "quindlewarp mortisfable"


def by_key(items):
    return {getattr(i, "key", None): i for i in items}


class ReportBase(Base):
    def setUp(self):
        Base.setUp(self)
        self.enable()
        self.now = int(self.clock[0])

    def report(self):
        text, _n = self.p.build_report()
        return text

    def history(self, rows):
        CLIENT.history[:] = [dict(r, dialog_id=r.get("dialog_id", DID)) for r in rows]


class TestReportContent(ReportBase):
    def test_sections_header_and_settings(self):
        self.incoming(text="hello there")
        self.fire_timers()
        text = self.report()
        for part in ("=== ai_autoreply diagnostic report ===", "v" + mod.__version__,
                     "no message texts included", "preset Balanced", "master ON", "settings: reply_all=off",
                     "skip_links=on", "max_parts=4", "owner_active=45s", "debounce=3s", "cooldown=20s",
                     "chat_hourly=20", "hourly_cap=30", "daily_cap=50", "scan=off", "stickers=on",
                     "chats: 1 listed, 1 enabled", "--- summary (window) ---", "outcomes:",
                     "== chat 0:%d | user | mode auto | enabled" % DID, "state: pending 0", "since: last_in",
                     "timeline (oldest first):", "DEC sent/ok", "=== end of report ==="):
            self.assertIn(part, text)
        self.assertIn("unix %d" % int(self.clock[0]), text)

    def test_effective_values_follow_the_preset(self):
        self.p.settings["preset"] = 3                 # Live
        self.p.settings.pop("debounce", None)
        text = self.report()
        self.assertIn("preset Live", text)
        self.assertIn("human_timing=on", text)
        self.assertIn("scan=on", text)
        self.assertIn("owner_active=15s", text)
        self.assertIn("debounce=2s", text)

    def test_no_message_texts_names_or_usernames(self):
        self.history([
            {"id": 1, "out": False, "date": self.now - 300, "text": SECRET_IN},
            {"id": 2, "out": True, "date": self.now - 200, "text": SECRET_OWNER},
        ])
        self.incoming(text=SECRET_IN + " again?")
        self.fire_timers()
        text = self.report()
        for word in ("zxqvortlemon", "plumbaxion", "quindlewarp", "mortisfable", "hello back", "Alice"):
            self.assertNotIn(word, text)
        self.assertIn("MSG in        %4d ch  text" % len(SECRET_IN), text)
        self.assertIn("MSG out-owner %4d ch  text" % len(SECRET_OWNER), text)

    def test_directions_and_types(self):
        self.p._remember_bot_text("ну норм, а ти")
        self.history([
            {"id": 1, "out": False, "date": self.now - 120, "text": "", "has_media": True},
            {"id": 2, "out": True, "date": self.now - 60, "text": "ну норм, а ти"},
            {"id": 3, "out": False, "date": self.now - 50, "text": "", "has_media": True, "is_sticker": True},
            {"id": 4, "out": True, "date": self.now - 40, "text": "", "has_media": True},
            {"id": 5, "out": False, "date": self.now - 30, "text": "x", "is_service": True},
        ])
        text = self.report()
        self.assertIn("MSG in           0 ch  media  #1", text)
        self.assertIn("MSG out-bot     13 ch  text  #2", text)
        self.assertIn("ch  sticker  #3", text)
        self.assertIn("MSG out-?", text)
        self.assertNotIn("#5", text)                 # service rows are not listed
        self.assertIn("incoming -> bot reply: n 1 | avg 60s | max 60s", text)

    def test_reason_text_in_owner_language(self):
        self.p._decide(self.key(), "skip", "link")
        self.p.settings["ui_lang"] = 2               # Russian
        text = self.report()
        self.assertIn("DEC skip/link - " + mod.reason_text("ru", "link"), text)
        self.assertIn("skip/link 1", text)

    def test_suspicious_pause(self):
        self.history([{"id": 1, "out": False, "date": self.now - 1500, "text": "are you there"}])
        text = self.report()
        self.assertIn("suspicious pauses (> 10 min, enabled chat, master on): 1", text)
        self.assertIn("chat 0:%d: incoming at" % DID, text)
        self.assertIn("then nothing until now", text)
        self.p.settings["master"] = False             # the bot was told to be silent: not suspicious
        self.assertIn("pauses (> 10 min, enabled chat, master on): none", self.report())

    def test_reply_or_decision_ends_the_pause(self):
        self.history([{"id": 1, "out": False, "date": self.now - 1500, "text": "q"},
                      {"id": 2, "out": True, "date": self.now - 1400, "text": "a"}])
        self.assertIn("master on): none", self.report())
        self.history([{"id": 1, "out": False, "date": self.now - 1500, "text": "q"}])
        self.clock[0] -= 1450
        self.p._decide(self.key(), "skip", "link")
        self.clock[0] += 1450
        self.assertIn("master on): none", self.report())

    def test_enabled_chat_without_decisions_is_probed_by_history(self):
        other = 777
        self.p.chat_on(0, other, "Bob", "user")
        self.clock[0] += 4000                         # every decision is older than the window
        now = int(self.clock[0])
        CLIENT.history[:] = [{"id": 9, "out": False, "date": now - 900, "text": "hey", "dialog_id": other}]
        text = self.report()
        self.assertIn("== chat 0:%d | user | mode auto | enabled | fails 0 | no decisions in window" % other, text)
        self.assertIn("then nothing until now", text)
        self.assertNotIn("Bob", text)


class TestReportFlags(ReportBase):
    def test_stuck_inflight_and_timer(self):
        st = self.p._state(self.key())
        st.inflight = True
        st.timer = True
        self.clock[0] += 700
        text = self.report()
        self.assertIn("!! STUCK FLAG? inflight=True", text)
        self.assertIn("!! STUCK FLAG? timer=True", text)
        self.assertIn("inflight YES", text)

    def test_busy_flag_with_fresh_activity_is_not_stuck(self):
        st = self.p._state(self.key())
        st.inflight = True
        self.clock[0] += 700
        self.p._decide(self.key(), "info", "typing_sent")
        self.assertNotIn("STUCK", self.report())

    def test_pending_without_timer(self):
        st = self.p._state(self.key())
        st.pending = [(1, 7, "x"), (2, 7, "y")]
        st.timer = False
        self.assertIn("!! PENDING WITHOUT TIMER: 2 message(s)", self.report())
        st.timer = True
        self.assertNotIn("PENDING WITHOUT TIMER", self.report())

    def test_auto_disabled_after_errors(self):
        self.p._commit(self.key(), set={"enabled": False, "fails": 5, "auto_off_ts": self.clock[0]})
        self.p._decide(self.key(), "disabled", "auto_disabled_after_errors")
        text = self.report()
        self.assertIn("| disabled | fails 5 | auto_off 0s ago", text)
        self.assertIn("!! AUTO-DISABLED after repeated errors", text)

    def test_history_failure_does_not_break_the_report(self):
        old = CLIENT.get_recent_messages

        def boom(did, limit=20, account=None):
            raise RuntimeError("db locked " + SECRET_IN)
        CLIENT.get_recent_messages = boom
        try:
            self.p._decide(self.key(), "skip", "link")
            text = self.report()
        finally:
            CLIENT.get_recent_messages = old
        self.assertIn("history unavailable (RuntimeError)", text)
        self.assertIn("--- summary (window) ---", text)
        self.assertIn("DEC skip/link", text)
        self.assertNotIn("zxqvortlemon", text)


class TestReportSize(ReportBase):
    def test_limit_keeps_header_and_states_drops_oldest(self):
        for c in range(14):
            self.p.chat_on(0, 1000 + c, "C%d" % c, "user")
        for i in range(mod.DECISIONS_MAX):
            self.clock[0] += 5
            self.p._decide(self.p.chat_key(0, 1000 + i % 14), "skip", "some_rather_long_reason_code_%d" % (i % 7))
        now = int(self.clock[0])
        CLIENT.get_recent_messages = (lambda did, limit=20, account=None:
                                      [{"id": n, "out": n % 2 == 0, "date": now - 30 * n, "text": "w" * n,
                                        "dialog_id": did} for n in range(1, 40)][:limit])
        try:
            text, n = self.p.build_report()
        finally:
            CLIENT.get_recent_messages = lambda did, limit=20, account=None: list(CLIENT.history)[-limit:]
        self.assertLessEqual(len(text), mod.REPORT_MAX_CHARS)
        self.assertGreater(len(text), mod.REPORT_MAX_CHARS // 2)
        self.assertTrue(text.startswith("=== ai_autoreply diagnostic report ==="))
        self.assertIn("--- summary (window) ---", text)
        self.assertEqual(text.count("\n== chat "), mod.REPORT_MAX_CHATS)
        self.assertEqual(text.count("\nstate: "), mod.REPORT_MAX_CHATS)
        self.assertIn("older event(s) dropped to fit the size limit", text)
        self.assertIn("more chat(s) with decisions are not shown", text)
        self.assertTrue(text.rstrip().endswith("=== end of report ==="))
        self.assertGreater(n, 300)


class TestReportCommands(ReportBase):
    def test_parse_log_verbs(self):
        for w in ("log", "лог", "журнал", "report", "звіт", "отчет", "отчёт"):
            self.assertEqual(self.p.parse_admin(".ai " + w), ("log", ""), w)
        self.assertEqual(self.p.parse_admin(".аі лог"), ("log", ""))
        self.assertIsNone(self.p.parse_admin(".ai log now"))

    def test_ai_log_copies_the_report_and_is_not_sent(self):
        self.incoming(text=SECRET_IN)
        self.fire_timers()
        n_sent, n_ai = len(CLIENT.sent), len(CLIENT.ai_calls)
        res = self.p.on_send_message_hook(0, type("P", (), {"message": ".ai log", "peer": DID})())
        self.assertEqual(res.strategy, mod.HookStrategy.CANCEL)
        self.assertEqual(len(CLIENT.sent), n_sent)
        self.assertEqual(len(CLIENT.clipboard), 1)
        self.assertTrue(CLIENT.clipboard[0].startswith("=== ai_autoreply diagnostic report ==="))
        self.assertNotIn("zxqvortlemon", CLIENT.clipboard[0])
        self.assertIn("DEC cmd/admin_log", CLIENT.clipboard[0])
        self.assertIn("Report copied: %d characters" % len(CLIENT.clipboard[0]), CLIENT.bulletins[-1])
        self.assertEqual(len(CLIENT.ai_calls), n_ai)           # no AI call is needed for the report

    def test_ai_log_works_in_a_chat_that_is_not_listed(self):
        res = self.p.on_send_message_hook(0, type("P", (), {"message": ".ai log", "peer": 555})())
        self.assertEqual(res.strategy, mod.HookStrategy.CANCEL)
        self.assertEqual(len(CLIENT.clipboard), 1)

    def test_button_in_log_group_runs_in_background(self):
        bg = []
        old = CLIENT.run_in_bg
        CLIENT.run_in_bg = lambda fn: bg.append(fn)
        try:
            items = by_key(all_settings(self.p))
            self.assertEqual(items["log_report"].text, "Copy report (last hour)")
            items["log_report"].on_click()
            self.assertEqual(CLIENT.clipboard, [])     # nothing done on the UI thread
            self.assertEqual(len(bg), 1)
            bg[0]()
        finally:
            CLIENT.run_in_bg = old
        self.assertEqual(len(CLIENT.clipboard), 1)
        self.assertIn("Report copied", CLIENT.bulletins[-1])

    def test_button_also_with_an_empty_log(self):
        self.p.clear_log()
        items = by_key(all_settings(self.p))
        items["log_report"].on_click()
        self.assertIn("no chat had decisions or incoming messages in the window", CLIENT.clipboard[0])
        self.assertIn("Report copied: %d characters, 0 entries" % len(CLIENT.clipboard[0]), CLIENT.bulletins[-1])

    def test_labels_are_translated(self):
        for i, lang in ((1, "uk"), (2, "ru")):
            self.p.settings["ui_lang"] = i
            self.assertNotEqual(self.p.t("log_report"), mod.S["log_report"][0])
        self.assertEqual(mod.tr("ru", "log_report"), "Скопировать отчёт (последний час)")
        self.assertNotEqual(mod.reason_text("uk", "admin_log"), "admin log")

    def test_failure_is_reported_not_raised(self):
        self.p.build_report = lambda: (_ for _ in ()).throw(ValueError("x"))
        self.assertIsNone(self.p.report_to_clipboard())
        self.assertIn("Report failed", CLIENT.bulletins[-1])
        self.assertFalse(self.p._report_busy)


class TestDecisionLogStorage(Base):
    def count_writes(self):
        calls = []
        orig = self.p.set_setting

        def spy(k, v):
            if k == "decisions":
                calls.append(v)
            orig(k, v)
        self.p.set_setting = spy
        return calls

    def test_burst_is_written_once_then_throttled(self):
        calls = self.count_writes()
        for i in range(50):
            self.p._decide("0:1", "skip", "link")
        self.assertEqual(len(calls), 1)                 # the first one at once, the rest is held back
        self.clock[0] += 2
        self.p._decide("0:1", "skip", "link")
        self.assertEqual(len(calls), 1)
        self.clock[0] += mod.DECISIONS_FLUSH_SEC
        self.p._decide("0:1", "sent", "ok")
        self.assertEqual(len(calls), 2)
        self.assertEqual(len(json.loads(calls[-1])), 52)

    def test_unload_copy_and_report_force_the_write(self):
        calls = self.count_writes()
        self.p._decide("0:1", "skip", "link")
        self.p._decide("0:1", "skip", "quiet_hours")
        self.assertEqual(len(calls), 1)
        self.p.on_plugin_unload()
        self.assertEqual(len(calls), 2)
        self.assertEqual(json.loads(calls[-1])[-1]["r"], "quiet_hours")
        self.p.on_plugin_unload()                       # nothing new: no write
        self.assertEqual(len(calls), 2)
        self.p._decide("0:1", "skip", "link")
        self.p.copy_log()
        self.assertEqual(len(calls), 3)
        self.p._decide("0:1", "error", "ai_failed")
        self.p.build_report()
        self.assertEqual(len(calls), 4)

    def test_scan_tick_flushes_a_pending_burst(self):
        calls = self.count_writes()
        self.p._decide("0:1", "skip", "link")
        self.p._decide("0:1", "skip", "link")
        self.clock[0] += mod.DECISIONS_FLUSH_SEC + 1
        self.p._scan_armed = True
        self.p._scan_tick()
        self.assertEqual(len(calls), 2)

    def test_depth_is_400(self):
        for i in range(450):
            self.p._decide("0:%d" % (i % 3), "skip", "r%d" % i)
        self.assertEqual(len(self.p._decisions), mod.DECISIONS_MAX)
        self.assertEqual(mod.DECISIONS_MAX, 400)
        self.assertEqual(len(self.p.decision_rows()), 40)
        self.assertEqual(len(self.p.log_for_clipboard().splitlines()), 40)
        self.p.on_plugin_unload()
        self.assertEqual(len(json.loads(self.p.settings["decisions"])), 400)

    def test_old_stored_format_is_read(self):
        old = [{"t": 999000 + i, "chat": "0:42", "o": "skip", "r": "quiet_hours"} for i in range(59)]
        old.append({"t": 999100, "chat": "0:42", "o": "info", "r": "sticker_sent", "x": "🙂"})
        old.append("garbage")
        p2 = mod.Plugin()
        p2._now = lambda: 1000000.0
        p2.settings = dict(self.p.settings, decisions=json.dumps(old))
        p2.on_plugin_load()
        self.assertEqual(len(p2._decisions), 60)
        self.assertEqual(p2._decisions.maxlen, mod.DECISIONS_MAX)
        self.assertEqual(p2.decision_rows()[0][2]["x"], "🙂")
        text, n = p2.build_report()
        self.assertEqual(n, 60)
        self.assertIn("info/sticker_sent 🙂", text.replace("DEC ", ""))
        p2._decide("0:42", "sent", "ok")
        p2.on_plugin_unload()
        stored = json.loads(p2.settings["decisions"])
        self.assertEqual(len(stored), 61)
        self.assertEqual(set(stored[-1]), {"t", "chat", "o", "r"})

    def test_bad_stored_log_is_empty(self):
        p2 = mod.Plugin()
        p2.settings = dict(self.p.settings, decisions="{not json")
        p2.on_plugin_load()
        self.assertEqual(len(p2._decisions), 0)
        self.assertIn("no chat had decisions", p2.build_report()[0])
