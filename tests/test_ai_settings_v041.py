"""0.4.1 tests: the settings screen (main block, compact chat list, collapsible groups).

Run: python -m unittest discover -s tests -v
"""
import unittest

from test_ai_autoreply import Base, CLIENT, DID, all_settings, mod

# Every global setting of the 0.4.0 screen: key -> (row type, default). Keys, types and defaults must not change.
GLOBAL = {
    "master": ("Switch", True), "ui_lang": ("Selector", 0), "preset": ("Selector", 3),
    "reply_lang": ("Selector", 3), "reply_all": ("Switch", False), "all_accounts": ("Input", ""),
    "skip_links": ("Switch", True), "revive": ("Switch", False), "revive_after": ("Input", "20"),
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
}
for _k in ("lat_warm_min", "lat_warm_max", "lat_cold_min", "lat_cold_max", "lat_long_pct", "lat_long_min",
           "lat_long_max", "warm_window", "cold_after", "type_ms", "warm_cap", "split2_pct", "split_gap_min",
           "split_gap_max", "ack_reply_pct", "loop_burst", "owner_defers", "cooldown_jitter", "catchup_min",
           "scan_interval"):
    GLOBAL[_k] = ("Input", "")
BUTTONS = {"add_pick": "DialogPicker", "add_username": "UsernameInput", "test_pick": "DialogPicker"}
TOP = ["master", "reply_all", "all_accounts", "skip_links", "short_msgs", "revive", "reply_lang", "tone", "preset",
       "ui_lang"]


def by_key(items):
    return {getattr(i, "key", None): i for i in items if getattr(i, "key", None)}


class Screen(Base):
    def tap(self, key):
        by_key(self.p.create_settings())[key].on_click()


class TestAllSettingsReachable(Screen):
    def test_every_key_kept_with_type_and_default(self):
        rows = by_key(all_settings(self.p))
        for key, (kind, default) in GLOBAL.items():
            self.assertIn(key, rows, key)
            self.assertEqual(type(rows[key]).__name__, kind, key)
            self.assertEqual(rows[key].default, default, key)
        for key, kind in BUTTONS.items():
            self.assertEqual(type(rows[key]).__name__, kind, key)

    def test_folded_keys_appear_only_after_opening_their_group(self):
        folded = set(by_key(self.p.create_settings()))
        opened = set(by_key(all_settings(self.p)))
        self.assertTrue(set(TOP) <= folded)
        hidden = set(GLOBAL) - set(TOP)
        self.assertEqual(hidden & folded, set())                 # everything else waits in a group
        self.assertTrue(hidden <= opened)
        # each group reveals its own keys
        seen = set()
        for gid in mod.Plugin.SETTINGS_GROUPS:
            self.p._open_groups = {gid}
            seen |= set(by_key(self.p.create_settings())) - folded
        self.assertTrue(hidden <= seen)

    def test_per_chat_options_unchanged(self):
        self.enable()
        sk = self.p._sk(self.key())
        self.p._open_key = self.key()
        rows = by_key(self.p.create_settings())
        self.assertEqual((rows["mode_" + sk].default, len(rows["mode_" + sk].items)), (mod.MODE_AUTO, 3))
        self.assertEqual((rows["rlang_" + sk].default, len(rows["rlang_" + sk].items)), (0, 5))
        self.assertTrue(rows["keep_" + sk].default)
        for k in ("memory_", "see_media_", "transcribe_voice_"):
            self.assertFalse(rows[k + sk].default, k)
        self.assertEqual(rows["prompt_" + sk].default, "")
        self.assertTrue(callable(rows["test_" + sk].on_click))
        self.assertTrue(callable(rows["remove_" + sk].on_click))


class TestMainBlock(Screen):
    def test_top_block_order(self):
        items = self.p.create_settings()
        self.assertEqual(items[0].text, "Main")
        keys = [getattr(i, "key", None) for i in items]
        chats = next(i for i, it in enumerate(items) if str(getattr(it, "text", "")).startswith("Chats with the bot"))
        self.assertEqual([k for k in keys[:chats] if k], TOP)

    def test_first_run_tells_what_to_do(self):
        texts = lambda: [str(getattr(i, "text", "")) for i in self.p.create_settings()]
        self.assertIn(self.p.t("start_note"), texts()[:2])
        self.assertIn(self.p.t("no_chats"), texts())
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


class TestGroups(Screen):
    def test_collapsed_by_default_and_toggle(self):
        rows = by_key(self.p.create_settings())
        for gid in mod.Plugin.SETTINGS_GROUPS:
            self.assertTrue(rows["grp_" + gid].text.startswith("▸ "), gid)
            self.assertTrue(rows["grp_" + gid].subtext, gid)
        self.assertNotIn("lat_warm_min", rows)
        self.tap("grp_live")
        rows = by_key(self.p.create_settings())
        self.assertTrue(rows["grp_live"].text.startswith("▾ "))
        self.assertIn("lat_warm_min", rows)
        self.assertNotIn("humanize", rows)                      # other groups stay closed
        self.tap("grp_style")
        rows = by_key(self.p.create_settings())
        self.assertIn("lat_warm_min", rows)
        self.assertIn("humanize", rows)
        self.tap("grp_live")
        rows = by_key(self.p.create_settings())
        self.assertNotIn("lat_warm_min", rows)
        self.assertIn("humanize", rows)

    def test_open_state_is_not_stored(self):
        before = dict(self.p.settings)
        for gid in mod.Plugin.SETTINGS_GROUPS:
            self.tap("grp_" + gid)
        self.p.create_settings()
        added = set(self.p.settings) - set(before)
        self.assertEqual(added, set())
        p2 = mod.Plugin()
        p2.settings = dict(self.p.settings)
        p2.on_plugin_load()
        self.assertNotIn("lat_warm_min", by_key(p2.create_settings()))

    def test_titles_localized(self):
        for lang in (1, 2, 3):
            self.p.settings["ui_lang"] = lang
            rows = by_key(self.p.create_settings())
            for gid in mod.Plugin.SETTINGS_GROUPS:
                title = rows["grp_" + gid].text[2:]
                self.assertNotIn(title, mod.S, gid)              # a real text, not a missing key
        self.p.settings["ui_lang"] = 1
        self.assertEqual(by_key(self.p.create_settings())["grp_style"].text, "▸ Стиль і людяність")

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

    def test_log_is_last_and_shows_ten_rows(self):
        self.enable()
        for i in range(25):
            self.clock[0] += 1
            self.p._decide(self.key(), "skip", "quiet hours")
        n = len(self.p._decisions)
        rows = by_key(self.p.create_settings())
        self.assertEqual(rows["grp_log"].subtext, "%d entries" % n)
        self.assertNotIn("log_copy", rows)
        self.p._open_groups = {"log"}
        items = self.p.create_settings()
        i = next(n for n, it in enumerate(items) if getattr(it, "key", "") == "grp_log")
        tail = items[i + 1:]
        self.assertEqual(sum(1 for it in tail if type(it).__name__ == "Header"), mod.Plugin.LOG_SHOWN)
        by_key(tail)["log_copy"].on_click()
        self.assertGreater(len(CLIENT.clipboard[0].splitlines()), mod.Plugin.LOG_SHOWN)   # the copy is complete


class TestChatList(Screen):
    def add_chats(self, n):
        for i in range(n):
            self.p.chat_on(0, 1000 + i, "Chat %02d" % i, "user")

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
