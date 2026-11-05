"""0.8.0 tests: settings pages (ui.Page), the flat fallback, confirmations, queue, interest, news, bulk change."""
import unittest

from test_ai_autoreply import Base, CLIENT, DID, all_settings, mod


class Page(object):
    def __init__(self, key, text, subtext=None, icon=None):
        self.key, self.text, self.subtext, self.icon = key, text, subtext, icon


def keys_of(items):
    return [getattr(i, "key", None) for i in items if getattr(i, "key", None)]


class Pages(Base):
    def setUp(self):
        super(Pages, self).setUp()
        self._old = (mod.Page, getattr(CLIENT, "SETTINGS_PAGES", None))
        mod.Page, CLIENT.SETTINGS_PAGES = Page, True

    def tearDown(self):
        mod.Page = self._old[0]
        if self._old[1] is None:
            del CLIENT.SETTINGS_PAGES
        else:
            CLIENT.SETTINGS_PAGES = self._old[1]
        super(Pages, self).tearDown()

    def key(self, did=DID):
        return self.p.chat_key(0, did)

    def crawl(self):
        """page id -> rows, every page reachable from the main one."""
        seen, todo = {}, [""]
        while todo:
            page = todo.pop()
            if page in seen:
                continue
            seen[page] = self.p.create_settings(page or None)
            todo += [i.key for i in seen[page] if isinstance(i, Page)]
        return seen

    def page(self, page):
        return {getattr(i, "key", None): i for i in self.p.create_settings(page)}

    def legacy(self):
        mod.Page = None
        try:
            return all_settings(self.p)
        finally:
            mod.Page = Page


class TestTree(Pages):
    def test_no_duplicate_keys_on_any_page(self):
        self.enable()
        self.p.settings["ui_mode"] = 1
        for page, rows in self.crawl().items():
            keys = keys_of(rows)
            self.assertEqual(len(keys), len(set(keys)), page)
            self.assertTrue(rows, page)

    def test_every_old_key_is_reachable(self):
        self.enable()
        self.p.settings["ui_mode"] = 1
        self.p._open_key = self.key()
        old = set(keys_of(self.legacy())) - {"ui_section", "chat_" + self.p._sk(self.key()), "chats_all"}
        new = set()
        for rows in self.crawl().values():
            new |= set(keys_of(rows))
        self.assertEqual(old - new, set())
        sk = self.p._sk(self.key())
        for k in ("tone_", "lore_name_", "lore_age_", "lore_city_", "refresh_"):
            self.assertIn(k + sk, new)
        for k in ("model_cheap_pick", "temp_pick", "ui_mode", "report_send", "chat_sort", "q_rev"):
            self.assertIn(k, new)

    def test_category_pages_are_short(self):
        self.enable()
        self.p.settings["ui_mode"] = 1
        for page in ("", "pg_chats", "pg_persona", "pg_style", "pg_media", "pg_timing", "pg_memory", "pg_model",
                     "pg_cmd", "pg_service"):
            self.assertLessEqual(len(self.p.create_settings(page or None)), 14, page)

    def test_fallback_without_pages(self):
        for flag, page in ((False, Page), (True, None)):
            CLIENT.SETTINGS_PAGES, mod.Page = flag, page
            items = self.p.create_settings()
            self.assertEqual((items[0].key, len(items[0].items)), ("ui_section", len(mod.Plugin.UI_SECTIONS)))
        CLIENT.SETTINGS_PAGES, mod.Page = True, Page
        self.assertEqual(self.p.create_settings()[1].key, "master")

    def test_simple_mode_hides_expert_pages(self):
        root = keys_of(self.p.create_settings())               # no chats: simple mode and the quick setup
        self.assertIn("pg_setup1", root)
        self.assertNotIn("pg_model", root)
        self.assertIn("ui_more", root)
        self.assertNotIn("pg_time_adv", keys_of(self.p.create_settings("pg_timing")))
        self.assertIn("model", keys_of(self.p.create_settings("pg_model_custom")))
        self.assertNotIn("all_accounts", keys_of(self.p.create_settings("pg_chats")))
        self.page("")["ui_more"].on_click()
        self.assertIn("pg_model", keys_of(self.p.create_settings()))
        self.p.settings.pop("ui_mode")
        self.enable()                                           # chats exist: advanced by default
        self.assertIn("pg_cmd", keys_of(self.p.create_settings()))

    def test_quick_setup(self):
        self.assertEqual(keys_of(self.p.create_settings("pg_setup1"))[-1], "pg_setup2")
        self.assertIn("lore_name", keys_of(self.p.create_settings("pg_setup2")))
        rows = self.page("pg_setup3")
        rows["setup_quiet"].on_click()
        rows["setup_fin"].on_click()
        self.assertEqual((self.p.settings["quiet_hours"], self.p.settings["setup_done"]), ("01:00-08:00", True))
        self.assertNotIn("pg_setup1", keys_of(self.p.create_settings()))

    def test_drawing_writes_nothing(self):
        self.enable()
        before = dict(self.p.settings)
        self.crawl()
        self.assertEqual(self.p.settings, before)


class TestChatPage(Pages):
    def test_chat_page_rows_and_confirmed_remove(self):
        self.enable()
        sk = self.p._sk(self.key())
        rows = self.page("pg_chat:" + self.key())
        for k in ("keep_", "mode_", "gender_", "rlang_", "conversation_style_", "tone_", "react_", "prompt_",
                  "test_", "remove_"):
            self.assertIn(k + sk, rows)
        self.assertIn("pg_lore:" + self.key(), rows)
        self.assertEqual(rows["tone_" + sk].default, 0)
        rows["remove_" + sk].on_click()
        self.assertIn(self.key(), self.p._chats)
        self.assertEqual(self.page("pg_chat:" + self.key())["remove_" + sk].text, self.p.t("tap_again"))
        rows["remove_" + sk].on_click()
        self.assertNotIn(self.key(), self.p._chats)
        self.assertEqual(len(self.p.create_settings("pg_chat:" + self.key())), 1)   # a removed chat's page

    def test_second_tap_too_late_only_arms_again(self):
        self.enable()
        cb = self.page("pg_log")
        self.p._decide(self.key(), "skip", "duplicate")
        cb = self.page("pg_log")["log_clear"].on_click
        cb()
        self.clock[0] += 6
        cb()
        self.assertTrue(self.p._decisions)
        cb()
        self.assertFalse(self.p._decisions)

    def test_access_page_has_no_raw_keys(self):
        self.enable()
        texts = " ".join(str(getattr(i, "text", "")) for i in self.p.create_settings("pg_access:" + self.key()))
        self.assertNotIn("cloud_", texts)
        self.assertIn(self.p.t("cloud_title"), texts)
        self.assertEqual(mod.tr("ru", "cloud_title"), u"Память в Neon")

    def test_person_tone_and_lore_fields_reach_the_prompt(self):
        self.enable()
        sk = self.p._sk(self.key())
        self.p.settings["tone_" + sk] = 3
        self.assertIn(mod.TONE_RULES[2], self.p.build_system(self.key(), {}))
        self.p.settings["tone_" + sk] = 0
        self.assertIn(mod.TONE_RULES[0], self.p.build_system(self.key(), {}))
        self.p.settings.update({"lore_name_" + sk: "Olia", "lore_city_" + sk: "Lviv"})
        self.assertIn("Olia, Lviv", self.p._lore_block(self.key()))
        self.p.chat_off(self.key(), remove=True)
        self.assertIsNone(self.p.settings.get("tone_" + sk))
        self.assertIsNone(self.p.settings.get("lore_name_" + sk))

    def test_refresh_topic_writes_first(self):
        self.enable()
        self.p.settings["revive"] = False
        CLIENT.history[:] = [{"id": 1, "from_id": 7, "out": False, "date": int(self.clock[0] - 30), "text": "hey",
                              "is_bot": False, "reply_to": None, "dialog_id": DID}]
        self.page("pg_chat:" + self.key())["refresh_" + self.p._sk(self.key())].on_click()
        self.assertTrue(CLIENT.sent)
        self.p.settings["mode_" + self.p._sk(self.key())] = mod.MODE_DRAFT
        self.assertNotIn("refresh_" + self.p._sk(self.key()), self.page("pg_chat:" + self.key()))


class TestModelLists(Pages):
    def test_background_model_and_temperature_lists(self):
        rows = self.page("pg_model")
        self.assertEqual(rows["temp_pick"].default, 1)                   # 0.85 when nothing is stored
        self.assertEqual(rows["model_cheap_pick"].default, 0)
        rows["temp_pick"].on_change(2)
        rows["model_cheap_pick"].on_change(2)
        self.assertEqual((self.p.settings["temperature"], self.p.settings["model_cheap"]),
                         ("1.0", mod.Plugin.MODEL_PRESETS[2]))
        self.p.settings["temperature"] = "0.3"
        self.assertEqual(self.page("pg_model")["temp_pick"].default, 3)  # custom value
        self.assertEqual(self.page("pg_model_custom")["temperature"].default, "0.85")


class TestQueue(Pages):
    def test_send_now_and_stop(self):
        self.enable()
        self.p.settings["debounce"] = "60"
        self.incoming(text="hello?")
        rows = self.page("pg_queue")
        sk = self.p._sk(self.key())
        self.assertIn("q_now_" + sk, rows)
        self.assertIn(self.p.t("q_n", 1), self.page("")["pg_queue"].subtext)
        rows["q_stop_" + sk].on_click()
        self.assertFalse(self.p._state(self.key()).pending)
        self.assertIn("q_stop_all", rows)
        self.incoming(text="again?")
        self.page("pg_queue")["q_now_" + sk].on_click()
        self.assertEqual(len(CLIENT.sent), 1)
        self.assertNotIn("q_now_" + sk, self.page("pg_queue"))
        self.assertIn(self.p.t("q_empty"), [getattr(i, "text", "") for i in self.p.create_settings("pg_queue")])
        self.assertIn("q_rev", self.p.settings)                         # the open queue page is redrawn


class TestInterestAndMemory(Pages):
    def test_interest_score_and_sort(self):
        self.enable()
        self.enable(did=DID + 1)
        now = int(self.clock[0])
        rows = []
        for i in range(30):
            rows.append({"id": i, "out": i % 2 == 1, "date": now - 3000 + i * 60, "text": "так? 😀" if i % 2 == 0 else "ok"})
        self.p._interest_note(self.key(), rows)
        self.p._interest_note(self.key(DID + 1), [dict(r, text="", date=now - 9 * 86400) for r in rows[:4]])
        sc = self.p._scores()
        self.assertTrue(0 <= sc[self.key(DID + 1)] < sc[self.key()] <= 100)
        chats = [i.key for i in self.p.create_settings("pg_chats") if isinstance(i, Page)]
        self.assertEqual(chats[:2], ["pg_chat:" + self.key(), "pg_chat:" + self.key(DID + 1)])
        self.p._interest_note(self.key(), rows[:2])                     # at most every 10 minutes
        self.assertEqual(self.p._scores()[self.key()], sc[self.key()])

    def test_memory_bars(self):
        self.enable()
        self.p._mem_len[self.key()] = mod.MEM_SUMMARY_MAX // 2
        self.assertIn(u"▓▓▓▓░░░░ 50%", self.page("")["pg_memory"].subtext)
        self.assertIn("50%", self.p.create_settings("pg_memory")[0].text)


class TestNewsReportBulk(Pages):
    def test_news_links_open_the_setting_first(self):
        news = self.p.create_settings("pg_news")
        links = [i.key for i in news if isinstance(i, Page)]
        self.assertIn("pg_style_adv#max_reply_min", links)
        rows = self.p.create_settings("pg_style_adv#max_reply_min")
        self.assertEqual((type(rows[0]).__name__, rows[1].key), ("Header", "max_reply_min"))
        self.assertEqual(len(keys_of(rows)), len(set(keys_of(rows))))
        self.assertIn("pg_news", keys_of(self.p.create_settings()))
        {getattr(i, "key", None): i for i in news}["news_ok"].on_click()
        self.assertNotIn("pg_news", keys_of(self.p.create_settings()))

    def test_report_is_sent_in_parts(self):
        self.enable()
        self.page("pg_service")["report_send"].on_pick(777, "Dev")
        self.assertTrue(CLIENT.sent)
        self.assertTrue(all(d == 777 and len(t) <= 4000 for d, t, _r in CLIENT.sent))
        self.assertIn("Dev", CLIENT.bulletins[-1])

    def test_bulk_change_by_filter(self):
        self.enable()
        self.enable(did=DID + 1)
        self.p.chat_off(self.key(DID + 1), remove=False)
        self.p.settings.update({"bulk_f": 1, "bulk_mode": 2, "bulk_tone": 3})
        self.page("pg_bulk")["bulk_apply"].on_click()
        sk, sk2 = self.p._sk(self.key()), self.p._sk(self.key(DID + 1))
        self.assertEqual((self.p.settings["mode_" + sk], self.p.settings["tone_" + sk]), (mod.MODE_DRAFT, 2))
        self.assertEqual(self.p.settings.get("mode_" + sk2, 0), mod.MODE_AUTO)    # paused chat: not in the filter
        self.assertEqual(self.p.settings["bulk_mode"], 0)


class TestCallbacksKept(Pages):
    def test_main_screen_reload_keeps_page_callbacks(self):
        self.p._settings = {"a": 1}
        self.p._settings = {"b": 2}
        self.assertEqual(self.p._settings, {"a": 1, "b": 2})


if __name__ == "__main__":
    unittest.main()
