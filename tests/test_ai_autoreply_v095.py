"""0.9.5: start the chat memory over / bring it back (#2 A), the memory scale on the Conversation page (#3), one
memory budget per reply (3000 characters, summary 1500) and the server memory searched by the incoming message.
Fake Zephyr, no network, no real AI calls."""
import shutil
import tempfile
import unittest

from test_ai_autoreply import Base, CLIENT, DID, mod
from test_ai_cloud_memory import CloudBase
from test_ai_settings_pages_v080 import Pages


class Store(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.s = mod.ChatMemoryStore(self.dir, enabled=True, max_revisions_per_chat=4096)

    def save(self, text, through):
        rec = self.s.get_summary(0, DID, enabled=True)
        return self.s.set_summary(0, DID, text, through, expected_revision=(rec or {}).get("revision", 0),
                                  enabled=True)

    def test_reset_then_restore(self):
        self.assertTrue(self.save(u"Старая сводка", 10))
        self.assertTrue(self.s.reset(0, DID, 20, enabled=True))
        rec = self.s.get_summary(0, DID, enabled=True)
        self.assertEqual(rec["summary"], "")
        self.assertEqual(rec["through_id"], 20)
        self.assertFalse(self.s.reset(0, DID, 21, enabled=True))          # already empty: no new revision
        self.assertTrue(self.s.restore(0, DID, enabled=True))
        rec = self.s.get_summary(0, DID, enabled=True)
        self.assertEqual(rec["summary"], u"Старая сводка")
        self.assertEqual(rec["through_id"], 10)

    def test_reset_keeps_boundary_moving_forward(self):
        self.save(u"Сводка", 50)
        self.s.reset(0, DID, 30, enabled=True)
        self.assertEqual(self.s.get_summary(0, DID, enabled=True)["through_id"], 50)

    def test_restore_with_nothing_older(self):
        self.assertFalse(self.s.restore(0, DID, enabled=True))
        self.assertEqual(self.s.last_error, "nothing_to_restore")
        self.save(u"Одна", 10)
        self.assertFalse(self.s.restore(0, DID, enabled=True))

    def test_restore_skips_the_same_text(self):
        self.save(u"А", 10)
        self.save(u"Б", 20)
        self.save(u"Б", 30)
        self.assertTrue(self.s.restore(0, DID, enabled=True))
        self.assertEqual(self.s.get_summary(0, DID, enabled=True)["summary"], u"А")


class Chat(Base):
    def setUp(self):
        super().setUp()
        self.enable()
        self.sk = self.p._sk(self.key())
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.p.data_dir = self.dir
        self.p._memory_owner_id = lambda account: 111
        CLIENT.history[:] = [{"id": i, "date": 1000 + i, "text": "t%d" % i, "out": False, "from_id": DID,
                              "dialog_id": DID, "account": 0} for i in range(1, 31)]
        CLIENT.bulletins[:] = []

    def store(self):
        return self.p._memory_for_owner(0, 111)


class TestResetRestore(Chat):
    def test_reset_clears_summary_and_notes_then_restore_brings_both_back(self):
        self.store().set_summary(0, DID, u"Мы договорились о встрече", 5, enabled=True)
        self.p.settings["learned_" + self.sk] = u"любит кофе\nживёт в Киеве"
        self.assertTrue(self.p._memory_reset(self.key()))
        self.assertEqual(self.store().get_summary(0, DID, enabled=True)["summary"], "")
        self.assertEqual(self.p.settings["learned_" + self.sk], "")
        self.assertIn(self.p.t("bl_mem_reset"), CLIENT.bulletins)
        self.assertNotIn(u"встрече", self.p._memory_block(self.store().get_summary(0, DID, enabled=True)) or "")
        self.assertTrue(self.p._memory_restore(self.key()))
        self.assertEqual(self.store().get_summary(0, DID, enabled=True)["summary"], u"Мы договорились о встрече")
        self.assertEqual(self.p.settings["learned_" + self.sk], u"любит кофе\nживёт в Киеве")
        self.assertIn(self.p.t("bl_mem_restored"), CLIENT.bulletins)

    def test_reset_boundary_is_the_newest_message(self):
        self.p._memory_reset(self.key())
        self.assertEqual(self.store().get_summary(0, DID, enabled=True)["through_id"], 30)

    def test_restore_with_nothing(self):
        self.assertFalse(self.p._memory_restore(self.key()))
        self.assertIn(self.p.t("bl_mem_nothing"), CLIENT.bulletins)

    def test_storage_error_keeps_the_saved_notes(self):
        self.p.settings["learned_prev_" + self.sk] = u"заметка"
        st = self.store()
        st.restore = lambda *a, **k: False
        st.last_error = "storage_unavailable_or_full"
        self.assertFalse(self.p._memory_restore(self.key()))
        self.assertEqual(self.p.settings["learned_prev_" + self.sk], u"заметка")
        self.assertIn(self.p.t("bl_mem_fail"), CLIENT.bulletins)

    def test_removing_the_chat_clears_the_saved_notes(self):
        self.p.settings["learned_prev_" + self.sk] = "x"
        self.p.chat_off(self.key(), remove=True)
        self.assertIsNone(self.p.settings.get("learned_prev_" + self.sk))

    def test_reasons(self):
        for c in ("memory_reset", "memory_restored"):
            self.assertIn(c, mod.R)


class TestScale(Chat):
    def test_text_and_warning(self):
        self.p._mem_meta[self.key()] = (4960, self.clock[0] - 7200)
        self.p.settings["learned_" + self.sk] = "\n".join("n%d" % i for i in range(7))
        text = self.p._mem_scale(self.key())
        self.assertIn("62%", text)
        self.assertIn("4960", text)
        self.assertIn(self.p.t("mem_ago_h", 2), text)
        self.assertIn("7", text)
        self.assertNotIn(self.p.t("mem_warn"), text)
        self.p._mem_meta[self.key()] = (7300, self.clock[0])
        self.assertIn(self.p.t("mem_warn"), self.p._mem_scale(self.key()))

    def test_never_updated(self):
        self.p._mem_meta[self.key()] = (0, 0)
        self.assertIn(self.p.t("mem_never"), self.p._mem_scale(self.key()))

    def test_scale_is_filled_from_the_store_when_missing(self):
        self.store().set_summary(0, DID, u"х" * 800, 5, enabled=True)
        self.p._mem_scale(self.key())                    # schedules the read
        self.fire_timers()
        self.assertEqual(self.p._mem_meta[self.key()][0], 800)


class TestPage(Pages):
    def setUp(self):
        super().setUp()
        self.enable()
        self.p.settings["ui_mode"] = 1
        self.sk = self.p._sk(self.key())

    def test_rows(self):
        self.assertIn("pg_cmem:" + self.key(), self.page("pg_talk:" + self.key()))
        mem = self.page("pg_cmem:" + self.key())
        self.assertIn("mem_reset_" + self.sk, mem)
        self.assertIn("mem_restore_" + self.sk, mem)
        self.assertNotIn("mem_cloud_del_" + self.sk, mem)
        self.assertLessEqual(len(self.p.create_settings("pg_talk:" + self.key())), 14)
        self.assertLessEqual(len(self.p.create_settings("pg_cmem:" + self.key())), 14)

    def test_memory_off(self):
        self.p.settings["memory_" + self.sk] = False
        rows = self.p.create_settings("pg_cmem:" + self.key())
        self.assertEqual(len(rows), 1)


class TestCloudDelete(CloudBase):
    def test_danger_row_only_when_the_cloud_is_on(self):
        sk = self.p._sk(self.key())
        self.p._is_group = lambda key: False
        keys = lambda: [getattr(r, "key", None) for r in self.p._pg_memory_page({}, self.key())]
        self.assertNotIn("mem_cloud_del_" + sk, keys())
        self.active()
        self.assertIn("mem_cloud_del_" + sk, keys())


class TestBudget(CloudBase):
    def test_query_from_incoming_then_fallback(self):
        self.active()
        msgs = [{"role": "user", "content": u"[12:00] Помнишь про поездку в Львов?"}]
        self.context_rows = [self.memory_row(2, u"Поездка в Львов в мае")]
        self.assertIn(u"Львов в мае", self.p._cloud_context(self.key(), 0, DID, msgs))
        self.assertEqual(self.calls[-1][0], "context")
        self.assertIn(u"поездку", self.calls[-1][4])
        self.context_rows = []
        n = len(self.calls)
        self.p._cloud_context(self.key(), 0, DID, msgs)
        queries = [c[4] for c in self.calls[n:] if c[0] == "context"]
        self.assertEqual(len(queries), 2)
        self.assertEqual(queries[1], "")

    def test_cloud_query(self):
        self.assertEqual(mod.cloud_query([{"role": "user", "content": "ok 12"}]), "")
        self.assertEqual(mod.cloud_query([]), "")
        self.assertEqual(len(mod.cloud_query([{"role": "user", "content": u"слово " * 100}])), 200)
        self.assertEqual(mod.cloud_query([{"role": "user", "content": u"первое"},
                                          {"role": "assistant", "content": u"ответ"}]), u"первое")

    def test_budget_limits_the_cloud_block(self):
        self.active()
        self.context_rows = [self.memory_row(i, u"Текст " + u"а" * 900) for i in range(1, 21)]
        block = self.p._cloud_context(self.key(), 0, DID, [], budget=1500)
        self.assertLessEqual(len(block), 2000)
        self.assertIn(u"Текст", block)


if __name__ == "__main__":
    unittest.main()
