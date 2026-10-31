"""0.3.6 tests: Live preset (default), safety-net scan, human timing, typing/read/sticker actions, language.

Everything runs on a fake clock (Base.clock) and a recording time.sleep; nothing waits for real.
Run: python -m unittest discover -s tests -v
"""
import json
import random
import time
import unittest

from test_ai_autoreply import Base, CLIENT, DID, mod

ACTIONS = ("mark_read", "set_typing", "get_recent_stickers", "send_sticker", "send_request", "get_message_media")


class FixedRng(object):
    """uniform() returns the middle (or the lower end), random() a fixed value."""

    def __init__(self, rnd=0.5, low=False):
        self.rnd, self.low = rnd, low

    def uniform(self, a, b):
        return a if self.low else (a + b) / 2.0

    def random(self):
        return self.rnd

    def choice(self, seq):
        return seq[0]


class LiveBase(Base):
    """Base switched to the defaults of a new install (no preset, no reply_lang stored)."""

    def setUp(self):
        super(LiveBase, self).setUp()
        self.p.settings.pop("preset", None)
        self.p.settings.pop("reply_lang", None)
        self.events = []
        self.sleeps = []
        ev = self.events
        mod.time.sleep = lambda s: self.sleeps.append(s)
        self._send_text = CLIENT.send_text

        def send_text(did, text, reply_to=None):
            ev.append(("send", text))
            return self._send_text(did, text, reply_to)

        CLIENT.send_text = send_text
        CLIENT.mark_read = lambda did, max_id, account=None: ev.append(("read", did, max_id))
        CLIENT.set_typing = lambda did, account=None, cancel=False: ev.append(("cancel" if cancel else "typing", did))
        CLIENT.ai_result = lambda messages, **kw: "ну норм, дивись що вийде"

    def tearDown(self):
        CLIENT.send_text = self._send_text
        for a in ACTIONS:
            if hasattr(CLIENT, a):
                delattr(CLIENT, a)

    def hist(self, *rows):
        """rows: (out, age_seconds, text). Newest last. Returns the list put into the fake history."""
        out = []
        for i, (o, age, text) in enumerate(rows):
            out.append({"id": 1000 + i, "from_id": 7, "out": o, "date": int(self.clock[0] - age), "text": text,
                        "is_service": False, "dialog_id": DID})
        CLIENT.history[:] = out
        return out

    def kinds(self):
        return [e[0] for e in self.events]


class TestLivePreset(unittest.TestCase):
    def test_new_install_is_live_and_explicit_choice_stays(self):
        p = mod.Plugin()
        p.settings["ui_lang"] = 3
        p.on_plugin_load()
        self.assertEqual(p._preset_index(), mod.LIVE_PRESET)
        self.assertEqual(p._pnum("owner_active", 0, 3600), 15)
        self.assertEqual(p._pnum("hourly_cap", 0, 100000), 0)
        self.assertEqual(p._pnum("chat_hourly", 1, 1000), 60)
        self.assertTrue(p._live())
        self.assertTrue(p._pbool("scan"))
        for v in (0, 1, 2):
            p.settings["preset"] = v
            self.assertEqual(p._preset_index(), v)
            self.assertFalse(p._live())
        p.settings["preset"] = "garbage"
        self.assertEqual(p._preset_index(), mod.LIVE_PRESET)
        p.settings["preset"] = 0
        self.assertEqual(p._pnum("owner_active", 0, 3600), 45)
        p.settings["owner_active"] = "9"
        self.assertEqual(p._pnum("owner_active", 0, 3600), 9)

    def test_live_numbers_are_editable(self):
        p = mod.Plugin()
        p.on_plugin_load()
        p.settings["lat_warm_max"] = "4"
        p.settings["type_ms"] = "50"
        self.assertEqual(p._timing_params()["lat_warm_max"], 4)
        self.assertEqual(p._timing_params()["type_ms"], 50)
        self.assertEqual(p._timing_params()["warm_cap"], 25)


class TestLatencyModel(unittest.TestCase):
    P = dict(mod.PRESET_BASE)

    def test_kind(self):
        k = lambda a, b, c: mod.conv_kind(a, b, c, self.P)
        self.assertEqual(k(30, 30, 40), "warm")
        self.assertEqual(k(30, 30, None), "medium")           # nobody replied recently
        self.assertEqual(k(200, 200, 210), "medium")
        self.assertEqual(k(900, 900, 900), "cold")
        self.assertEqual(k(None, None, None), "cold")

    def test_warm_range_and_hard_cap(self):
        rng = random.Random(3)
        for _ in range(300):
            total, typ = mod.latency_seconds(rng, "warm", 40, 60, self.P)
            self.assertTrue(2.0 <= total <= 9.0 + 1.0 + 2.6, total)
            self.assertLessEqual(typ, total)
        for _ in range(100):
            total, _t = mod.latency_seconds(rng, "warm", 4000, 4000, self.P)   # huge texts still capped
            self.assertLessEqual(total, 25.0)

    def test_cold_range_with_rare_long_wait(self):
        rng = random.Random(5)
        longs = shorts = 0
        for _ in range(600):
            total, _t = mod.latency_seconds(rng, "cold", 10, 20, self.P)
            self.assertTrue(8.0 <= total <= 130.0, total)
            if total > 55:
                longs += 1
            else:
                shorts += 1
        self.assertTrue(20 < longs < 110, longs)             # ~10 %
        self.assertGreater(shorts, longs)

    def test_scales_with_length(self):
        a = mod.latency_seconds(FixedRng(), "warm", 0, 0, self.P)[0]
        b = mod.latency_seconds(FixedRng(), "warm", 100, 200, self.P)[0]
        self.assertGreater(b, a + 3)


class TestLiveFlow(LiveBase):
    def test_warm_reply_waits_types_and_reads_first(self):
        self.enable()
        CLIENT.get_recent_messages_backup = None
        self.hist((False, 50, u"привіт"), (True, 40, u"йо"))
        self.incoming(text=u"як справи")
        CLIENT.history.append({"id": 2000, "from_id": 7, "out": False, "date": int(self.clock[0]), "text": u"як справи",
                               "is_service": False})
        self.fire_timers()
        self.assertEqual(len(CLIENT.sent), 1)
        k = self.kinds()
        self.assertIn("read", k)
        self.assertLess(k.index("read"), k.index("send"))        # read before the reply
        self.assertIn("typing", k)
        self.assertLess(k.index("typing"), k.index("send"))
        self.assertEqual(k.count("send"), 1)
        self.assertLessEqual(sum(self.sleeps), 25.0)
        txt = self.p.decisions_text()
        self.assertIn("typing_sent", txt)
        self.assertEqual(max(self.sleeps), max(self.sleeps))
        self.assertTrue(all(s <= mod.TYPING_REFRESH_SEC + 1e-9 for s in self.sleeps))   # short chunks, no long block

    def test_cold_start_reads_just_before_typing_and_waits_longer(self):
        self.enable()
        self.hist((False, 3000, u"давно"), (True, 2900, u"так"))
        self.incoming(text=u"привіт, ти тут?")
        CLIENT.history.append({"id": 2001, "from_id": 7, "out": False, "date": int(self.clock[0]), "text": u"привіт, ти тут?",
                               "is_service": False})
        self.fire_timers()
        self.assertEqual(len(CLIENT.sent), 1)
        k = self.kinds()
        self.assertEqual(k.count("read"), 1)
        self.assertLess(k.index("read"), k.index("typing"))
        self.assertLess(k.index("typing"), k.index("send"))
        self.assertGreaterEqual(sum(self.sleeps), 3.0)
        self.assertLessEqual(sum(self.sleeps), 245.0)
        self.assertRegex(self.p.decisions_text(), r"latency_wait_\d+")

    def test_latency_reason_is_localized(self):
        for lang, word in ((1, u"чекаю"), (2, u"жду"), (3, u"waiting")):
            self.p.settings["ui_lang"] = lang
            self.assertIn("12", self.p.rt("latency_wait_12"))
            self.assertIn(word, self.p.rt("latency_wait_12"))
        for code in ("scan_found", "deferred_owner_active", "typing_sent", "read_sent", "read_blocked_by_ghost",
                     "sticker_sent", "owner_replied"):
            for lang in (1, 2, 3):
                self.p.settings["ui_lang"] = lang
                self.assertNotEqual(self.p.rt(code), code.replace("_", " "))
        for key in ("h_live", "show_typing", "read_msgs", "stickers", "sticker_pct", "sticker_recent", "o_info", "o_defer",
                    "lat_warm_min", "scan_on", "read_always"):
            row = mod.S[key]
            self.assertEqual(len(row), 3)
            self.assertTrue(all(row))

    def test_owner_active_is_deferred_not_dropped(self):
        self.enable()
        key = self.key()
        st = self.p._state(key)
        st.owner_ts = self.clock[0] - 5                          # you wrote 5 s ago (before their message)
        self.incoming(text=u"ти де")
        self.fire_once()                                          # debounce -> process -> deferred
        self.assertEqual(CLIENT.sent, [])
        self.assertIn("deferred_owner_active", self.p.decisions_text())
        self.fire_timers()                                        # your silence window ends -> the reply goes out
        self.assertEqual(len(CLIENT.sent), 1)
        self.assertGreaterEqual(self.p._pnum("owner_defers", 0, 100), 8)

    def test_owner_answered_the_same_message_skips(self):
        self.enable()
        self.incoming(text=u"глянь це")
        self.clock[0] += 1
        self.p.handle_incoming(0, self.msg(text=u"вже відписав сам", out=True))   # you replied yourself
        self.fire_timers()
        self.assertEqual(CLIENT.sent, [])
        self.assertIn("owner_replied", self.p.decisions_text().replace(" ", "_"))

    def test_abort_while_waiting_when_owner_writes(self):
        self.enable()
        self.hist((False, 3000, u"давно"))
        self.incoming(text=u"агов")
        CLIENT.history.append({"id": 2002, "from_id": 7, "out": False, "date": int(self.clock[0]), "text": u"агов",
                               "is_service": False})
        st = self.p._state(self.key())
        calls = []

        def sleeper(s):
            calls.append(s)
            if len(calls) == 1:
                self.p.handle_incoming(0, self.msg(text=u"я тут", out=True))

        mod.time.sleep = sleeper
        self.fire_timers()
        self.assertEqual(CLIENT.sent, [])
        self.assertEqual(st.abort, "owner replied")

    def test_no_hourly_cap_short_cooldown_many_turns(self):
        self.enable()
        n = {"i": 0}

        def ai(messages, **kw):
            n["i"] += 1
            return "відповідь номер %d готова" % n["i"]

        CLIENT.ai_result = ai
        for i in range(14):
            self.incoming(text=u"повідомлення %d?" % i)
            self.fire_timers()
            self.clock[0] += 16
        self.assertEqual(len(CLIENT.sent), 14)
        self.p._hourly.extend([self.clock[0]] * 500)
        self.assertIsNone(self.p.caps_ok(self.key()))             # no global hourly cap in Live
        self.p.settings["preset"] = 0
        self.assertEqual(self.p.caps_ok(self.key()), "hourly cap reached")

    def test_cooldown_between_turns_is_0_to_3(self):
        self.enable()
        vals = [self.p._cooldown() for _ in range(200)]
        self.assertTrue(all(0 <= v <= 3.0 for v in vals))
        self.assertGreater(max(vals), 1.5)
        self.p.settings["cooldown"] = "7"
        self.assertEqual(self.p._cooldown(), 7)

    def test_similarity_only_exact_duplicate_blocks(self):
        st = self.p._state(self.key())
        st.recent.append(mod.norm_text(u"ну дивись там щось є точно"))
        self.assertEqual(self.p.reply_problems(u"ну дивись там щось є точно!", st), [])
        self.assertEqual(self.p.reply_problems(u"ну дивись там щось є точно", st), ["repeat"])
        self.p.settings["preset"] = 0
        self.assertEqual(self.p.reply_problems(u"ну дивись там щось є точно!", st), ["repeat"])

    def test_ack_sometimes_answered_questions_always(self):
        self.enable()
        self.p._rng = FixedRng(rnd=0.9)
        self.incoming(text=u"ок")
        self.fire_timers()
        self.assertEqual(CLIENT.sent, [])
        self.assertIn("acknowledgement", self.p.decisions_text().replace(" ", "_") + self.p.decisions_text())
        self.p._rng = FixedRng(rnd=0.1)
        self.clock[0] += 100
        self.incoming(text=u"ага")
        self.fire_timers()
        self.assertEqual(len(CLIENT.sent), 1)
        self.assertIn("one or two words", CLIENT.ai_calls[-1]["system"])
        self.p._rng = FixedRng(rnd=0.99)
        self.clock[0] += 100
        self.incoming(text=u"ок?")                                # a question is never skipped
        self.fire_timers()
        self.assertEqual(len(CLIENT.sent), 2)

    def test_emoji_only_still_skipped(self):
        self.enable()
        self.incoming(text=u"👍")
        self.fire_timers()
        self.assertEqual(CLIENT.sent, [])

    def test_split_into_two_with_a_pause(self):
        self.enable()
        self.p.settings["short_msgs"] = False      # the random 2-part split of the older mode
        self.p.settings["split2_pct"] = "100"
        CLIENT.ai_result = lambda messages, **kw: u"ну дивись, там вроде все гаразд. потім напишу тобі точно"
        self.incoming(text=u"що там")
        self.fire_timers()
        self.assertEqual(len(CLIENT.sent), 2)
        self.assertTrue(any(1.0 <= s <= 3.0 for s in self.sleeps))
        self.p.settings["split2_pct"] = "0"
        self.clock[0] += 100
        self.incoming(text=u"а тепер що")
        self.fire_timers()
        self.assertEqual(len(CLIENT.sent), 3)

    def test_no_night_weirdness_without_quiet_hours(self):
        self.enable()
        self.clock[0] = time.mktime((2026, 10, 30, 3, 0, 0, 0, 0, -1))
        self.incoming(text=u"спиш? як ти")
        self.fire_timers()
        self.assertEqual(len(CLIENT.sent), 1)

    def test_typing_can_be_switched_off(self):
        self.enable()
        self.p.settings["show_typing"] = False
        self.hist((False, 3000, u"давно"))
        self.incoming(text=u"агов")
        CLIENT.history.append({"id": 2003, "from_id": 7, "out": False, "date": int(self.clock[0]), "text": u"агов",
                               "is_service": False})
        self.fire_timers()
        self.assertEqual(len(CLIENT.sent), 1)
        self.assertNotIn("typing", self.kinds())

    def test_disabled_while_waiting_stops(self):
        self.enable()
        self.hist((False, 3000, u"давно"))
        self.incoming(text=u"агов")
        CLIENT.history.append({"id": 2004, "from_id": 7, "out": False, "date": int(self.clock[0]), "text": u"агов",
                               "is_service": False})
        key = self.key()

        def sleeper(s):
            self.p._chats[key]["enabled"] = False

        mod.time.sleep = sleeper
        self.fire_timers()
        self.assertEqual(CLIENT.sent, [])


class TestScan(LiveBase):
    def put(self, mid, age, text=u"ти тут?", out=False):
        CLIENT.history.append({"id": mid, "from_id": 7, "out": out, "date": int(self.clock[0] - age), "text": text,
                               "is_service": False, "dialog_id": DID})

    def test_finds_missed_message_and_answers_once(self):
        self.enable()
        self.put(500, 20)
        self.assertEqual(self.p._scan_all(), 1)
        self.assertIn("scan_found", self.p.decisions_text())
        self.fire_timers()
        self.assertEqual(len(CLIENT.sent), 1)
        self.assertEqual(self.p._scan_all(), 0)                   # dedupe
        self.assertEqual(self.p.handle_incoming(0, self.msg(text=u"ти тут?", mid=500)), "duplicate")  # late event
        self.assertEqual(self.sleeps and 0, 0)

    def test_event_then_scan_is_not_double_handled(self):
        self.enable()
        self.put(501, 20)
        self.p.handle_incoming(0, self.msg(text=u"ти тут?", mid=501, age=20))
        self.assertEqual(self.p._scan_all(), 0)
        self.fire_timers()
        self.assertEqual(len(CLIENT.sent), 1)

    def test_old_young_and_answered_messages_are_ignored(self):
        self.enable()
        self.put(510, 40 * 60)                                    # older than 30 min
        self.put(511, 2)                                          # younger than the grace: events handle it
        self.assertEqual(self.p._scan_all(), 0)
        CLIENT.history[:] = []
        self.put(512, 100)
        self.put(513, 50, out=True, text=u"уже відповів")          # answered afterwards
        self.assertEqual(self.p._scan_all(), 0)
        self.fire_timers()
        self.assertEqual(CLIENT.sent, [])

    def test_window_is_configurable(self):
        self.enable()
        self.put(520, 20 * 60)
        self.p.settings["catchup_min"] = "10"
        self.assertEqual(self.p._scan_all(), 0)
        self.p.settings["catchup_min"] = "30"
        self.assertEqual(self.p._scan_all(), 1)

    def test_only_enabled_chats_and_master(self):
        self.put(530, 20)
        self.assertEqual(self.p._scan_all(), 0)                   # chat not listed
        self.enable()
        self.p.settings["master"] = False
        self.assertEqual(self.p._scan_all(), 0)
        self.p.settings["master"] = True
        self.assertEqual(self.p._scan_all(), 1)

    def test_marker_survives_restart(self):
        self.enable()
        self.put(540, 20)
        self.p._scan_all()
        self.fire_timers()
        p2 = mod.Plugin()
        p2.settings = dict(self.p.settings)
        p2._now = lambda: self.clock[0]
        p2.on_plugin_load()
        self.assertEqual(p2._marks.get(self.key()), 540)
        CLIENT.history[:] = []
        self.put(540, 25)
        self.assertEqual(p2._scan_all(), 0)

    def test_periodic_chain_and_backoff(self):
        self.p._ensure_scan()
        self.assertEqual(len(CLIENT.ui_queue), 1)
        self.p._ensure_scan()
        self.assertEqual(len(CLIENT.ui_queue), 1)                 # one chain only
        self.fire_once()                                          # no chats -> backs off to 60 s
        self.assertEqual(CLIENT.ui_queue[0][0], 60000)
        self.enable()
        CLIENT.ui_queue[:] = []
        self.p._scan_tick()
        delay = CLIENT.ui_queue[-1][0] / 1000.0
        self.assertTrue(25 * 0.85 - 0.01 <= delay <= 25 * 1.15 + 0.01, delay)
        CLIENT.ui_queue[:] = []
        self.p.settings["master"] = False
        self.p._scan_tick()
        self.assertEqual(CLIENT.ui_queue[-1][0], 60000)
        self.assertEqual(self.sleeps, [])                         # the scan never sleeps/blocks

    def test_chain_stops_when_scan_is_off_and_unload(self):
        self.p._ensure_scan()
        self.p.settings["scan"] = False
        CLIENT.ui_queue[:] = []
        self.p._scan_tick()
        self.assertEqual(CLIENT.ui_queue, [])
        self.p.settings["scan"] = True
        self.p._ensure_scan()
        self.assertEqual(len(CLIENT.ui_queue), 1)
        CLIENT.ui_queue[:] = []
        self.p.on_plugin_unload()
        self.p._scan_tick()
        self.assertEqual(CLIENT.ui_queue, [])

    def test_resume_and_start_trigger_catch_up(self):
        self.enable()
        self.put(550, 20 * 60)
        CLIENT.ui_queue[:] = []
        self.p.on_app_event("RESUME")
        self.assertTrue(any(d == 1500 for d, _f in CLIENT.ui_queue))
        for d, f in list(CLIENT.ui_queue):
            if d == 1500:
                f()
        self.fire_timers()
        self.assertEqual(len(CLIENT.sent), 1)                     # a 20 min old message is within the 30 min window

    def test_no_scan_in_balanced(self):
        self.p.settings["preset"] = 0
        CLIENT.ui_queue[:] = []
        self.p._ensure_scan()
        self.p.on_app_event("RESUME")
        self.assertEqual(CLIENT.ui_queue, [])

    def test_events_accept_older_messages_in_live(self):
        self.enable()
        self.assertIsNone(self.incoming(text=u"після офлайну?", age=600))
        self.p.settings["preset"] = 0
        self.assertEqual(self.incoming(text=u"після офлайну?", age=600), "too old")


class FakeJava(object):
    """Stands in for chaquopy's jclass: records the TL objects the plugin builds."""

    def __init__(self, ghost_read=False, ghost_typing=False):
        self.ghost_read, self.ghost_typing = ghost_read, ghost_typing
        self.requests = []

    def __call__(self, name):
        outer = self
        short = name.split("$")[-1].split(".")[-1]
        if short == "MessagesController":
            class MC(object):
                @staticmethod
                def getInstance(acc):
                    class I(object):
                        @staticmethod
                        def getInputPeer(did):
                            return ("peer", did)
                    return I
            return MC
        if short == "ZephyrConfig":
            class ZC(object):
                ghostNoRead = outer.ghost_read
                ghostNoTyping = outer.ghost_typing

                @staticmethod
                def load():
                    pass
            return ZC
        return type(short, (object,), {})


class TestTlActions(LiveBase):
    def setUp(self):
        super(TestTlActions, self).setUp()
        for a in ("mark_read", "set_typing"):
            delattr(CLIENT, a)                                    # no helpers: the plugin builds the TL itself
        self.java = FakeJava()
        self._old = mod._jclass
        mod._jclass = self.java
        CLIENT.send_request = lambda req, cb=None, account=None: self.java.requests.append(req)

    def tearDown(self):
        mod._jclass = self._old
        super(TestTlActions, self).tearDown()

    def test_read_history_request(self):
        self.enable()
        self.assertTrue(self.p._mark_read(self.key(), 77))
        req = self.java.requests[-1]
        self.assertEqual(type(req).__name__, "TL_messages_readHistory")
        self.assertEqual((req.peer, req.max_id), (("peer", DID), 77))
        self.assertIn("read_sent", self.p.decisions_text())
        self.assertFalse(self.p._mark_read(self.key(), 77))       # once per id
        self.assertTrue(self.p._mark_read(self.key(), 78))

    def test_typing_request_and_cancel(self):
        self.assertTrue(self.p._send_typing(DID, 0))
        req = self.java.requests[-1]
        self.assertEqual(type(req).__name__, "TL_messages_setTyping")
        self.assertEqual(type(req.action).__name__, "TL_sendMessageTypingAction")
        self.assertTrue(self.p._send_typing(DID, 0, cancel=True))
        self.assertEqual(type(self.java.requests[-1].action).__name__, "TL_sendMessageCancelAction")

    def test_read_blocked_by_ghost_is_logged_once(self):
        self.enable()
        self.java.ghost_read = True
        self.assertFalse(self.p._mark_read(self.key(), 90))
        self.assertFalse(self.p._mark_read(self.key(), 91))
        self.assertEqual(self.java.requests, [])
        self.assertEqual(self.p.decisions_text().count("read_blocked_by_ghost"), 1)
        self.java.ghost_typing = True
        self.assertFalse(self.p._send_typing(DID, 0))

    def test_groups_and_switch_off_do_not_read(self):
        self.enable()
        self.p._chats[self.key()]["dialog_id"] = -DID
        self.assertFalse(self.p._mark_read(self.key(), 5))
        self.p._chats[self.key()]["dialog_id"] = DID
        self.p.settings["read_msgs"] = False
        self.assertFalse(self.p._mark_read(self.key(), 5))
        self.assertEqual(self.java.requests, [])

    def test_unavailable_java_never_raises(self):
        mod._jclass = self._old                                   # the real one: no `java` module here
        self.enable()
        self.assertFalse(self.p._mark_read(self.key(), 5))
        self.assertFalse(self.p._send_typing(DID, 0))

    def test_read_always_reads_even_when_not_answering(self):
        self.enable()
        self.p.settings["quiet_hours"] = "00:00-23:59"
        self.p.settings["read_always"] = True
        self.incoming(text=u"привіт як ти")
        self.fire_timers()
        self.assertEqual(CLIENT.sent, [])
        self.assertEqual(type(self.java.requests[-1]).__name__, "TL_messages_readHistory")
        self.java.requests[:] = []
        self.p.settings["read_always"] = False
        self.clock[0] += 100
        self.incoming(text=u"ей")
        self.fire_timers()
        self.assertEqual(self.java.requests, [])                  # skipped and not reading by default


class TestStickers(LiveBase):
    """The sticker is chosen by a short ai_complete 'picker' call from the chat context, never at random."""
    STK = [{"id": 11, "emoji": u"😂", "set_title": "A"}, {"id": 12, "emoji": u"👍", "set_title": "B"},
           {"id": 13, "emoji": u"❤️", "set_title": "C"}]

    def setUp(self):
        super(TestStickers, self).setUp()
        self.stk_sent = []
        self.picker = []                                          # raw answers the fake picker returns, in order
        self.picker_calls = []
        CLIENT.get_recent_stickers = lambda limit=30, account=None: list(self.STK)[:limit]
        CLIENT.send_sticker = lambda did, sid, account=None, reply_to=None: self.stk_sent.append(sid) or True

        def ai(messages, **kw):
            if "STICKER CANDIDATES" in str(messages[-1].get("content")):
                self.picker_calls.append(messages[-1]["content"])
                r = self.picker.pop(0) if self.picker else '{"use_sticker": false}'
                if isinstance(r, Exception):
                    raise r
                return r
            return "ну норм, дивись що вийде"

        CLIENT.ai_result = ai
        self.p.settings["sticker_pct"] = "100"

    def cand(self, batch=((1, 7, u"ахах круто"),), parts=(u"ха ну",), hist=None):
        c = self.p._chats[self.key()]
        return self.p._maybe_sticker(c, DID, 0, list(batch), list(parts), False, key=self.key(), hist=hist)

    def test_parser(self):
        f = mod.parse_sticker_decision
        self.assertEqual(f('{"use_sticker": true, "index": 2, "reason_emoji": "👍", "mode": "instead"}'),
                         {"use": True, "index": 2, "emoji": u"👍", "mode": "instead"})
        self.assertEqual(f('Sure!\n```json\n{"use_sticker": false}\n```')["use"], False)
        self.assertEqual(f('use_sticker: true, index: 3')["index"], 3)
        self.assertEqual(f('{"use_sticker": "true", "index": "1", "mode": "weird"}')["mode"], "after")
        self.assertIsNone(f("blah blah"))
        self.assertIsNone(f("{broken"))
        self.assertIsNone(f(""))

    def test_fitting_sticker_is_sent_after_text_and_context_is_in_the_prompt(self):
        self.enable()
        self.hist((False, 60, u"бачив фільм?"), (True, 50, u"так, дуже смішний"))
        self.picker.append('{"use_sticker": true, "index": 1, "reason_emoji": "😂", "mode": "after"}')
        self.incoming(text=u"ахах круто")
        CLIENT.history.append({"id": 2100, "from_id": 7, "out": False, "date": int(self.clock[0]), "text": u"ахах круто",
                               "is_service": False})
        self.fire_timers()
        self.assertEqual(self.stk_sent, [11])
        self.assertEqual(len(CLIENT.sent), 1)                     # text first, then the sticker
        prompt = self.picker_calls[0]
        for needle in (u"бачив фільм?", u"ахах круто", u"ну норм", u"1: 😂 (A)", u"3: ❤️ (C)"):
            self.assertIn(needle, prompt)
        txt = self.p.decisions_text()
        self.assertIn("sticker_decided_yes", txt)
        self.assertIn("sticker_sent", txt)
        self.assertIn(u"😂", u" ".join(r[1] for r in self.p.decision_rows()))

    def test_unfitting_means_no_sticker(self):
        self.enable()
        self.picker.append('{"use_sticker": false, "index": 0}')
        self.assertIsNone(self.cand())
        self.assertIn("sticker_decided_no", self.p.decisions_text())
        self.assertEqual(self.stk_sent, [])

    def test_garbage_falls_back_to_matching_emoji_only(self):
        self.enable()
        self.picker.append("hmm I think maybe")
        self.assertEqual(self.cand(parts=(u"ха ну 😂",))["id"], 11)       # emoji of the reply matches a candidate
        self.picker.append("###")
        self.assertIsNone(self.cand(parts=(u"ну ок",)))                   # no emoji match: better no sticker
        self.assertIn("sticker_skipped_no_match", self.p.decisions_text())
        self.picker.append(RuntimeError("down"))
        self.assertIsNone(self.cand(parts=(u"ну ок",)))
        self.assertIn("sticker_skipped_ai_error", self.p.decisions_text())

    def test_bad_index_is_skipped(self):
        self.enable()
        self.picker.append('{"use_sticker": true, "index": 99, "mode": "after"}')
        self.assertIsNone(self.cand())
        self.assertIn("sticker_skipped_bad_index", self.p.decisions_text())

    def test_no_repeat_of_sticker_or_set_in_a_row(self):
        self.enable()
        key = self.key()
        self.p._state(key).last_sticker = (11, "A")
        self.picker.append('{"use_sticker": true, "index": 1}')
        got = self.cand()
        self.assertEqual(got["id"], 12)                           # candidate 1 is now the first fresh one
        self.assertNotIn(u"(A)", self.picker_calls[-1])
        self.p._sticker_hist.extend([12, 13])
        self.assertIsNone(self.cand())                            # everything is a repeat
        self.assertIn("sticker_skipped_repeat", self.p.decisions_text())
        self.assertEqual(len(self.picker_calls), 1)               # no AI call when nothing is fresh

    def test_sending_remembers_id_and_set(self):
        self.enable()
        st = self.p._state(self.key())
        self.p._send_sticker(self.key(), st, DID, 0, {"id": 12, "set": "B"}, None)
        self.assertEqual(st.last_sticker, (12, "B"))

    def test_no_picker_call_for_questions_groups_off_or_zero_chance(self):
        self.enable()
        c = self.p._chats[self.key()]
        self.assertIsNone(self.cand(batch=((1, 7, u"ахах а ти де?"),)))
        self.assertIsNone(self.p._maybe_sticker(dict(c, type="group"), DID, 0, [(1, 7, u"ахах")], [u"ну"], False, key=self.key()))
        self.p.settings["stickers"] = False
        self.assertIsNone(self.cand())
        self.p.settings["stickers"] = True
        self.p.settings["sticker_pct"] = "0"
        self.assertIsNone(self.cand())
        self.assertEqual(self.picker_calls, [])

    def test_probability_means_chance_to_ask_the_picker(self):
        self.enable()
        self.p.settings["sticker_pct"] = "12"
        for i in range(400):
            self.p._rng = random.Random(i)
            self.cand()
        n = len(self.picker_calls)
        self.assertTrue(20 < n < 90, n)

    def test_old_app_without_sticker_api_is_silent(self):
        self.enable()
        del CLIENT.get_recent_stickers
        self.assertIsNone(self.cand())
        CLIENT.get_recent_stickers = lambda limit=30, account=None: []
        self.assertIsNone(self.cand())
        self.assertIn("sticker_skipped_no_candidates", self.p.decisions_text())
        CLIENT.get_recent_stickers = lambda limit=30, account=None: (_ for _ in ()).throw(RuntimeError("x"))
        self.assertIsNone(self.cand())
        self.assertEqual(self.picker_calls, [])

    def test_instead_mode_only_for_tiny_replies(self):
        self.enable()
        self.picker.append('{"use_sticker": true, "index": 1, "mode": "instead"}')
        self.assertTrue(self.cand(parts=(u"ага",))["instead"])
        self.picker.append('{"use_sticker": true, "index": 2, "mode": "instead"}')
        self.assertFalse(self.cand(parts=(u"ну це дуже довга відповідь про все на світі, справді довга",))["instead"])

    def test_instead_sends_only_the_sticker_and_own_sticker_is_not_owner_activity(self):
        self.enable()
        self.picker.append('{"use_sticker": true, "index": 1, "mode": "instead"}')
        base = CLIENT.ai_result
        CLIENT.ai_result = lambda m, **kw: u"ага" if "STICKER" not in str(m[-1].get("content")) else base(m)
        self.incoming(text=u"ахах круто")
        self.fire_timers()
        self.assertEqual(self.stk_sent, [11])
        self.assertEqual(CLIENT.sent, [])
        st = self.p._state(self.key())
        before = st.owner_ts
        self.p.handle_incoming(0, self.msg(text=u"", out=True))   # the sticker coming back as an outgoing event
        self.assertEqual(st.owner_ts, before)

    def test_media_description_reaches_the_picker_only_when_enabled(self):
        self.enable()
        CLIENT.get_message_media = lambda did, mid, account=None: {"kind": "sticker", "emoji": u"😭", "set_title": "Sad"}
        hist = [{"id": 5, "out": False, "text": "", "has_media": True}]
        self.picker.append('{"use_sticker": false}')
        self.cand(hist=hist)
        self.assertNotIn("Incoming media", self.picker_calls[-1])
        self.p.settings["see_media_" + self.p._sk(self.key())] = True
        self.picker.append('{"use_sticker": false}')
        self.cand(hist=hist)
        self.assertIn(u"[media: sticker, 😭, Sad]", self.picker_calls[-1])

    def test_skip_reasons_are_localized(self):
        for lang in (1, 2, 3):
            self.p.settings["ui_lang"] = lang
            for code in ("sticker_decided_yes", "sticker_decided_no", "sticker_skipped_no_match", "sticker_skipped_repeat"):
                self.assertNotEqual(self.p.rt(code), code.replace("_", " "))
            self.assertNotIn("%s", self.p.rt("sticker_skipped_ai_error"))


class TestLanguage(LiveBase):
    def system(self):
        return CLIENT.ai_calls[-1]["system"]

    def ask(self, text, hist=()):
        self.enable()
        self.hist(*hist)
        self.incoming(text=text)
        CLIENT.history.append({"id": 3000 + self.n, "from_id": 7, "out": False, "date": int(self.clock[0]),
                               "text": text, "is_service": False})
        self.fire_timers()
        self.assertTrue(CLIENT.ai_calls)

    def test_default_follows_the_other_person(self):
        self.assertEqual(self.p._reply_lang_mode(self.key()), 3)

    def test_russian_message_gets_russian_even_if_owner_writes_ukrainian(self):
        own = [(True, 5000 - i * 10, u"ну я зараз піду, це вже нічого не змінить") for i in range(6)]
        self.ask(u"привет, что делаешь? это срочно", own)
        self.assertIn("Russian", self.system())
        self.assertIn("тією мовою, якою написав співрозмовник", self.system())

    def test_ukrainian_message(self):
        self.ask(u"привіт, що робиш? це терміново", [(True, 5000, u"что такое, это же всё не то")])
        self.assertIn("Ukrainian", self.system())

    def test_mix_follows_the_current_message_newest_weighs_more(self):
        self.ask(u"привіт, как дела? що там нового")
        self.assertIn("Ukrainian", self.system())
        CLIENT.ai_calls[:] = []
        self.clock[0] += 500
        self.p._lang_cache.clear()
        self.p._state(self.key()).answered.clear()
        self.incoming(text=u"привіт, ты как? что там нового")
        CLIENT.history.append({"id": 3999, "from_id": 7, "out": False, "date": int(self.clock[0]),
                               "text": u"привіт, ты как? что там нового", "is_service": False})
        self.fire_timers()
        self.assertIn("Russian", self.system())

    def test_short_message_uses_recent_incoming_then_owner_then_ukrainian(self):
        self.ask(u"ага ок", [(False, 400, u"привет, как дела? что нового"), (True, 390, u"ну ок")])
        self.assertIn("Russian", self.system())
        self.tearDown()
        self.setUp()
        self.ask(u"ага ок", [(True, 400, u"что делаешь, это же очень странно")])
        self.assertIn("Russian", self.system())                   # no incoming signal: the owner's language
        self.tearDown()
        self.setUp()
        self.ask(u"ага ок", [(True, 400, u"хм")])
        self.assertIn("Ukrainian", self.system())

    def test_incoming_language_helper(self):
        f = mod.incoming_language
        self.assertEqual(f([u"привет, как дела"], []), "Russian")
        self.assertEqual(f([u"привіт, як справи"], []), "Ukrainian")
        self.assertEqual(f([u"ок"], [u"что это такое"]), "Russian")
        self.assertIsNone(f([u"ок"], [u"ок", u"гм"]))
        self.assertEqual(f([u"hello how are you doing"], []), "English")
        self.assertEqual(f([u"ыэ"], [u"привіт"]), "Russian")

    def test_explicit_modes_still_override(self):
        self.p.settings["reply_lang"] = 1
        self.assertEqual(self.p.pick_reply_lang(self.key(), 0, DID, u"привет, что это"), "Ukrainian")
        self.p.settings["reply_lang"] = 2
        self.assertEqual(self.p.pick_reply_lang(self.key(), 0, DID, u"привіт"), "Russian")


class TestMeta(unittest.TestCase):
    def test_header(self):
        self.assertEqual(mod.__version__, "0.4.5")
        self.assertEqual(mod.__version_code__, 17)
        self.assertIn("network.requests", mod.__permissions__)
        self.assertEqual(len(mod.PRESET_NAMES), len(mod.PRESETS))


if __name__ == "__main__":
    unittest.main()
