"""0.3.2 tests: readable decision log, non-interactive notes, uk/ru/en localization, 'bot writes first' command.

Run: python -m unittest discover -s tests -v
"""
import re
import unittest

from test_ai_autoreply import Base, CLIENT, DID, PLUGIN, mod, own_history


class Params(object):
    def __init__(self, message, peer=DID):
        self.message, self.peer = message, peer


def default_info(did, account=None):
    return dict(CLIENT.info)


class TestDecisionLog(Base):
    def setUp(self):
        Base.setUp(self)
        self.enable()

    def tearDown(self):
        CLIENT.get_dialog_info = default_info

    def rows(self):
        items = self.p.create_settings()
        i = [n for n, x in enumerate(items) if getattr(x, "text", "") == "Recent decisions"][0]
        return items, items[i + 1:]

    def test_one_row_per_decision_newest_first_with_full_reason(self):
        self.p._decide(self.key(), "skip", "chat hourly cap")
        self.clock[0] += 5
        self.p._decide(self.key(), "sent", "ok")
        _items, rest = self.rows()
        self.assertEqual(type(rest[0]).__name__, "Header")
        self.assertRegex(rest[0].text, r"^\d\d:\d\d:\d\d · Alice$")
        self.assertEqual(rest[1].text, "sent")                      # newest first
        self.assertEqual(type(rest[1]).__name__, "Divider")         # non-clickable, multi-line
        self.assertTrue(rest[3].text.startswith("skipped: "))
        self.assertIn("hourly limit", rest[3].text)
        self.assertNotIn("…", rest[3].text)

    def test_reason_is_never_cut(self):
        self.p._decide(self.key(), "skip", "empty context (last message is not from them)")
        _i, rest = self.rows()
        self.assertEqual(rest[1].text,
                         "skipped: " + mod.reason_text("en", "empty_context_last_message_is_not_from_them"))

    def test_ukrainian_plain_language(self):
        self.p.settings["ui_lang"] = 1
        self.p._decide(self.key(), "skip", "chat hourly cap")
        items = self.p.create_settings()
        i = [n for n, x in enumerate(items) if getattr(x, "text", "") == "Останні рішення"][0]
        self.assertTrue(items[i + 2].text.startswith("пропущено: співрозмовник пише швидше"))

    def test_title_falls_back_to_id(self):
        CLIENT.get_dialog_info = lambda did, account=None: {"title": ""}
        self.p._decide("0:777", "skip", "disabled")
        _i, rest = self.rows()
        self.assertTrue(rest[0].text.endswith("· 777"))

    def test_title_from_dialog_info_when_chat_not_listed(self):
        CLIENT.get_dialog_info = lambda did, account=None: {"title": "Cherish"}
        self.p._decide("0:8666190439", "sent", "ok")
        _i, rest = self.rows()
        self.assertTrue(rest[0].text.endswith("· Cherish"))

    def test_copy_and_clear(self):
        for i in range(25):
            self.p._decide(self.key(), "skip", "quiet hours")
        items, _r = self.rows()
        by_key = {getattr(x, "key", None): x for x in items}
        by_key["log_copy"].on_click()
        self.assertEqual(len(CLIENT.clipboard[0].splitlines()), 26)
        self.assertIn("Alice", CLIENT.clipboard[0])
        by_key["log_clear"].on_click()
        self.assertEqual(len(self.p._decisions), 0)
        self.assertEqual(self.p.settings["decisions"], "[]")
        _i, rest = self.rows()
        self.assertEqual(rest[0].text, "No decisions yet.")
        self.p.copy_log()
        self.assertEqual(len(CLIENT.clipboard), 1)               # nothing to copy

    def test_explanations_are_not_clickable_rows(self):
        for it in self.p.create_settings():
            if type(it).__name__ == "Text":
                self.assertTrue(callable(getattr(it, "on_click", None)), it.text)

    def test_note_sets_text_on_divider(self):
        self.assertEqual(mod.note("hello\nworld").text, "hello\nworld")


class TestLocalization(Base):
    def test_every_string_has_three_languages_and_same_placeholders(self):
        for key, row in mod.S.items():
            self.assertEqual(len(row), 3, key)
            self.assertTrue(all(row), key)
            counts = {len(re.findall(r"%[sd]", r)) for r in row}
            self.assertEqual(len(counts), 1, key)
        for key, row in mod.R.items():
            self.assertEqual(len(row), 3, key)
            self.assertTrue(all(row), key)

    def test_all_decision_codes_have_reasons(self):
        with open(PLUGIN, encoding="utf-8") as fh:
            src = fh.read()
        codes = set(re.findall(r'_skip\(key, "([^"]+)"\)', src))
        codes |= set(re.findall(r'_decide\([^,]+, "[a-z]+", "([^"%]+)"\)', src))
        codes |= {"outgoing", "master_off", "sender is bot", "duplicate", "too old", "empty",
                  "secret chat", "channel", "bot", "no text / service message", "hourly cap reached"}
        for c in codes:
            code = re.sub(r"\W+", "_", c.lower()).strip("_")
            self.assertIn(code, mod.R, c)

    def test_languages(self):
        for idx, lang in ((1, "uk"), (2, "ru"), (3, "en")):
            self.p.settings["ui_lang"] = idx
            self.assertEqual(self.p.lang(), lang)
        self.assertNotEqual(mod.tr("uk", "master"), mod.tr("en", "master"))
        self.assertNotEqual(mod.tr("ru", "master"), mod.tr("uk", "master"))
        self.assertEqual(mod.tr("xx", "master"), mod.tr("en", "master"))

    def test_auto_defaults_to_ukrainian_when_phone_language_is_not_visible(self):
        self.p.settings["ui_lang"] = 0
        old = mod.detect_ui_lang
        try:
            mod.detect_ui_lang = lambda: None
            self.assertEqual(self.p.lang(), "uk")
            mod.detect_ui_lang = lambda: "ru"
            self.assertEqual(self.p.lang(), "ru")
        finally:
            mod.detect_ui_lang = old

    def test_settings_and_bulletins_localized(self):
        self.p.settings["ui_lang"] = 1
        texts = " ".join(str(getattr(i, "text", "")) + str(getattr(i, "subtext", "") or "")
                         for i in self.p.create_settings())
        self.assertIn("Головний перемикач", texts)
        self.assertIn("Режим друга", texts)
        self.assertNotIn("Master switch", texts)
        self.p.settings["ui_lang"] = 2
        CLIENT.bulletins[:] = []
        self.p.on_enable_click({"account": 0, "dialog_id": DID})
        self.assertIn("включён", CLIENT.bulletins[-1])

    def test_selector_values_stay_index_based(self):
        keys = {getattr(i, "key", None): i for i in self.p.create_settings()}
        self.assertEqual(keys["ui_lang"].default, 0)
        self.assertEqual(len(keys["ui_lang"].items), 4)
        self.assertEqual(len(keys["preset"].items), 4)
        self.assertEqual(len(keys["tone"].items), 3)


class TestOwnerCommand(Base):
    def setUp(self):
        Base.setUp(self)
        self.enable()
        CLIENT.history[:] = own_history()
        CLIENT.ai_result = lambda m, **kw: "та норм, ти як"
        self.p.settings["typing_delay"] = False

    def hook(self, text, peer=DID):
        return self.p.on_send_message_hook(0, Params(text, peer))

    def cancelled(self, res):
        return res is not None and res.strategy == 1

    def fresh_incoming(self):
        CLIENT.history.append({"id": 900, "from_id": 7, "out": False, "date": int(self.clock[0] - 60),
                               "text": "ти де зараз був?", "is_bot": False, "dialog_id": DID})

    def test_plain_messages_pass_through(self):
        for t in ("привіт", ".air", "  ", "text .ai", ".ai1"):
            self.assertIsNone(self.hook(t), t)
        self.assertTrue(getattr(self.p, "send_hook_registered", False))

    def test_command_cancelled_and_never_sent(self):
        self.fresh_incoming()
        res = self.hook(".ai")
        self.assertTrue(self.cancelled(res))
        self.assertEqual(len(CLIENT.sent), 1)
        self.assertNotIn(".ai", CLIENT.sent[0][1])
        self.assertIn("owner_command", self.p.decisions_text())
        self.assertIn("ти де зараз був?", CLIENT.ai_calls[-1]["messages"][-2]["content"])
        self.assertEqual(CLIENT.ai_calls[-1]["messages"][-1]["role"], "user")

    def test_cyrillic_lookalike_and_case(self):
        self.fresh_incoming()
        self.assertTrue(self.cancelled(self.hook(".АІ")))
        self.assertEqual(len(CLIENT.sent), 1)

    def test_topic_instruction(self):
        res = self.hook(".ai запитай як пройшов іспит")
        self.assertTrue(self.cancelled(res))
        last = CLIENT.ai_calls[-1]["messages"][-1]["content"]
        self.assertIn("запитай як пройшов іспит", last)
        self.assertIn("Never invent facts", CLIENT.ai_calls[-1]["system"])
        self.assertIn("owner_command_topic", self.p.decisions_text())
        self.assertEqual(len(CLIENT.sent), 1)

    def test_draft_variants(self):
        for t in (".ai ?", ".ai draft", ".ai?"):
            CLIENT.drafts[:] = []
            CLIENT.sent[:] = []
            self.assertTrue(self.cancelled(self.hook(t)), t)
            self.assertEqual(len(CLIENT.drafts), 1, t)
            self.assertEqual(CLIENT.sent, [], t)
        CLIENT.drafts[:] = []
        self.hook(".ai ? про вечерю")
        self.assertIn("про вечерю", CLIENT.ai_calls[-1]["messages"][-1]["content"])
        self.assertEqual(len(CLIENT.drafts), 1)

    def test_setting_sends_to_draft(self):
        self.p.settings["cmd_mode"] = 1
        self.hook(".ai")
        self.assertEqual(len(CLIENT.drafts), 1)
        self.assertEqual(CLIENT.sent, [])

    def test_old_context_uses_opener(self):
        CLIENT.history[:] = [dict(h, date=int(self.clock[0] - 3 * 86400)) for h in own_history()]
        self.assertTrue(self.cancelled(self.hook(".ai")))
        self.assertIn("owner_command_opener", self.p.decisions_text())
        last = CLIENT.ai_calls[-1]["messages"][-1]["content"]
        self.assertIn("Open one", last)
        self.assertTrue(any(o in last for o in mod.DEFAULT_OPENERS))

    def test_custom_openers_and_humanize_off_sends_raw(self):
        CLIENT.history[:] = []
        self.p.settings["humanize"] = False
        self.p.settings["cmd_openers"] = "агов\nє тут хтось"
        self.hook(".ai")
        self.assertEqual(CLIENT.ai_calls, [])
        self.assertIn(CLIENT.sent[0][1], ("агов", "є тут хтось"))

    def test_opener_falls_back_when_ai_fails(self):
        CLIENT.history[:] = []
        CLIENT.ai_result = lambda m, **kw: RuntimeError("down")
        self.hook(".ai")
        self.assertEqual(len(CLIENT.sent), 1)
        self.assertIn(CLIENT.sent[0][1], mod.DEFAULT_OPENERS)

    def test_topic_ai_failure_sends_nothing_and_is_logged(self):
        CLIENT.ai_result = lambda m, **kw: RuntimeError("down")
        self.assertTrue(self.cancelled(self.hook(".ai тема")))
        self.assertEqual(CLIENT.sent, [])
        self.assertIn("owner_command_ai_failed", self.p.decisions_text())
        self.assertTrue(CLIENT.bulletins)
        self.assertEqual(self.p._cmd_busy, set())

    def test_not_in_list_passes_unless_any_private(self):
        other = 555
        self.assertIsNone(self.hook(".ai", other))
        self.p.settings["cmd_any_private"] = True
        self.assertTrue(self.cancelled(self.hook(".ai", other)))
        self.assertEqual(CLIENT.sent[-1][0], other)
        self.assertIsNone(self.hook(".ai", -100))                # groups never
        CLIENT.info = {"id": 1, "title": "Bot", "type": "user", "is_bot": True}
        self.assertIsNone(self.hook(".ai", 556))

    def test_disabled_command_and_media_pass_through(self):
        self.p.settings["cmd_enable"] = False
        self.assertIsNone(self.hook(".ai"))
        self.p.settings["cmd_enable"] = True
        pr = Params(".ai")
        pr.photo = object()
        self.assertIsNone(self.p.on_send_message_hook(0, pr))

    def test_master_off_cancels_without_sending(self):
        self.p.settings["master"] = False
        self.assertTrue(self.cancelled(self.hook(".ai")))
        self.assertEqual(CLIENT.sent, [])
        self.assertEqual(CLIENT.ai_calls, [])

    def test_ignores_cooldown_and_hourly_limits_but_logs(self):
        self.p.settings["chat_hourly"] = "1"
        self.p.settings["hourly_cap"] = "1"
        self.p._state(self.key()).cooldown_until = self.clock[0] + 1000
        for i in range(3):
            CLIENT.ai_result = lambda m, i=i, **kw: "варіант %d тут" % i
            self.hook(".ai тема %d" % i)
        self.assertEqual(len(CLIENT.sent), 3)
        self.assertEqual(self.p.decisions_text().count("owner_command_topic"), 3)

    def test_sent_text_is_deduplicated_as_bot_text(self):
        self.hook(".ai тема")
        self.assertTrue(self.p._is_bot_text(CLIENT.sent[0][1]))
        st = self.p._state(self.key())
        before = st.owner_ts
        self.incoming(text=CLIENT.sent[0][1], out=True)          # echo of our own message
        self.assertEqual(st.owner_ts, before)
        self.assertEqual(CLIENT.ui_queue, [])
        self.assertEqual(len(CLIENT.sent), 1)

    def test_busy_guard(self):
        self.p._cmd_busy.add(self.key())
        self.assertTrue(self.cancelled(self.hook(".ai")))
        self.assertEqual(CLIENT.sent, [])
        self.assertIn("owner_command_busy", self.p.decisions_text())

    def test_no_disclosure_prefix_in_owner_command(self):
        self.p.settings["disclosure"] = True
        self.hook(".ai тема")
        self.assertNotIn(mod.ROBOT, CLIENT.sent[0][1])

    def test_custom_trigger(self):
        self.p.settings["cmd_triggers"] = "/start, .го"
        self.assertTrue(self.cancelled(self.hook(".ГО")))
        self.assertIsNone(self.hook(".ai"))

    def test_settings_expose_command_options(self):
        keys = {getattr(i, "key", None): i for i in self.p.create_settings()}
        for k in ("cmd_enable", "cmd_triggers", "cmd_mode", "cmd_any_private", "cmd_openers"):
            self.assertIn(k, keys)
        self.assertFalse(keys["cmd_any_private"].default)
        self.assertTrue(keys["cmd_enable"].default)


if __name__ == "__main__":
    unittest.main()
