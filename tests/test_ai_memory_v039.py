"""Memory integration tests; fake Zephyr/model, persistent local fixture files only."""
from pathlib import Path
import json
import uuid

from test_ai_autoreply import Base, CLIENT, DID, chats_screen, mod


class TestCompactMemory(Base):
    def setUp(self):
        super().setUp()
        self.enable()
        self.sk = self.p._sk(self.key())
        self.root = Path(__file__).resolve().parents[1] / "out" / "test-memory-integration" / uuid.uuid4().hex
        self.root.mkdir(parents=True)
        self.p.data_dir = str(self.root)
        self.owners = {0: 111, 1: 333}
        self.p._memory_owner_id = lambda account: self.owners.get(account)
        self.calls = []
        self.original_ai = CLIENT.ai_complete
        self.original_history = CLIENT.get_recent_messages
        self.original_media = getattr(CLIENT, "get_message_media", None)
        self.original_voice = getattr(CLIENT, "get_voice", None)
        CLIENT.ai_complete = self.complete
        CLIENT.get_recent_messages = lambda did, limit=20, account=None: list(CLIENT.history)[-limit:]
        CLIENT.get_message_media = lambda *a, **k: self.fail("Memory fetched media")
        CLIENT.get_voice = lambda *a, **k: self.fail("Memory fetched audio")
        CLIENT.history[:] = self.history()

    def tearDown(self):
        CLIENT.ai_complete = self.original_ai
        CLIENT.get_recent_messages = self.original_history
        for name,value in (("get_message_media",self.original_media),("get_voice",self.original_voice)):
            if value is None:
                if hasattr(CLIENT,name):delattr(CLIENT,name)
            else:setattr(CLIENT,name,value)

    def history(self, count=42, account=0, did=DID):
        return [{"id":i,"date":1000+i,"text":"actual text %d"%i,"out":bool(i%2),
                 "from_id":7 if i%2==0 else 111,"dialog_id":did,"account":account,
                 "audio_b64":"NEVER_COPY_AUDIO","image_b64":"NEVER_COPY_IMAGE"}
                for i in range(1,count+1)]

    def complete(self,messages,**kwargs):
        self.calls.append((messages,kwargs))
        if kwargs.get("system","").startswith("Summarize only"):
            return json.dumps({"summary":"A bounded fact from the actual older conversation."})
        return "Here is the answer to the current question."

    def opt_in(self):
        self.p.settings["memory_"+self.sk]=True

    def store(self, owner=111):
        return self.p._memory_for_owner(0,owner)

    def context(self, **kwargs):
        return self.p._memory_context(self.key(),0,DID,**kwargs)

    def test_off_by_default_no_io_or_extra_model_calls(self):
        self.assertEqual(self.context(),"")
        self.assertEqual(self.calls,[])
        self.assertEqual(list(self.root.iterdir()),[])
        self.p._open_key=self.key()
        setting=next(item for item in chats_screen(self.p) if getattr(item,"key",None)=="memory_"+self.sk)
        self.assertFalse(setting.default)
        self.assertIn("AI server",setting.subtext)

    def test_summary_uses_only_old_text_metadata_and_explicit_model(self):
        self.opt_in()
        self.p.settings["model"]="owner-selected-model"
        self.p._work_context.task=(self.key(),self.p._config_epoch)
        self.p._work_context.images=["CURRENT_IMAGE_MUST_NOT_ATTACH"]
        block=self.context(messages=[{"role":"user","content":"actual text 7"}])
        self.assertIn("untrusted_chat_memory_json",block)
        self.assertEqual(len(self.calls),1)
        messages,kwargs=self.calls[0]
        self.assertNotIn("images",kwargs)
        self.assertEqual(kwargs["model"],"owner-selected-model")
        raw=messages[0]["content"]
        self.assertNotIn("NEVER_COPY",raw)
        payload=json.loads(raw)
        ids=[row["id"] for row in payload["messages"]]
        self.assertLessEqual(max(ids),30)
        self.assertNotIn(7,ids)
        self.assertTrue(all(set(row)=={"id","date","out","from_id","text"} for row in payload["messages"]))
        self.assertLessEqual(len(raw),16000)
        record=self.store().get_summary(0,DID,enabled=True)
        self.assertEqual(record["through_id"],30)
        self.assertEqual(record["revision"],1)
        self.assertEqual(CLIENT.sent,[])

    def test_reuses_summary_and_does_not_call_model_on_every_reply(self):
        self.opt_in()
        first=self.context()
        self.assertTrue(first)
        self.assertEqual(self.context(),first)
        self.assertEqual(len(self.calls),1)
        self.clock[0]+=601
        self.assertEqual(self.context(),first)
        self.assertEqual(len(self.calls),1)

    def test_failures_throttled_without_disabling_normal_chat(self):
        self.opt_in()
        def invalid(messages,**kwargs):
            self.calls.append((messages,kwargs));return "not a summary JSON"
        CLIENT.ai_complete=invalid
        self.assertEqual(self.context(),"")
        self.assertEqual(self.context(),"")
        self.assertEqual(len(self.calls),1)
        self.assertTrue(self.p.is_enabled(self.key()))
        self.assertEqual(self.p._chats[self.key()].get("fails",0),0)
        self.clock[0]+=601
        self.assertEqual(self.context(),"")
        self.assertEqual(len(self.calls),2)

    def test_epoch_change_after_model_prevents_summary_commit(self):
        self.opt_in()
        self.p._work_context.task=(self.key(),self.p._config_epoch)
        def late(messages,**kwargs):
            self.p.on_app_event("settings_changed")
            return json.dumps({"summary":"late private facts"})
        CLIENT.ai_complete=late
        self.assertEqual(self.context(),"")
        self.assertIsNone(self.store().get_summary(0,DID,enabled=True))

    def test_revocation_during_model_prevents_summary_commit(self):
        self.opt_in()
        def late(messages,**kwargs):
            self.p.settings["memory_"+self.sk]=False
            return json.dumps({"summary":"revoked private facts"})
        CLIENT.ai_complete=late
        self.assertEqual(self.context(),"")
        self.assertIsNone(self.store().get_summary(0,DID,enabled=True))

    def test_slot_reuse_or_missing_account_identity_cannot_reuse_old_owner_memory(self):
        self.opt_in()
        self.assertTrue(self.context())
        old_path=self.store().path
        CLIENT.history[:]=[]
        self.owners[0]=222
        self.assertEqual(self.context(),"")
        self.assertNotEqual(self.store(222).path,old_path)
        self.assertTrue(Path(old_path).exists())
        self.owners.pop(0)
        self.assertEqual(self.context(),"")

    def test_owner_switch_during_model_prevents_summary_commit(self):
        self.opt_in()
        def late(messages,**kwargs):
            self.owners[0]=222
            return json.dumps({"summary":"another owner must not inherit this"})
        CLIENT.ai_complete=late
        self.assertEqual(self.context(),"")
        self.assertIsNone(self.store(111).get_summary(0,DID,enabled=True))

    def test_history_scope_and_secret_service_forwarded_rows_filtered(self):
        self.opt_in()
        rows=self.history(60)
        rows[0]["account"]=1
        rows[1]["dialog_id"]=999
        rows[2]["is_secret"]=True
        rows[3]["is_service"]=True
        rows[4]["is_forwarded"]=True
        rows[5]["fwd_from"]={"user":99}
        CLIENT.history[:]=rows
        self.assertTrue(self.context())
        payload=json.loads(self.calls[0][0][0]["content"])
        self.assertFalse(set(range(1,7)) & {row["id"] for row in payload["messages"]})
        self.assertEqual(self.p._memory_context("1:42",0,DID),"")
        self.assertIsNone(self.store().get_summary(1,DID,enabled=True))

    def test_restrict_payload_and_summary_lengths(self):
        self.opt_in()
        CLIENT.history[:]=[dict(row,text="bounded text "*1000)for row in self.history(100)]
        self.assertTrue(self.context())
        self.assertLessEqual(len(self.calls[0][0][0]["content"]),16000)
        self.assertGreaterEqual(len(json.loads(self.calls[0][0][0]["content"])["messages"]),10)

    def test_both_generation_modes_use_memory_without_changing_current_question(self):
        self.opt_in()
        store=self.store()
        self.assertTrue(store.set_summary(0,DID,"old fact",30,enabled=True))
        messages=[{"role":"user","content":"CURRENT QUESTION MUST REMAIN"}]
        original=json.loads(json.dumps(messages))
        self.p.settings["humanize"]=False
        self.p.generate(self.key(),0,DID,messages,self.p._chats[self.key()],None)
        self.assertIn("COMPACT CHAT MEMORY",self.calls[-1][1]["system"])
        self.assertEqual(self.calls[-1][0],original)
        self.p.settings["humanize"]=True
        self.p.get_profile=lambda *a,**k:{"examples":[],"style":{}}
        self.p.reply_problems=lambda *a,**k:[]
        self.p.generate(self.key(),0,DID,messages,self.p._chats[self.key()],None)
        self.assertIn("COMPACT CHAT MEMORY",self.calls[-1][1]["system"])
        self.assertEqual(messages,original)
        self.assertEqual(CLIENT.sent,[])


if __name__=="__main__":
    import unittest
    unittest.main(verbosity=2)
