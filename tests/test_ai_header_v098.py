"""ai_autoreply 0.9.8: header button with a quick menu, Neon usage line of the memory scale; fake bridge only."""
from test_ai_autoreply import Base, CLIENT, DID, mod


class HeaderBase(Base):
    NAMES = ("HEADER_BUTTON", "MEMORY_API_VERSION", "ai_memory_status", "ai_memory_consent", "ai_memory_write",
             "ai_memory_context", "ai_memory_delete", "ai_memory_cancel")

    def setUp(self):
        super().setUp()
        self._orig = {n: (hasattr(CLIENT, n), getattr(CLIENT, n, None)) for n in self.NAMES}
        self._mt = getattr(mod.MenuType, "CHAT_HEADER_BUTTON", None)

    def tearDown(self):
        for n, (ex, v) in self._orig.items():
            if ex:
                setattr(CLIENT, n, v)
            elif hasattr(CLIENT, n):
                delattr(CLIENT, n)
        if self._mt is None and hasattr(mod.MenuType, "CHAT_HEADER_BUTTON"):
            delattr(mod.MenuType, "CHAT_HEADER_BUTTON")
        super().tearDown()

    def hdr_items(self):
        return [m for m in getattr(self.p, "menu", []) if m.key == "ai_autoreply_hdr"]


class TestHeaderButton(HeaderBase):
    def test_not_added_on_old_app(self):
        self.p._header_button()
        self.assertEqual(self.hdr_items(), [])

    def test_added_when_supported(self):
        mod.MenuType.CHAT_HEADER_BUTTON = "HEADER"
        CLIENT.HEADER_BUTTON = True
        self.p._header_button()
        self.assertEqual(len(self.hdr_items()), 1)
        self.p._header_button(replace=True)
        self.assertEqual(len(self.hdr_items()), 1)

    def test_quick_actions_for_a_chat_that_is_off(self):
        acts = self.p._quick_actions(0, DID)
        self.assertEqual(len(acts), 1)

    def test_quick_actions_for_an_active_chat(self):
        self.enable()
        labels = [a[0] for a in self.p._quick_actions(0, DID)]
        self.assertEqual(len(labels), 5)
        self.assertEqual(len(set(labels)), 5)

    def test_mode_action_toggles_draft_and_auto(self):
        self.enable()
        key = self.key()
        acts = dict((i, a) for i, a in enumerate(self.p._quick_actions(0, DID)))
        acts[1][1]()
        self.assertEqual(self.p._chat_mode(key), mod.MODE_DRAFT)
        self.p._quick_actions(0, DID)[1][1]()
        self.assertEqual(self.p._chat_mode(key), mod.MODE_AUTO)

    def test_click_shows_dialog_with_actions_and_watch_runs_the_chosen_one(self):
        self.enable()
        shown = []
        self.p._show_quick = lambda ctx, labels, acts: shown.append((labels, acts))
        self.p.on_header_click({"account": 0, "dialog_id": DID})
        self.assertEqual(len(shown), 1)
        ran = []
        acts = [("a", lambda: ran.append("a")), ("b", lambda: ran.append("b"))]
        self.p._watch_quick({"which": 1, "closed": True}, self.clock[0] + 100, acts)
        self.fire_timers()
        self.assertEqual(ran, ["b"])
        self.p._watch_quick({"which": 7}, self.clock[0] + 100, acts)
        self.fire_timers()
        self.assertEqual(ran, ["b"])

    def test_watch_stops_on_dismiss_without_choice(self):
        ran = []
        self.p._watch_quick({"which": None, "closed": True}, self.clock[0] + 100, [("a", lambda: ran.append(1))])
        self.fire_timers()
        self.assertEqual(ran, [])


class TestCloudUsageLine(HeaderBase):
    def setUp(self):
        super().setUp()
        self.enable()
        self.key_ = self.key()
        self.usage = None
        self.owner = 9001
        self.p._memory_owner_id = lambda account: self.owner
        CLIENT.MEMORY_API_VERSION = 1
        for n in ("ai_memory_consent", "ai_memory_write", "ai_memory_context", "ai_memory_delete", "ai_memory_cancel"):
            setattr(CLIENT, n, lambda *a, **k: {})
        CLIENT.ai_memory_status = self.status
        self.binding = "a" * 64
        self.p._cloud_save(self.key_, 0, {"ownerId": "9001", "binding": self.binding, "enabled": True, "revision": 1,
                                          "startTs": 1, "deletePending": False, "raw": False})

    def status(self, account, timeout=10):
        out = {"ownerId": str(self.owner), "ownerMatch": True, "binding": self.binding}
        if self.usage is not None:
            out["usage"] = self.usage
        return out

    def good(self):
        return {"scopes": 11, "chats": [{"dialogId": str(DID), "topicId": 0, "messages": 143,
                                         "messagesUntil": "2026-12-05T10:00:00.000Z"}]}

    def test_line_after_the_background_read(self):
        self.usage = self.good()
        self.assertEqual(self.p._cloud_usage_line(self.key_), "")
        self.fire_timers()
        line = self.p._cloud_usage_line(self.key_)
        self.assertIn("143", line)
        self.assertIn("11", line)
        self.assertIn("05.12", line)

    def test_no_usage_means_no_line(self):
        self.p._cloud_usage_line(self.key_)
        self.fire_timers()
        self.assertEqual(self.p._cloud_usage_line(self.key_), "")

    def test_garbage_usage_is_ignored(self):
        self.usage = {"scopes": 999, "chats": "x"}
        self.p._cloud_usage_line(self.key_)
        self.fire_timers()
        self.assertEqual(self.p._cloud_usage_line(self.key_), "")

    def test_other_owner_is_ignored(self):
        self.usage = self.good()
        orig = self.status
        CLIENT.ai_memory_status = lambda a, timeout=10: dict(orig(a), ownerId="777")
        self.p._cloud_usage_line(self.key_)
        self.fire_timers()
        self.assertEqual(self.p._cloud_usage_line(self.key_), "")

    def test_cache_does_not_refetch_within_five_minutes(self):
        self.usage = self.good()
        calls = []
        orig = CLIENT.ai_memory_status
        CLIENT.ai_memory_status = lambda a, timeout=10: calls.append(1) or orig(a, timeout)
        self.p._cloud_usage_line(self.key_)
        self.fire_timers()
        self.p._cloud_usage_line(self.key_)
        self.p._cloud_usage_line(self.key_)
        self.fire_timers()
        self.assertEqual(len(calls), 1)

    def test_off_chat_makes_no_call(self):
        self.p._cloud_save(self.key_, 0, {"ownerId": "9001", "binding": self.binding, "enabled": False, "revision": 2,
                                          "startTs": 1, "deletePending": False})
        calls = []
        CLIENT.ai_memory_status = lambda a, timeout=10: calls.append(1) or {}
        self.assertEqual(self.p._cloud_usage_line(self.key_), "")
        self.fire_timers()
        self.assertEqual(calls, [])
