"""Regression cases from the exported task backlog; synthetic data, no provider calls."""
import json
from unittest.mock import patch
from test_ai_autoreply import Base, CLIENT, DID, mod, screen


class TestOwnerCancellation(Base):
    def test_manual_response_during_generation_cancels_balanced_reply_even_same_timestamp(self):
        self.enable()
        self.p.settings.update(typing_delay=False, owner_active='0')
        def complete(_messages):
            self.p._note_owner(self.key(), {'id':99,'text':'Я отвечу сам'})
            return 'hello back'
        CLIENT.ai_result=complete
        self.incoming(text='hello',mid=98)
        self.fire_timers()
        self.assertEqual(CLIENT.sent,[])
        self.assertEqual(self.p._state(self.key()).owner_seq,1)

    def test_manual_text_during_sending_is_not_ignored(self):
        self.enable();st=self.p._state(self.key());st.sending=True
        self.p._note_owner(self.key(),{'id':88,'text':'Пишу вручную'})
        self.assertEqual(st.owner_seq,1)

    def test_each_part_rechecks_owner_cancellation(self):
        self.enable();st=self.p._state(self.key());self.p.settings.update(typing_delay=False,disclosure=False)
        sends=[]
        def send(*args,**kwargs):
            sends.append(args[1]);self.p._note_owner(self.key(),{'id':55,'text':'Дальше я сам'})
        with patch.object(CLIENT,'send_text',send):
            self.assertFalse(self.p.deliver(self.key(),self.p._chats[self.key()],st,DID,['first','second'],[],True))
        self.assertEqual(sends,['first'])

    def test_plugin_text_echo_is_not_owner_activity(self):
        self.enable();self.p._remember_bot_text('собственный ответ')
        self.p._note_owner(self.key(),{'id':42,'text':'собственный ответ'})
        self.assertEqual(self.p._state(self.key()).owner_seq,0)


class TestScopedCommands(Base):
    def test_off_and_pause_keep_settings_delete_removes_only_selected_account(self):
        self.enable();self.enable(account=1)
        key=self.key();other=self.p.chat_key(1,DID);sk=self.p._sk(key);osk=self.p._sk(other)
        self.p.settings['prompt_'+sk]='first';self.p.settings['prompt_'+osk]='second'
        self.p._run_admin(0,DID,key,'off','')
        self.assertFalse(self.p._chats[key]['enabled'])
        self.assertEqual(self.p.settings['prompt_'+sk],'first')
        self.assertTrue(self.p._chats[other]['enabled'])
        self.p._run_admin(0,DID,key,'on','')
        self.p._run_admin(0,DID,key,'pause','')
        self.assertEqual(self.p.settings['prompt_'+sk],'first')
        self.p._run_admin(0,DID,key,'delete','')
        self.assertNotIn(key,self.p._chats)
        self.assertEqual(self.p.settings['prompt_'+osk],'second')

    def test_pause_invalidates_inflight_even_after_reenable(self):
        self.enable();key=self.key();epoch=self.p._epoch(key)
        self.p._work_context.task=(key,epoch)
        self.p.chat_off(key,False);self.p.chat_on(0,DID,'Alice','user')
        self.assertFalse(self.p._task_alive(key,0,DID))

    def test_russian_aliases_with_existing_default_trigger_preference(self):
        self.p.settings['cmd_triggers']='.ai, .аі'
        for text,verb in [('.аи офф','off'),('.аи пауза','pause'),('.аи удалить','delete'),('.ai delete','delete'),('.аи старт','start')]:
            self.assertEqual(self.p.parse_admin(text),(verb,''))

    def test_dialog_info_does_not_fall_back_to_wrong_account(self):
        with patch.object(CLIENT,'get_dialog_info',lambda did:{'title':'wrong-account'}):
            with self.assertRaises(RuntimeError):self.p._dialog_info(1,DID)

    def test_owner_command_and_polite_stop_send_to_explicit_account(self):
        self.enable(account=1);key=self.p.chat_key(1,DID);sent=[]
        self.p.settings.update(typing_delay=False,cmd_cooldown='0')
        with patch.object(CLIENT,'send_text',lambda did,text,reply_to=None,account=None:sent.append(account)):
            self.p._polite_stop(key,self.p._chats[key],self.p._state(key),DID,[])
            self.p._run_command(1,DID,key,False,'say hello')
        self.assertTrue(sent);self.assertEqual(set(sent),{1})


class TestRepliesAndContext(Base):
    def test_sentence_boundary_wins_even_when_shorter_than_half_limit(self):
        text='Готово. '+('длинная следующая мысль '*10)
        self.assertEqual(mod.cap_text(text,100),'Готово.')

    def test_hard_limit_without_sentence_boundary_is_explicit(self):
        result=mod.cap_text('длинное слово '*100,80)
        self.assertLessEqual(len(result),80);self.assertTrue(result.endswith('…'))

    def test_decimal_point_is_not_a_sentence_boundary(self):
        text='Стоимость 3.14 и ещё много текста '*20
        result=mod.cap_text(text,40)
        self.assertNotEqual(result,'Стоимость 3.')

    def test_clock_dates_do_not_modify_message_text_and_do_not_cross_chats(self):
        self.enable();key=self.key()
        hist=[{'id':1,'date':self.clock[0]-7*86400,'text':'новость прошлой недели','out':False}]
        self.p.build_messages(key,0,DID,[(2,7,'а как сейчас?')],hist=hist)
        block=self.p._clock_block(key)
        self.assertIn('Current UTC time:',block);self.assertIn('новость прошлой недели',block)
        self.assertIn(self.p._utc_stamp(hist[0]['date']),block)
        self.assertNotIn('новость прошлой недели',self.p._clock_block('1:42'))
        self.assertIsNone(self.p._utc_stamp(float('nan')))

    def test_lore_replace_excludes_global_and_structured_fields(self):
        self.enable();key=self.key();sk=self.p._sk(key)
        self.p.settings.update(lore='глобальный факт',lore_name='Имя владельца')
        self.p.settings['lore_'+sk]='только этот чат'
        self.assertIn('глобальный факт',self.p._lore_block(key))
        self.p.settings['lore_mode_'+sk]=1
        block=self.p._lore_block(key)
        self.assertNotIn('глобальный факт',block);self.assertNotIn('Имя владельца',block)
        self.assertIn('только этот чат',block)

    def test_model_dropdown_preserves_custom_and_has_working_callback(self):
        self.p.settings['model']='custom-model'
        picker=self.p._model_picker();self.assertEqual(picker.default,len(self.p.MODEL_PRESETS))
        picker.on_change(1);self.assertEqual(self.p._model_for('reply'),'glm-5.3')
        picker.on_change(999);self.assertEqual(self.p._model_for('reply'),'glm-5.3')
        self.assertTrue(any(getattr(i,'key',None)=='model_pick' for i in screen(self.p,'prompts')))

    def test_scan_recovers_orphaned_pending_without_duplicate_new_input(self):
        self.enable();key=self.key();st=self.p._state(key)
        st.pending=[(11,7,'hello')];st.first_ts=self.clock[0];st.last_ts=self.clock[0]
        self.p._scan_chat(key,self.p._chats[key])
        self.assertTrue(st.timer);self.assertTrue(CLIENT.ui_queue)
        self.assertIn('pending_timer_recovered',self.p.decisions_text())

    def test_voice_wait_uses_duration_after_generation_time(self):
        self.enable();key=self.key();st=self.p._state(key);self.p.settings['disclosure']=False
        self.p._media_pending[(key,1)]={'epoch':self.p._epoch(key),'received_at':self.clock[0]-20,'voice_duration':120}
        timing=[]
        with patch.object(self.p,'_live_wait',lambda *args:timing.append(args[-1]) or True):
            self.p.deliver(key,self.p._chats[key],st,DID,['reply'],[(1,7,'voice')],False)
        self.assertEqual(timing[0]['wait'],100)

