"""0.4.1 tests: the settings screen (main block, compact chat list); since 0.4.9 one section at a time.

Run: python -m unittest discover -s tests -v
"""
import unittest

from test_ai_autoreply import Base, CLIENT, DID, all_settings, chats_screen, mod, screen

# Every global setting of the 0.4.0 screen: key -> (row type, default). Keys, types and defaults must not change.
GLOBAL = {
    "master": ("Switch", True), "ui_lang": ("Selector", 0), "preset": ("Selector", 3),
    "reply_lang": ("Selector", 3), "reply_all": ("Switch", False), "all_accounts": ("Input", ""),
    "skip_links": ("Switch", True), "lore": ("Input", ""), "lore_learn": ("Switch", False), "revive": ("Switch", False), "revive_after": ("Input", "20"),
    "revive_window": ("Input", "3"), "revive_daily": ("Input", "2"),
    "cmd_enable": ("Switch", True), "cmd_triggers": ("Input", mod.DEFAULT_TRIGGERS), "cmd_mode": ("Selector", 0),
    "cmd_any_private": ("Switch", False), "cmd_openers": ("Input", ""),
    "humanize": ("Switch", True), "learn_style": ("Switch", True), "learn_n": ("Input", "40"),
    "style_share": ("Switch", False), "style_cache_min": ("Input", "30"), "tone": ("Selector", 0),
    "short_msgs": ("Switch", True), "max_parts": ("Input", "4"), "split_msgs": ("Switch", True),
    "typing_delay": ("Switch", True), "typing_cap": ("Input", ""), "banned_words": ("Input", ""),
    "skip_emoji": ("Switch", True), "answer_detail": ("Selector", 1), "max_reply": ("Input", ""),
    "temperature": ("Input", "0.95"), "default_prompt": ("Input", ""), "context_n": ("Input", "40"),
    "context_chars": ("Input", "16000"), "model": ("Input", ""), "disclosure": ("Switch", True),
    "disclosure_text": ("Input", mod.ROBOT + " "), "trigger": ("Input", ".ai "),
    "debounce": ("Input", ""), "cooldown": ("Input", ""), "chat_hourly": ("Input", ""),
    "polite_stop": ("Switch", True), "owner_active": ("Input", ""), "quiet_hours": ("Input", ""),
    "skip_ack": ("Switch", True), "group_need_question": ("Switch", True), "daily_cap": ("Input", ""),
    "hourly_cap": ("Input", ""), "human_timing": ("Switch", True), "scan": ("Switch", True),
    "show_typing": ("Switch", True), "read_msgs": ("Switch", True), "read_always": ("Switch", False),
    "stickers": ("Switch", True), "sticker_pct": ("Input", "12"), "sticker_recent": ("Switch", True),
    "reactions": ("Selector", 0),                                 # 0.4.9
}
for _k in ("lat_warm_min", "lat_warm_max", "lat_cold_min", "lat_cold_max", "lat_long_pct", "lat_long_min",
           "lat_long_max", "warm_window", "cold_after", "type_ms", "warm_cap", "split2_pct", "split_gap_min",
           "split_gap_max", "ack_reply_pct", "loop_burst", "owner_defers", "cooldown_jitter", "catchup_min",
           "scan_interval"):
    GLOBAL[_k] = ("Input", "")
BUTTONS = {"add_pick": "DialogPicker", "add_username": "UsernameInput", "test_pick": "DialogPicker"}
# 0.4.9: the Main section (the section selector first); the tone moved to the Style section
TOP = ["ui_section", "master", "reply_all", "all_accounts", "skip_links", "short_msgs", "lore", "lore_learn", "revive",
       "reply_lang", "preset", "reactions", "ui_lang"]


def by_key(items):
    return {getattr(i, "key", None): i for i in items if getattr(i, "key", None)}


class Screen(Base):
    def tap(self, key):
        by_key(self.p.create_settings())[key].on_click()

    def section_keys(self):
        """section id -> keys shown in it (the section selector itself left out)."""
        return {sid: set(by_key(screen(self.p, sid))) - {"ui_section"} for sid in mod.Plugin.UI_SECTIONS}


class TestAllSettingsReachable(Screen):
    def test_every_key_kept_with_type_and_default(self):
        rows = by_key(all_settings(self.p))
        for key, (kind, default) in GLOBAL.items():
            self.assertIn(key, rows, key)
            self.assertEqual(type(rows[key]).__name__, kind, key)
            self.assertEqual(rows[key].default, default, key)
        for key, kind in BUTTONS.items():
            self.assertEqual(type(rows[key]).__name__, kind, key)

    def test_each_global_key_is_in_exactly_one_section(self):
        sections = self.section_keys()
        for key in list(GLOBAL) + list(BUTTONS):
            where = [sid for sid, keys in sections.items() if key in keys]
            self.assertEqual(len(where), 1, (key, where))
        self.assertEqual(set(TOP) - {"ui_section"}, sections["main"] & set(GLOBAL))

    def test_section_selector_is_first_everywhere(self):
        for sid in mod.Plugin.UI_SECTIONS:
            items = screen(self.p, sid)
            self.assertEqual((type(items[0]).__name__, items[0].key, items[0].default), ("Selector", "ui_section", 0))
            self.assertEqual(len(items[0].items), len(mod.Plugin.UI_SECTIONS))
            self.assertTrue(items[0].subtext, sid)
            self.assertEqual(sum(1 for it in items if getattr(it, "key", None) == "ui_section"), 1)

    def test_per_chat_options_unchanged(self):
        self.enable()
        sk = self.p._sk(self.key())
        self.p._open_key = self.key()
        rows = by_key(chats_screen(self.p))
        self.assertEqual((rows["mode_" + sk].default, len(rows["mode_" + sk].items)), (mod.MODE_AUTO, 3))
        self.assertEqual((rows["rlang_" + sk].default, len(rows["rlang_" + sk].items)), (0, 5))
        self.assertEqual((rows["react_" + sk].default, len(rows["react_" + sk].items)), (0, 3))
        self.assertTrue(rows["keep_" + sk].default)
        for k in ("see_media_", "transcribe_voice_"):
            self.assertFalse(rows[k + sk].default, k)
        self.assertTrue(rows["memory_" + sk].default)              # 0.5.2: memory is on by default in private chats
        self.assertEqual(rows["prompt_" + sk].default, "")
        self.assertTrue(callable(rows["test_" + sk].on_click))
        self.assertTrue(callable(rows["remove_" + sk].on_click))


class TestMainBlock(Screen):
    def test_default_shows_only_a_short_main_section(self):
        items = self.p.create_settings()                         # nothing stored: Main
        self.assertLessEqual(len(items), 14)
        self.assertEqual([getattr(i, "key", None) for i in items if getattr(i, "key", None)], TOP)
        self.assertEqual(items[0].items[0], "Main")
        self.p.settings["master"] = False                         # with the 'master off' note too
        self.assertLessEqual(len(self.p.create_settings()), 14)
        for _ in range(20):
            self.p.chat_on(0, 2000 + _, "C%d" % _, "user")
        keys = set(by_key(self.p.create_settings()))
        self.assertFalse(any(k.startswith("chat_") for k in keys))  # chats live in their own section

    def test_first_run_tells_what_to_do(self):
        texts = lambda: [str(getattr(i, "text", "")) for i in self.p.create_settings()]
        self.assertIn(self.p.t("start_note"), texts()[:2])
        self.assertIn(self.p.t("no_chats"), [str(getattr(i, "text", "")) for i in chats_screen(self.p)])
        screen(self.p, "main")
        self.p.settings["reply_all"] = True
        self.assertNotIn(self.p.t("start_note"), texts())
        self.p.settings["reply_all"] = False
        self.enable()
        self.assertNotIn(self.p.t("start_note"), texts())
        self.p.settings["master"] = False
        self.assertEqual(texts()[1], self.p.t("master_off_note"))

    def test_modes_explained_once_at_the_chat_mode(self):
        self.enable()
        self.p._open_key = self.key()
        items = all_settings(self.p)
        hits = [i for i in items if "Friend:" in str(getattr(i, "subtext", "") or "") + str(getattr(i, "text", ""))]
        self.assertEqual([getattr(i, "key", None) for i in hits], ["mode_" + self.p._sk(self.key())])


class TestSections(Screen):
    def test_changing_the_section_changes_the_content(self):
        seen = {}
        for i, sid in enumerate(mod.Plugin.UI_SECTIONS):
            self.p.settings["ui_section"] = i                     # what PluginSettingsModel.setValue stores
            seen[sid] = [getattr(it, "key", None) or getattr(it, "text", None) for it in self.p.create_settings()][1:]
        self.assertEqual(len({tuple(v) for v in seen.values()}), len(mod.Plugin.UI_SECTIONS))
        self.assertIn("lat_warm_min", seen["live"])
        self.assertNotIn("lat_warm_min", seen["main"])
        self.assertIn("humanize", seen["style"])
        self.assertIn("tone", seen["style"])
        self.assertIn("add_pick", seen["chats"])
        self.assertIn("cmd_triggers", seen["cmd"])
        self.assertIn("stickers", seen["media"])
        self.assertIn("default_prompt", seen["prompts"])
        self.assertIn("test_pick", seen["test"])
        self.assertIn("log_report", seen["log"])

    def test_nothing_is_folded_inside_a_section(self):
        for sid in mod.Plugin.UI_SECTIONS:
            for it in screen(self.p, sid):
                self.assertFalse(str(getattr(it, "text", "")).startswith(("▸ ", "▾ ")), (sid, it.text))
                self.assertFalse(str(getattr(it, "key", "")).startswith("grp_"), sid)
        live = set(by_key(screen(self.p, "live")))
        for k in ("lat_warm_min", "split_gap_max", "revive_daily", "read_always"):
            self.assertIn(k, live)

    def test_section_kept_between_redraws_and_reloads(self):
        self.p.settings["ui_section"] = mod.Plugin.UI_SECTIONS.index("limits")
        for _ in range(3):
            self.assertIn("quiet_hours", by_key(self.p.create_settings()))
        p2 = mod.Plugin()
        p2.settings = dict(self.p.settings)
        p2.on_plugin_load()
        self.assertIn("quiet_hours", by_key(p2.create_settings()))
        self.assertEqual(by_key(p2.create_settings())["ui_section"].items[self.p.settings["ui_section"]], "Limits")

    def test_bad_stored_section_falls_back_to_main(self):
        for bad in (99, -1, "x", None):
            self.p.settings["ui_section"] = bad
            self.assertIn("master", by_key(self.p.create_settings()))

    def test_log_is_the_last_section(self):
        self.assertEqual(mod.Plugin.UI_SECTIONS[-1], "log")
        self.assertEqual(by_key(self.p.create_settings())["ui_section"].items[-1], "Log")
        self.p.settings["ui_lang"] = 1
        self.assertEqual(by_key(self.p.create_settings())["ui_section"].items[-1], "Журнал")
        self.p.settings["ui_lang"] = 2
        self.assertEqual(by_key(self.p.create_settings())["ui_section"].items[-1], "Журнал")

    def test_section_names_localized(self):
        for lang in (1, 2, 3):
            self.p.settings["ui_lang"] = lang
            names = by_key(self.p.create_settings())["ui_section"].items
            for sid, name in zip(mod.Plugin.UI_SECTIONS, names):
                self.assertNotIn(name, mod.S, sid)                # a real text, not a missing key
        self.p.settings["ui_lang"] = 2
        self.assertEqual(by_key(self.p.create_settings())["ui_section"].items,
                         ["Главное", "Чаты", "Стиль", "Время и паузы", "Лимиты", "Команды", "Медиа и память",
                          "Промпты и модель", "Тест стиля", "Журнал"])

    def test_only_the_section_is_stored(self):
        self.enable()
        before = dict(self.p.settings)
        for i in range(len(mod.Plugin.UI_SECTIONS)):
            self.p.settings["ui_section"] = i
            self.p.create_settings()
        self.p.settings["ui_section"] = mod.Plugin.UI_SECTIONS.index("chats")
        self.tap("chat_" + self.p._sk(self.key()))              # an expanded chat lives in memory only
        self.assertIn("mode_" + self.p._sk(self.key()), by_key(self.p.create_settings()))
        added = set(self.p.settings) - set(before)
        self.assertEqual(added, {"ui_section"})

    def test_empty_fields_show_the_current_preset_value(self):
        self.p.settings["preset"] = 3                            # Live
        rows = by_key(all_settings(self.p))
        self.assertEqual(rows["debounce"].subtext, "Empty = 2-5")
        self.assertEqual(rows["owner_active"].subtext, "Empty = 15. 0 = off")
        self.assertEqual(rows["hourly_cap"].subtext, "Empty = 0. 0 = no limit")
        self.assertEqual(rows["chat_hourly"].subtext, "Empty = 60")
        self.assertIn("preset: on", rows["human_timing"].subtext)
        self.p.settings["preset"] = 0                            # Balanced
        rows = by_key(all_settings(self.p))
        self.assertEqual(rows["owner_active"].subtext, "Empty = 45. 0 = off")
        self.assertEqual(rows["chat_hourly"].subtext, "Empty = 20")
        self.assertEqual(rows["typing_cap"].subtext, "Empty = 2.5")
        self.assertIn("preset: off", rows["human_timing"].subtext)
        self.assertEqual(rows["max_reply"].subtext, "Empty = 1200 (by answer detail)")
        self.p.settings["answer_detail"] = 0
        self.assertEqual(by_key(all_settings(self.p))["max_reply"].subtext, "Empty = 400 (by answer detail)")

    def test_log_section_shows_ten_rows(self):
        self.enable()
        for i in range(25):
            self.clock[0] += 1
            self.p._decide(self.key(), "skip", "quiet hours")
        n = len(self.p._decisions)
        self.assertEqual(by_key(self.p.create_settings())["ui_section"].subtext, self.p.t("gs_main"))
        self.assertNotIn("log_copy", by_key(self.p.create_settings()))
        items = screen(self.p, "log")
        self.assertEqual(items[0].subtext, "%d entries" % n)
        tail = items[1:]
        self.assertEqual(sum(1 for it in tail if type(it).__name__ == "Header"), mod.Plugin.LOG_SHOWN)
        by_key(tail)["log_copy"].on_click()
        self.assertGreater(len(CLIENT.clipboard[0].splitlines()), mod.Plugin.LOG_SHOWN)   # the copy is complete


class TestChatList(Screen):
    def add_chats(self, n):
        for i in range(n):
            self.p.chat_on(0, 1000 + i, "Chat %02d" % i, "user")

    def setUp(self):
        super().setUp()
        self.p.settings["ui_section"] = mod.Plugin.UI_SECTIONS.index("chats")

    def chat_rows(self):
        return [it for it in self.p.create_settings() if str(getattr(it, "key", "")).startswith("chat_")]

    def test_short_list_has_no_button(self):
        self.add_chats(mod.Plugin.CHATS_SHOWN)
        self.assertEqual(len(self.chat_rows()), mod.Plugin.CHATS_SHOWN)
        self.assertNotIn("chats_all", by_key(self.p.create_settings()))

    def test_long_list_folds_its_tail(self):
        self.add_chats(40)
        self.assertEqual(len(self.chat_rows()), mod.Plugin.CHATS_SHOWN)
        rows = by_key(self.p.create_settings())
        self.assertEqual(rows["chats_all"].text, "Show all chats (40)")
        hdr = next(it for it in self.p.create_settings() if str(getattr(it, "text", "")).startswith("Chats with"))
        self.assertEqual(hdr.text, "Chats with the bot · on: 40 of 40")
        self.tap("chats_all")
        self.assertEqual(len(self.chat_rows()), 40)
        self.assertEqual(by_key(self.p.create_settings())["chats_all"].text, "Show fewer chats")
        self.tap("chats_all")
        self.assertEqual(len(self.chat_rows()), mod.Plugin.CHATS_SHOWN)

    def test_opened_chat_beyond_the_fold_stays_visible(self):
        self.add_chats(40)
        last = self.p.chat_key(0, 1039)
        self.p._open_key = last
        rows = by_key(self.p.create_settings())
        sk = self.p._sk(last)
        self.assertIn("chat_" + sk, rows)
        self.assertIn("mode_" + sk, rows)
        self.assertEqual(len(self.chat_rows()), mod.Plugin.CHATS_SHOWN + 1)


if __name__ == "__main__":
    unittest.main()
