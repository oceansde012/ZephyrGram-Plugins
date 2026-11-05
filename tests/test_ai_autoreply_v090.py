"""0.9.0 tests: settings audit fixes (preset switches, report button, 14-row pages, menu language,
menu items hidden where the bot cannot work, daily cap 0 = no limit, hints)."""
from test_ai_autoreply import CLIENT, DID, mod
from test_ai_settings_pages_v080 import Page, Pages, keys_of

PRESET_SWITCHES = (("human_timing", "human_timing"), ("skip_ack", "skip_ack"),
                   ("group_need_question", "group_q"), ("scan", "scan_on"))


class TestPresetSwitches(Pages):
    def test_switch_shows_the_value_the_preset_uses(self):
        for preset in range(len(mod.PRESETS)):
            self.p.settings["preset"] = preset
            for key, label in PRESET_SWITCHES:
                row = self.p._pswitch(key, label)
                self.assertIs(row.default, self.p._pbool(key), (preset, key))
                self.assertIn(self.p.t("st_on" if row.default else "st_off"), row.subtext)

    def test_pages_show_preset_value_and_explicit_value_wins(self):
        self.p.settings["ui_mode"] = 1
        self.p.settings["preset"] = 0                              # Balanced: human timing and scan off
        self.assertFalse(self.page("pg_timing")["human_timing"].default)
        self.assertFalse(self.page("pg_limits_adv")["scan"].default)
        self.p.settings["preset"] = 3                              # Live: both on
        self.assertTrue(self.page("pg_timing")["human_timing"].default)
        self.p.settings["human_timing"] = False                    # explicit choice still decides
        self.assertFalse(self.p._pbool("human_timing"))


class TestServiceReport(Pages):
    def test_report_button_on_service_page(self):
        row = self.page("pg_service").get("log_report")
        self.assertIsNotNone(row)
        self.assertEqual(row.on_click, self.p.copy_report)


class TestFourteenRows(Pages):
    def add_chats(self, n, accounts=1):
        for i in range(n):
            self.p.chat_on(i % accounts, 1000 + i, "Chat %d" % i, "user")
        self.p._load_chats()

    def test_chat_list_never_over_14_rows(self):
        for accounts in (1, 2, 3):
            for n in (1, 2, 11, 12, 13, 15, 30):
                self.p.settings["chats"] = "{}"
                self.p._chats = {}
                self.add_chats(n, accounts)
                rows = self.p.create_settings("pg_chats")
                self.assertLessEqual(len(rows), 14, (accounts, n))
                shown = [r for r in rows if isinstance(r, Page) and r.key.startswith("pg_chat:")]
                self.assertEqual(any(getattr(r, "key", None) == "chats_all" for r in rows), len(shown) < n,
                                 (accounts, n))

    def test_add_chat_on_own_page_and_six_chats_fit(self):
        self.add_chats(10)
        rows = self.p.create_settings("pg_chats")
        self.assertIn("pg_add", keys_of(rows))
        self.assertNotIn("add_pick", keys_of(rows))
        self.assertEqual(sum(1 for r in rows if isinstance(r, Page) and r.key.startswith("pg_chat:")), 6)
        self.assertEqual(len(rows), 14)
        self.assertEqual(keys_of(self.p.create_settings("pg_add")), ["add_pick", "add_username"])

    def test_add_chat_reachable_without_chats(self):
        self.assertIn("pg_add", keys_of(self.p.create_settings("pg_chats")))

    def test_show_all_still_lists_every_chat(self):
        self.add_chats(20)
        self.p._toggle_all_chats()
        rows = self.p.create_settings("pg_chats")
        self.assertEqual(sum(1 for r in rows if isinstance(r, Page) and r.key.startswith("pg_chat:")), 20)

    def test_delay_pages_split_and_short(self):
        self.enable()
        self.p.settings["ui_mode"] = 1
        adv = self.p.create_settings("pg_time_adv")
        cold = self.p.create_settings("pg_time_cold")
        self.assertIn("pg_time_cold", keys_of(adv))
        self.assertIn("reset_pace", keys_of(adv))
        for rows in (adv, cold):
            self.assertLessEqual(len(rows), 14)
        self.assertEqual(set(keys_of(cold)), {"cold_after", "lat_cold_min", "lat_cold_max", "lat_long_pct",
                                              "lat_long_min", "lat_long_max"})
        reached = set()
        for rows in self.crawl().values():
            reached |= set(keys_of(rows))
        self.assertTrue(set(mod.PACE_KEYS) <= reached)

    def test_cold_page_is_advanced(self):
        self.enable()
        self.p.settings["ui_mode"] = 0
        self.assertNotIn("pg_time_cold", self.crawl())


class TestMenuLanguage(Pages):
    def texts(self):
        return {m.key: m.text for m in self.p.menu}

    def test_language_change_re_adds_menu_items(self):
        self.assertEqual(self.texts()["ai_autoreply_on"], mod.tr("en", "menu_on"))
        sel = {getattr(i, "key", None): i for i in self.p._section_main()}["ui_lang"]
        sel.on_change(2)                                          # Russian
        self.assertEqual(self.p.settings["ui_lang"], 2)
        self.assertEqual(sorted(self.texts()), ["ai_autoreply_cmd", "ai_autoreply_off", "ai_autoreply_on"])
        for n in ("on", "off", "cmd"):
            self.assertEqual(self.texts()["ai_autoreply_" + n], mod.tr("ru", "menu_" + n))
        self.assertEqual(len(self.p.menu), 3)


class TestMenuHidden(Pages):
    def ctx(self, did=DID):
        return {"account": 0, "dialog_id": did, "message": None}

    def test_hidden_where_bot_never_works(self):
        for info in ({"type": "channel"}, {"type": "secret"}, {"type": "user", "is_bot": True}):
            CLIENT.info = dict(info, id=DID, title="X")
            self.assertFalse(self.p.cond_show_off(self.ctx()), info)
        for info in ({"type": "user", "is_bot": False}, {"type": "group"}, {}):
            CLIENT.info = dict(info, id=DID, title="X")
            self.assertTrue(self.p.cond_show_off(self.ctx()), info)

    def test_no_cache_shows_item(self):
        old = CLIENT.get_dialog_info

        def boom(did, account=None):
            raise RuntimeError("not cached")
        CLIENT.get_dialog_info = boom
        try:
            self.assertTrue(self.p.cond_show_off(self.ctx()))
        finally:
            CLIENT.get_dialog_info = old


class TestDailyCapZero(Pages):
    def test_zero_means_no_daily_limit(self):
        self.enable()
        key = self.p.chat_key(0, DID)
        self.p.settings["daily_cap"] = "1"
        self.p.settings["usage"] = mod.json.dumps({"day": self.p._day(), "n": {key: 5}})
        self.assertEqual(self.p.caps_ok(key), "daily cap reached")
        self.p.settings["daily_cap"] = "0"
        self.assertIsNone(self.p.caps_ok(key))
        self.assertIn(self.p.t("zero_none"), self.page("pg_limits_adv")["daily_cap"].subtext)


class TestHints(Pages):
    def test_reset_and_disclosure_hints(self):
        self.enable()
        self.p.settings["ui_mode"] = 1
        reset = self.page("pg_time_adv")["reset_pace"]
        self.assertIn(self.p.t("reset_pace_s"), (reset.subtext or "") + reset.text)
        for natural in (False, True):
            self.p.settings["natural_chat"] = natural
            row = self.page("pg_model")["natural_disclosure" if natural else "disclosure"]
            self.assertEqual(row.subtext, self.p.t("disclosure_s"))

    def test_settings_strings_use_typographic_apostrophe(self):
        for key, row in list(mod.S.items()):
            self.assertNotRegex(row[1], u"[а-яіїєґ]'[а-яіїєґ]", key)
