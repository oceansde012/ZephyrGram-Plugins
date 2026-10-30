"""Local harness for plugins/ai_autoreply with a fake `zephyr` module.

Run: python -m unittest discover -s tests -v
"""
import importlib.machinery
import importlib.util
import os
import sys
import time
import types
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PLUGIN = os.path.join(ROOT, "plugins", "ai_autoreply", "ai_autoreply.plugin")


def install_fake_zephyr():
    z = types.ModuleType("zephyr")
    ui = types.ModuleType("zephyr.ui")
    cl = types.ModuleType("zephyr.client")

    class BasePlugin(object):
        id, name, version = "ai_autoreply", "AI auto-reply", "0.1.0"

        def __init__(self):
            self.settings = {}
            self.logs = []
            self.errors = []

        def log(self, m):
            self.logs.append(str(m))

        def error(self, e):
            self.errors.append(e)

        def get_setting(self, k, d=None):
            return self.settings.get(k, d)

        def set_setting(self, k, v):
            self.settings[k] = v

        def add_on_new_message_hook(self, priority=0):
            pass

        def add_on_send_message_hook(self, priority=0):
            self.send_hook_registered = True

        def add_updates_hook(self, name, match_substring=False, priority=0):
            self.updates_hooks = getattr(self, "updates_hooks", []) + [name]

        def add_menu_item(self, item):
            self.menu = getattr(self, "menu", []) + [item]

    class HookStrategy:
        DEFAULT, CANCEL, MODIFY, MODIFY_FINAL = 0, 1, 2, 3

    class HookResult(object):
        def __init__(self, strategy=0, **kw):
            self.strategy = strategy

    class MenuType:
        CHAT_ACTION = "CHAT_ACTION"

    class MenuItem(object):
        def __init__(self, menu_type, text, on_click, icon=None, subtext=None, priority=0,
                     condition=None, key=None):
            self.text, self.on_click, self.condition, self.key = text, on_click, condition, key

    class Item(object):
        def __init__(self, **kw):
            self.__dict__.update(kw)

    for n in ("Header", "Switch", "Input", "Selector", "Text", "Divider", "DialogPicker", "UsernameInput"):
        setattr(ui, n, type(n, (Item,), {}))

    # fake client state
    cl.ui_queue = []
    cl.sent = []
    cl.drafts = []
    cl.bulletins = []
    cl.ai_calls = []
    cl.ai_result = lambda messages, **kw: "hello back"
    cl.history = []
    cl.info = {"id": 42, "title": "Alice", "type": "user", "is_bot": False, "username": "a"}

    def run_on_ui(fn, delay_ms=0):
        cl.ui_queue.append((delay_ms, fn))

    def run_in_bg(fn):
        fn()

    def ai_complete(messages, system=None, model=None, temperature=None, timeout=60):
        cl.ai_calls.append({"messages": messages, "system": system, "model": model,
                            "temperature": temperature})
        r = cl.ai_result(messages)
        if isinstance(r, Exception):
            raise r
        return r

    cl.run_on_ui, cl.run_in_bg, cl.ai_complete = run_on_ui, run_in_bg, ai_complete
    cl.bulletin = lambda t: cl.bulletins.append(t)
    cl.get_recent_messages = lambda did, limit=20, account=None: list(cl.history)[-limit:]
    cl.get_dialog_info = lambda did, account=None: dict(cl.info)
    cl.send_text = lambda did, text, reply_to=None: cl.sent.append((did, text, reply_to))
    cl.set_draft = lambda did, text: cl.drafts.append((did, text))
    cl.clipboard = []
    cl.copy_to_clipboard = lambda text: cl.clipboard.append(text)
    cl.message_to_dict = lambda mo: dict(mo)
    cl.current_account = lambda: 0

    z.HookResult, z.HookStrategy = HookResult, HookStrategy
    z.BasePlugin, z.MenuItem, z.MenuType, z.client, z.ui = BasePlugin, MenuItem, MenuType, cl, ui
    sys.modules["zephyr"], sys.modules["zephyr.ui"], sys.modules["zephyr.client"] = z, ui, cl
    return cl


CLIENT = install_fake_zephyr()
_loader = importlib.machinery.SourceFileLoader("ai_autoreply_plugin", PLUGIN)
_spec = importlib.util.spec_from_loader("ai_autoreply_plugin", _loader)
mod = importlib.util.module_from_spec(_spec)
_loader.exec_module(mod)

DID = 42


class Base(unittest.TestCase):
    def setUp(self):
        c = CLIENT
        c.ui_queue[:] = []
        c.sent[:] = []
        c.drafts[:] = []
        c.bulletins[:] = []
        c.clipboard[:] = []
        c.ai_calls[:] = []
        c.history[:] = []
        c.ai_result = lambda messages, **kw: "hello back"
        c.info = {"id": DID, "title": "Alice", "type": "user", "is_bot": False, "username": "a"}
        mod.time.sleep = lambda s: None          # no real typing delay
        self.clock = [1000000.0]
        self.p = mod.Plugin()
        self.p._now = lambda: self.clock[0]
        self.p.settings["ui_lang"] = 3            # English: the older tests assert English texts
        self.p.on_plugin_load()
        self.p.settings["debounce"] = "3"
        self.p._rng.seed(1)
        self.n = 0

    def enable(self, did=DID, account=0):
        ctx = {"account": account, "dialog_id": did}
        self.assertTrue(self.p.cond_show_off(ctx))
        self.p.on_enable_click(ctx)
        self.assertTrue(self.p.is_enabled(self.p.chat_key(account, did)), CLIENT.bulletins)
        self.assertTrue(self.p.cond_show_on(ctx))

    def msg(self, text="hi", out=False, age=0, is_bot=False, from_id=7, mid=None, did=DID):
        self.n += 1
        d = {"id": mid if mid is not None else self.n, "from_id": from_id, "out": out,
             "date": int(self.clock[0] - age), "text": text, "is_bot": is_bot,
             "reply_to": None, "dialog_id": did}
        return d

    def incoming(self, **kw):
        return self.p.handle_incoming(0, self.msg(**kw))

    def fire_timers(self):
        """Advance the clock past the debounce and run due timers (bounded)."""
        for _ in range(10):
            if not CLIENT.ui_queue:
                break
            delay, fn = CLIENT.ui_queue.pop(0)
            self.clock[0] += delay / 1000.0
            fn()

    def fire_once(self):
        """Run exactly one queued timer (advancing the clock by its delay)."""
        delay, fn = CLIENT.ui_queue.pop(0)
        self.clock[0] += delay / 1000.0
        fn()

    def key(self):
        return self.p.chat_key(0, DID)


class TestAllowlist(Base):
    def test_not_in_allowlist_ignored(self):
        self.assertIsNone(self.incoming())
        self.assertEqual(CLIENT.ui_queue, [])
        self.assertEqual(CLIENT.ai_calls, [])

    def test_enable_reply_and_disable(self):
        self.enable()
        self.incoming(text="hello")
        self.fire_timers()
        self.assertEqual(len(CLIENT.sent), 1)
        self.assertTrue(CLIENT.sent[0][1].endswith("hello back"))
        self.p.on_disable_click({"account": 0, "dialog_id": DID})
        self.clock[0] += 100
        self.incoming(text="again")
        self.fire_timers()
        self.assertEqual(len(CLIENT.sent), 1)

    def test_master_switch(self):
        self.enable()
        self.p.settings["master"] = False
        self.incoming()
        self.assertEqual(CLIENT.ui_queue, [])

    def test_secret_bot_channel_refused(self):
        for info in ({"type": "secret"}, {"type": "user", "is_bot": True}, {"type": "channel"}):
            CLIENT.info = dict(info, title="x")
            self.p.on_enable_click({"account": 0, "dialog_id": DID})
            self.assertFalse(self.p.is_enabled(self.key()))

    def test_chats_persist_as_json(self):
        self.enable()
        p2 = mod.Plugin()
        p2.settings = dict(self.p.settings)
        p2.on_plugin_load()
        self.assertTrue(p2.is_enabled(self.key()))

    def test_settings_list_enabled_chat_titles(self):
        self.enable()
        texts = [getattr(i, "text", "") for i in self.p.create_settings()]
        self.assertIn("▸ Alice", texts)


class TestAddChatSettings(Base):
    def items(self):
        return {getattr(i, "key", None): i for i in self.p.create_settings() if getattr(i, "key", None)}

    def test_add_section_has_picker_and_username(self):
        it = self.items()
        self.assertEqual(type(it["add_pick"]).__name__, "DialogPicker")
        self.assertEqual(type(it["add_username"]).__name__, "UsernameInput")
        self.assertEqual(it["add_pick"].on_pick, self.p.on_chat_added)
        self.assertEqual(it["add_username"].on_resolved, self.p.on_chat_added)

    def test_friend_mode_described(self):
        texts = " ".join(str(getattr(i, "subtext", "") or "") + str(getattr(i, "text", ""))
                         for i in self.p.create_settings())
        self.assertIn("OTHER person", texts)
        self.assertIn(".ai", texts)

    def test_picked_chat_enabled_and_listed(self):
        self.p.on_chat_added(DID, "Alice")
        self.assertTrue(self.p.is_enabled(self.key()))
        sk = self.p._sk(self.key())
        self.items()["chat_" + sk].on_click()            # 0.3.4: tap the chat row to open its options
        it = self.items()
        self.assertIn("mode_" + sk, it)
        self.assertIn("remove_" + sk, it)
        self.assertEqual(it["mode_" + sk].default, mod.MODE_AUTO)

    def test_picked_refused_types(self):
        for info in ({"type": "secret"}, {"type": "channel"}, {"type": "user", "is_bot": True}):
            CLIENT.info = dict(info, title="x")
            self.p.on_chat_added(DID, "x")
            self.assertFalse(self.p.is_enabled(self.key()))
        self.assertEqual(len(CLIENT.bulletins), 3)

    def test_friend_mode_other_person_triggers_owner_silent(self):
        self.p.on_chat_added(DID, "Alice")
        self.p.settings["mode_" + self.p._sk(self.key())] = mod.MODE_COMMAND
        self.p.settings["cmd_enable"] = False          # 0.3.3: an outgoing .ai would run the owner command
        self.assertEqual(self.incoming(out=True, text=".ai hi me"), "outgoing")     # owner never triggers
        self.p.settings["cmd_enable"] = True
        self.assertEqual(self.incoming(text="just chatting"), "no command prefix")
        self.assertIsNone(self.incoming(text=".ai what is 2+2"))
        self.fire_timers()
        self.assertEqual(len(CLIENT.sent), 1)
        self.assertEqual(CLIENT.ai_calls[0]["messages"][-1]["content"], "what is 2+2")

    def test_mode_selector_and_remove(self):
        self.p.on_chat_added(DID, "Alice")
        sk = self.p._sk(self.key())
        self.p.settings["mode_" + sk] = mod.MODE_DRAFT
        self.items()["chat_" + sk].on_click()
        self.items()["remove_" + sk].on_click()
        self.assertNotIn(self.key(), self.p._chats)
        self.assertNotIn("remove_" + sk, self.items())
        self.incoming()
        self.assertEqual(CLIENT.ai_calls, [])
        self.assertEqual(self.p._chat_mode(self.key()), mod.MODE_AUTO)

    def test_adding_twice_keeps_one_entry(self):
        self.p.on_chat_added(DID, "Alice")
        self.p.on_chat_added(DID, "Alice")
        self.assertEqual(len(self.p._chats), 1)

    def test_old_app_without_picker(self):
        saved = mod.DialogPicker, mod.UsernameInput
        mod.DialogPicker = mod.UsernameInput = None
        try:
            self.assertNotIn("add_pick", self.items())
        finally:
            mod.DialogPicker, mod.UsernameInput = saved


class TestFilters(Base):
    def setUp(self):
        Base.setUp(self)
        self.enable()

    def test_outgoing_bot_empty_ignored(self):
        self.assertEqual(self.incoming(out=True), "outgoing")
        self.assertEqual(self.incoming(is_bot=True), "sender is bot")
        self.assertEqual(self.incoming(text="  "), "no text / service message")

    def test_age_filter(self):
        self.assertEqual(self.incoming(age=181), "too old")
        self.assertIsNone(self.incoming(age=179))

    def test_dedupe_by_id(self):
        self.assertIsNone(self.incoming(mid=5))
        self.assertEqual(self.incoming(mid=5), "duplicate")

    def test_command_mode(self):
        self.p.settings["mode_0_42"] = mod.MODE_COMMAND
        self.assertEqual(self.incoming(text="what's up"), "no command prefix")
        self.assertIsNone(self.incoming(text=".ai tell a joke"))
        self.fire_timers()
        self.assertEqual(CLIENT.ai_calls[0]["messages"][-1]["content"], "tell a joke")

    def test_draft_mode_sets_draft_not_send(self):
        self.p.settings["mode_0_42"] = mod.MODE_DRAFT
        self.incoming(text="hello")
        self.fire_timers()
        self.assertEqual(CLIENT.sent, [])
        self.assertEqual(CLIENT.drafts, [(DID, "hello back")])


class TestLoops(Base):
    def setUp(self):
        Base.setUp(self)
        self.enable()

    def test_identical_repeats(self):
        self.assertIsNone(self.incoming(text="ping"))
        self.assertIsNone(self.incoming(text="ping"))
        self.assertEqual(self.incoming(text="Ping "), "repeated identical text")

    def test_auto_reply_markers(self):
        self.assertEqual(self.incoming(text="\U0001F916 I am away"), "looks like an auto-reply")
        self.assertEqual(self.incoming(text="Auto-reply: busy"), "looks like an auto-reply")

    def test_reply_burst_pauses(self):
        st = self.p._state(self.key())
        for _ in range(4):
            st.replies.append(self.clock[0] - 10)
        self.assertEqual(self.incoming(text="x"), "reply burst (possible loop)")
        self.clock[0] += 200
        self.assertIsNone(self.incoming(text="y"))


class TestCaps(Base):
    def setUp(self):
        Base.setUp(self)
        self.enable()
        self.p.settings["cooldown"] = "0"

    def round(self, text):
        self.incoming(text=text)
        self.fire_timers()

    def test_cooldown(self):
        self.p.settings["cooldown"] = "20"
        self.round("one")
        self.assertEqual(len(CLIENT.sent), 1)
        self.incoming(text="two")
        # first timer fires at debounce, but the cooldown re-arms it
        self.fire_timers()
        self.assertEqual(len(CLIENT.sent), 2)
        self.assertGreaterEqual(self.clock[0] - 1000000.0, 3 + 20)

    def test_debounce_batches(self):
        self.incoming(text="a")
        self.incoming(text="b")
        self.incoming(text="c")
        self.fire_timers()
        self.assertEqual(len(CLIENT.ai_calls), 1)
        self.assertEqual(len(CLIENT.sent), 1)

    def test_daily_cap(self):
        self.p.settings["daily_cap"] = "2"
        self.p.settings["hourly_cap"] = "100"
        for i in range(4):
            self.round("msg %d" % i)
        self.assertEqual(len(CLIENT.ai_calls), 2)

    def test_hourly_cap_and_expiry(self):
        self.p.settings["hourly_cap"] = "2"
        self.p.settings["daily_cap"] = "100"
        for i in range(3):
            self.round("m%d" % i)
        self.assertEqual(len(CLIENT.ai_calls), 2)
        self.clock[0] += 3700
        self.round("later")
        self.assertEqual(len(CLIENT.ai_calls), 3)

    def test_disclosure_only_first(self):
        self.round("one")
        self.round("two")
        self.assertTrue(CLIENT.sent[0][1].startswith(mod.ROBOT))
        self.assertFalse(CLIENT.sent[1][1].startswith(mod.ROBOT))

    def test_auto_disable_after_failures(self):
        CLIENT.ai_result = lambda m, **kw: RuntimeError("boom")
        for i in range(mod.MAX_FAILURES):
            self.round("m%d" % i)
        self.assertEqual(CLIENT.sent, [])         # errors never go to the chat
        self.assertFalse(self.p.is_enabled(self.key()))

    def test_history_used_and_roles(self):
        CLIENT.history[:] = [
            {"id": 101, "from_id": 7, "out": False, "date": 1, "text": "hi", "is_bot": False},
            {"id": 102, "from_id": 1, "out": True, "date": 2, "text": "yo", "is_bot": False},
        ]
        self.round("question")
        msgs = CLIENT.ai_calls[0]["messages"]
        self.assertEqual([m["role"] for m in msgs], ["user", "assistant", "user"])
        self.assertEqual(msgs[-1]["content"], "question")


OWN = ["ну ща гляну", "та норм", "ага давай", "хз шо там", "ок бро", "ща буду", "блін забув",
       "не знаю ще", "та ладно", "ну типу так", "ага ок", "потім напишу", "ніт", "хах ну да"]


def own_history(texts=OWN):
    return [{"id": 200 + i, "from_id": 1, "out": True, "date": 10 + i, "text": t, "is_bot": False}
            for i, t in enumerate(texts)]


class TestPureHelpers(unittest.TestCase):
    def test_clean_strips_markdown_quotes_prefix_filler(self):
        c = mod.clean_humanized
        self.assertEqual(c("**ну ща** `гляну`"), "ну ща гляну")
        self.assertEqual(c("Assistant: привіт"), "привіт")
        self.assertEqual(c('"та норм"'), "та норм")
        self.assertEqual(c("«ок»"), "ок")
        self.assertEqual(c("Звісно, зараз гляну"), "зараз гляну")
        self.assertEqual(c("- один\n- два"), "один\nдва")
        self.assertEqual(c("[user 7] йо"), "йо")

    def test_cap_text_at_sentence(self):
        t = mod.cap_text("Перше речення тут. " * 10, 60)
        self.assertTrue(t.endswith("."))
        self.assertLessEqual(len(t), 60)

    def test_examples_filter(self):
        self.assertFalse(mod.eligible_example("/start"))
        self.assertFalse(mod.eligible_example(".ai hi"))
        self.assertFalse(mod.eligible_example("глянь https://x.com/a"))
        self.assertFalse(mod.eligible_example("a" * 300))
        self.assertTrue(mod.eligible_example("ну ща гляну"))

    def test_style_stats_and_rules(self):
        st = mod.compute_style(OWN)
        self.assertEqual(st["n"], len(OWN))
        self.assertGreater(st["lower_start"], 0.9)
        self.assertEqual(st["period_end"], 0)
        self.assertEqual(st["emoji_rate"], 0)
        self.assertGreater(st["uk_share"], 0.5)
        rules = " ".join(mod.style_rules(st))
        self.assertIn("lowercase", rules)
        self.assertIn("period", rules)
        self.assertIn("Do not add any", rules)
        self.assertEqual(mod.style_rules(mod.compute_style(OWN[:3])), [])

    def test_apply_style(self):
        st = mod.compute_style(OWN)
        self.assertEqual(mod.apply_style("\U0001F600 Ну ща гляну.", st), "ну ща гляну")
        self.assertEqual(mod.apply_style("OK.", st), "OK")
        self.assertEqual(mod.apply_style("Ну ща.", {"n": 2}), "Ну ща.")

    def test_split(self):
        self.assertEqual(mod.split_reply("коротко"), ["коротко"])
        long = "Це перше речення довге. Це друге речення теж. Третє. Четверте речення ось."
        parts = mod.split_reply(long)
        self.assertTrue(1 < len(parts) <= 3)
        self.assertEqual(mod.split_reply("один рядок\nдругий рядок тут"), ["один рядок", "другий рядок тут"])

    def test_typing_delay_grows(self):
        self.assertLess(mod.typing_delay_s("ок"), mod.typing_delay_s("x" * 60))
        self.assertLessEqual(mod.typing_delay_s("x" * 5000, 1.3), 2.5)

    def test_emoji_only(self):
        self.assertTrue(mod.is_emoji_only("\U0001F44D"))
        self.assertTrue(mod.is_emoji_only("..."))
        self.assertFalse(mod.is_emoji_only("ок \U0001F44D"))


class TestHumanize(Base):
    def setUp(self):
        Base.setUp(self)
        self.enable()
        self.p.settings["cooldown"] = "0"
        CLIENT.history[:] = own_history()

    def round(self, text):
        self.incoming(text=text)
        self.fire_timers()

    def test_style_in_system_prompt(self):
        self.round("привіт")
        sysmsg = CLIENT.ai_calls[0]["system"]
        self.assertIn("ща гляну", sysmsg)               # few-shot example
        self.assertIn("lowercase", sysmsg)              # derived rule
        self.assertIn("No lists", sysmsg)               # anti-AI rules
        self.assertEqual(CLIENT.ai_calls[0]["temperature"], 0.95)

    def test_custom_prompt_is_extra_layer_and_tone(self):
        self.p.settings["default_prompt"] = "Call me Vova."
        self.p.settings["tone"] = 2
        self.round("hi")
        s = CLIENT.ai_calls[0]["system"]
        self.assertIn("Call me Vova.", s)
        self.assertIn("sarcastic", s)
        self.assertIn("No lists", s)

    def test_bot_replies_not_learned(self):
        CLIENT.ai_result = lambda m, **kw: "Ну давай гляну пізніше"
        self.round("привіт")
        CLIENT.history.append({"id": 900, "from_id": 1, "out": True, "date": 99,
                               "text": "ну давай гляну пізніше", "is_bot": False})
        texts = self.p._own_texts(0, DID)
        self.assertNotIn("ну давай гляну пізніше", texts)
        self.assertIn("ща буду", texts)

    def test_learning_off_and_cache(self):
        self.p.settings["learn_style"] = False
        self.round("привіт")
        self.assertNotIn("ща гляну", CLIENT.ai_calls[0]["system"])
        self.p.settings["learn_style"] = True
        n = len(CLIENT.history)
        self.p.get_profile(self.key(), 0, DID)
        CLIENT.history[:] = []
        self.assertEqual(len(self.p.get_profile(self.key(), 0, DID)["examples"]), n)   # cached
        self.clock[0] += 31 * 60
        self.assertEqual(self.p.get_profile(self.key(), 0, DID)["examples"], [])      # expired

    def test_borrow_from_other_chats(self):
        CLIENT.history[:] = own_history(OWN[:2])
        self.p._chats["0:77"] = {"enabled": True, "account": 0, "dialog_id": 77, "title": "B", "type": "user"}
        CLIENT.history[:] = own_history(OWN[:2])
        prof = self.p.get_profile(self.key(), 0, DID)
        self.assertGreaterEqual(prof["style"]["n"], 2)

    def test_postprocess_in_delivery(self):
        CLIENT.ai_result = lambda m, **kw: "**Ну** ща гляну."
        self.round("привіт")
        self.assertTrue(CLIENT.sent[0][1].endswith("ну ща гляну"))

    def test_split_and_delays(self):
        CLIENT.ai_result = lambda m, **kw: ("Це перше речення досить довге, щоб воно точно не влізло в одну "
                                            "коротку репліку. Це друге речення теж не маленьке, тому його варто відправити окремо.")
        slept = []
        mod.time.sleep = lambda s: slept.append(s)
        self.round("привіт")
        self.assertEqual(len(CLIENT.sent), 2)
        self.assertTrue(CLIENT.sent[0][1].startswith(mod.ROBOT))
        self.assertFalse(CLIENT.sent[1][1].startswith(mod.ROBOT))
        self.assertEqual(len(slept), 2)
        self.assertTrue(0.4 <= sum(slept) <= 2.5 + 1e-9, slept)
        self.assertEqual(len(self.p._state(self.key()).replies), 1)

    def test_split_off_and_delay_off(self):
        self.p.settings["split_msgs"] = False
        self.p.settings["typing_delay"] = False
        CLIENT.ai_result = lambda m, **kw: "Це перше речення довге. Це друге речення теж."
        slept = []
        mod.time.sleep = lambda s: slept.append(s)
        self.round("привіт")
        self.assertEqual(len(CLIENT.sent), 1)
        self.assertEqual(slept, [])

    def test_draft_not_split(self):
        self.p.settings["mode_0_42"] = mod.MODE_DRAFT
        CLIENT.ai_result = lambda m, **kw: "Це перше речення довге. Це друге речення теж."
        self.round("привіт")
        self.assertEqual(CLIENT.sent, [])
        self.assertEqual(len(CLIENT.drafts), 1)

    def test_skip_emoji_only(self):
        self.round("\U0001F44D")
        self.assertEqual(CLIENT.ai_calls, [])
        self.p.settings["skip_emoji"] = False
        self.round("\U0001F44E")
        self.assertEqual(len(CLIENT.ai_calls), 1)

    def test_max_reply_cap(self):
        self.p.settings["max_reply"] = "50"
        self.p.settings["split_msgs"] = False
        CLIENT.ai_result = lambda m, **kw: "слово " * 100
        self.round("привіт")
        self.assertLessEqual(len(CLIENT.sent[0][1]), 50 + len(mod.ROBOT) + 1)

    def test_duplicate_reply_retried_then_skipped(self):
        CLIENT.ai_result = lambda m, **kw: "ага давай потім напишу тобі"
        self.round("одне")
        self.assertEqual(len(CLIENT.sent), 1)
        self.round("друге")                     # same text twice: retry, still same -> skipped
        self.assertEqual(len(CLIENT.sent), 1)
        self.assertEqual(len(CLIENT.ai_calls), 3)
        self.assertIn("rejected", CLIENT.ai_calls[2]["system"])
        replies = iter(["ага давай потім напишу тобі", "зовсім інша відповідь тут"])
        CLIENT.ai_result = lambda m, **kw: next(replies)
        self.round("третє")
        self.assertEqual(CLIENT.sent[-1][1], "зовсім інша відповідь тут")

    def test_ai_tell_sent_anyway_after_retry(self):
        self.p.settings["disclosure"] = False
        CLIENT.ai_result = lambda m, **kw: "Як ШІ я не можу це зробити"
        self.round("привіт")
        self.assertEqual(len(CLIENT.ai_calls), 2)
        self.assertEqual(len(CLIENT.sent), 1)                # never silent
        self.assertTrue(self.p.is_enabled(self.key()))      # not counted as a failure

    def test_humanize_off_is_legacy(self):
        self.p.settings["humanize"] = False
        CLIENT.ai_result = lambda m, **kw: "Звісно. Це перше. Це друге."
        self.round("привіт")
        self.assertEqual(len(CLIENT.sent), 1)
        self.assertEqual(CLIENT.ai_calls[0]["system"], mod.DEFAULT_PROMPT)
        self.assertIsNone(CLIENT.ai_calls[0]["temperature"])

    def test_disclosure_rule_in_prompt(self):
        self.round("привіт")
        self.assertIn("honestly say", CLIENT.ai_calls[0]["system"])
        self.p.settings["disclosure"] = False
        self.round("інше")
        self.assertIn("never claim to be a human", CLIENT.ai_calls[-1]["system"])


class TestStyleTest(Base):
    def test_five_samples_nothing_sent(self):
        hist = []
        for i in range(8):
            hist.append({"id": 10 + i, "from_id": 7, "out": False, "date": 100 + i,
                         "text": "питання %d" % i, "is_bot": False})
        CLIENT.history[:] = hist + own_history()
        CLIENT.ai_result = lambda m, **kw: "ну ща гляну"
        self.assertTrue(self.p.start_style_test(0, DID, "Alice"))
        self.assertEqual(CLIENT.sent, [])
        self.assertEqual(len(CLIENT.ai_calls), 5)
        res = self.p.get_setting("style_test_result")
        self.assertIn("питання 7", res)
        self.assertNotIn("питання 2", res)
        self.assertTrue(CLIENT.bulletins)
        self.assertFalse(self.p._testing)

    def test_settings_expose_humanize_controls(self):
        keys = {getattr(i, "key", None) for i in self.p.create_settings()}
        for k in ("humanize", "learn_style", "learn_n", "split_msgs", "typing_delay", "tone", "test_pick"):
            self.assertIn(k, keys)
        text = " ".join(str(getattr(i, "subtext", "") or "") for i in self.p.create_settings())
        self.assertIn("your own AI server", text)


if __name__ == "__main__":
    unittest.main()
