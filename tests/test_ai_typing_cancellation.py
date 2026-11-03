"""Owner/settings cancellation must stop the wait and typing, not only the later text send."""
from unittest.mock import patch
from test_ai_autoreply import Base, CLIENT, DID, mod


class TestTypingCancellation(Base):
    def setUp(self):
        super().setUp()
        self.enable()
        self.p.settings.update(disclosure=False,typing_delay=True,show_typing=True)
        self.actions=[]
        self.sleeps=[]

    def record_typing(self,did,account,cancel=False):
        self.actions.append(('cancel' if cancel else 'typing',did,account))
        return True

    def owner_on_first_chunk(self,seconds):
        self.sleeps.append(seconds)
        # Deliberately no clock advance: owner_seq must work when timestamp equality cannot distinguish events.
        if len(self.sleeps)==1:
            self.p._note_owner(self.key(),{'id':999,'text':'Отвечаю сам'})

    def deliver(self,parts,timing=None):
        return self.p.deliver(self.key(),self.p._chats[self.key()],self.p._state(self.key()),DID,parts,[],True,timing=timing)

    def test_balanced_long_reply_stops_after_first_chunk_and_cancels_typing(self):
        with patch.object(self.p,'_send_typing',self.record_typing),patch.object(mod.time,'sleep',self.owner_on_first_chunk):
            self.assertFalse(self.deliver(['x'*1000]))
        self.assertEqual(self.sleeps,[mod.TYPING_REFRESH_SEC])
        self.assertEqual([a[0] for a in self.actions],['typing','cancel'])
        self.assertEqual(CLIENT.sent,[])
        self.assertEqual(self.p._state(self.key()).abort,'owner replied')

    def test_explicit_typing_cap_uses_cancellable_chunks_without_enabling_indicator(self):
        self.p.settings['typing_cap']='15'
        with patch.object(self.p,'_send_typing',self.record_typing),patch.object(mod.time,'sleep',self.owner_on_first_chunk):
            self.assertFalse(self.deliver(['x'*1000]))
        self.assertEqual(self.sleeps,[mod.TYPING_REFRESH_SEC])
        self.assertEqual([a[0] for a in self.actions],['cancel'])
        self.assertEqual(CLIENT.sent,[])

    def test_direct_delivery_detects_owner_between_parts_without_work_context(self):
        self.assertIsNone(getattr(self.p._work_context,'task',None))
        sent=[]
        def send(did,text,reply_to=None,account=None):
            sent.append(text)
            self.p._note_owner(self.key(),{'id':999,'text':'Дальше отвечу сам'})
        with patch.object(CLIENT,'send_text',send),patch.object(self.p,'_send_typing',self.record_typing),\
                patch.object(mod.time,'sleep',lambda seconds:self.sleeps.append(seconds)):
            self.assertFalse(self.deliver(['first','second']))
        self.assertEqual(sent,['first'])
        self.assertEqual(len(self.sleeps),1)
        self.assertEqual([a[0] for a in self.actions],['typing','cancel'])

    def test_already_expired_owner_guard_does_not_start_typing_or_sleep(self):
        st=self.p._state(self.key())
        self.p._work_context.task=(self.key(),self.p._epoch(self.key()))
        self.p._work_context.owner_guard=(self.key(),st.owner_seq)
        self.p._note_owner(self.key(),{'id':999,'text':'Уже отвечено'})
        with patch.object(self.p,'_send_typing',self.record_typing),patch.object(mod.time,'sleep',lambda seconds:self.sleeps.append(seconds)):
            self.assertFalse(self.p._wait_typing(DID,0,20))
        self.assertEqual(self.sleeps,[])
        self.assertEqual([a[0] for a in self.actions],['cancel'])

    def test_pause_then_reenable_does_not_resume_an_old_direct_wait(self):
        def change_settings(seconds):
            self.sleeps.append(seconds)
            self.p.chat_off(self.key(),False)
            self.p.chat_on(0,DID,'Alice','user')
        with patch.object(self.p,'_send_typing',self.record_typing),patch.object(mod.time,'sleep',change_settings):
            self.assertFalse(self.deliver(['x'*1000]))
        self.assertEqual(len(self.sleeps),1)
        self.assertEqual(self.actions[-1][0],'cancel')
        self.assertEqual(CLIENT.sent,[])

    def test_global_settings_epoch_cancels_a_wait(self):
        def change_epoch(seconds):
            self.sleeps.append(seconds);self.p._config_epoch+=1
        with patch.object(self.p,'_send_typing',self.record_typing),patch.object(mod.time,'sleep',change_epoch):
            self.assertFalse(self.p._wait_typing(DID,0,20))
        self.assertEqual(len(self.sleeps),1)
        self.assertEqual([a[0] for a in self.actions],['typing','cancel'])

    def test_unload_cancels_even_without_work_context(self):
        def unload(seconds):
            self.sleeps.append(seconds);self.p._scan_stop=True
        with patch.object(self.p,'_send_typing',self.record_typing),patch.object(mod.time,'sleep',unload):
            self.assertFalse(self.p._wait_typing(DID,0,20))
        self.assertEqual(len(self.sleeps),1)
        self.assertEqual(self.actions[-1][0],'cancel')

    def test_live_quiet_phase_cancellation_happens_before_read_or_typing(self):
        reads=[]
        timing={'wait':20,'type':8,'arr':self.clock[0],'read_id':12}
        with patch.object(self.p,'_send_typing',self.record_typing),patch.object(mod.time,'sleep',self.owner_on_first_chunk),\
                patch.object(self.p,'_mark_read',lambda *args:reads.append(args)):
            self.assertFalse(self.deliver(['reply'],timing=timing))
        self.assertEqual(self.sleeps,[mod.TYPING_REFRESH_SEC])
        self.assertEqual(reads,[])
        self.assertEqual([a[0] for a in self.actions],['cancel'])

    def test_live_typing_phase_uses_same_time_owner_sequence_guard(self):
        timing={'wait':20,'type':20,'arr':self.clock[0]}
        with patch.object(self.p,'_send_typing',self.record_typing),patch.object(mod.time,'sleep',self.owner_on_first_chunk):
            self.assertFalse(self.deliver(['reply'],timing=timing))
        self.assertEqual(self.sleeps,[mod.TYPING_REFRESH_SEC])
        self.assertEqual([a[0] for a in self.actions],['typing','cancel'])
        self.assertEqual(CLIENT.sent,[])

    def test_owner_event_triggered_by_typing_action_is_checked_before_sleep(self):
        def typing(did,account,cancel=False):
            self.record_typing(did,account,cancel)
            if not cancel:self.p._note_owner(self.key(),{'id':999,'text':'Я отвечу'})
            return True
        with patch.object(self.p,'_send_typing',typing),patch.object(mod.time,'sleep',lambda seconds:self.sleeps.append(seconds)):
            self.assertFalse(self.p._wait_typing(DID,0,20))
        self.assertEqual(self.sleeps,[])
        self.assertEqual([a[0] for a in self.actions],['typing','cancel'])

    def test_standalone_wait_without_allowlist_or_work_context_still_works(self):
        with patch.object(self.p,'_send_typing',self.record_typing),patch.object(mod.time,'sleep',lambda seconds:self.sleeps.append(seconds)):
            self.assertTrue(self.p._wait_typing(123456,0,10))
        self.assertEqual(sum(self.sleeps),10)
        self.assertNotIn('cancel',[a[0] for a in self.actions])

