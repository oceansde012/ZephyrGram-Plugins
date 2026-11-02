"""Group speakers, reply targets and topic scopes; no provider calls."""
from types import SimpleNamespace
from unittest.mock import patch
from test_ai_autoreply import Base, CLIENT, DID, mod, chats_screen

GROUP = -100500


class TestGroupParticipants(Base):
    def setUp(self):
        super().setUp()
        CLIENT.info = {'id':GROUP, 'title':'Public group', 'type':'group', 'is_bot':False, 'username':'public_group'}
        self.enable(did=GROUP)
        self.group_key = self.p.chat_key(0,GROUP)

    def row(self, mid, sender, text, topic=11, out=False, reply_to=None):
        return {'id':mid, 'dialog_id':GROUP, 'account':0, 'from_id':sender, 'from_name':'Alex',
                'out':out, 'date':self.clock[0]-100+mid, 'text':text, 'topic_id':topic,
                'reply_to':reply_to, 'is_service':False}

    def test_two_people_same_name_owner_and_reply_target_stay_distinct(self):
        rows=[self.row(1,11,'Мне 34'),self.row(2,99,'Я отвечаю за встречу',out=True),
              self.row(3,22,'А мне 28'),self.row(4,11,'Вопрос Алексу',reply_to=3)]
        with patch.object(self.p,'_memory_owner_id',lambda account:99):
            messages=self.p.build_messages(self.group_key,0,GROUP,[(4,11,'Вопрос Алексу')],hist=rows)
        text='\n'.join(m['content'] for m in messages)
        self.assertIn('[user user:11;',text)
        self.assertIn('[user user:22;',text)
        self.assertIn('[owner owner:user:99;',text)
        self.assertIn('reply_to:3; reply_sender:user:22',text)
        self.assertNotIn('Alex',text)  # coinciding display names are not identifiers

    def test_two_forum_topics_have_independent_history_even_for_same_people(self):
        rows=[self.row(1,11,'факт из первой темы'),self.row(2,22,'факт из второй',topic=22),
              self.row(3,11,'ответь здесь',topic=11),self.row(4,22,'ответь там',topic=22)]
        first=self.p.build_messages(self.group_key,0,GROUP,[(3,11,'ответь здесь')],hist=rows)
        second=self.p.build_messages(self.group_key,0,GROUP,[(4,22,'ответь там')],hist=rows)
        self.assertNotIn('факт из второй',str(first));self.assertIn('факт из первой темы',str(first))
        self.assertNotIn('факт из первой темы',str(second));self.assertIn('факт из второй',str(second))

    def test_cross_topic_reply_does_not_reveal_other_topic_or_invent_sender(self):
        rows=[self.row(1,22,'другая тема',topic=22),self.row(2,11,'видишь мой вопрос?',reply_to=1)]
        messages=self.p.build_messages(self.group_key,0,GROUP,[(2,11,'видишь мой вопрос?')],hist=rows)
        text=str(messages)
        self.assertNotIn('другая тема',text);self.assertIn('reply_to:1; reply_sender:unknown',text)

    def test_unknown_topic_metadata_uses_one_current_message_without_cached_history(self):
        rows=[self.row(1,11,'история без темы'),self.row(2,22,'новый вопрос')]
        for row in rows:row.pop('topic_id')
        messages=self.p.build_messages(self.group_key,0,GROUP,[(2,22,'новый вопрос')],hist=rows)
        self.assertEqual(len(messages),1)
        self.assertNotIn('история без темы',str(messages))
        self.assertIn('новый вопрос',str(messages))

    def test_process_partitions_topics_before_loading_context(self):
        one=self.row(1,11,'тема один');two=self.row(2,22,'тема два',topic=22)
        for row in [one,two]:self.p._remember_group_metadata(self.group_key,row)
        calls=[]
        with patch.object(self.p,'_process',lambda key,batch:calls.append((self.p._work_context.group_scope,list(batch))) or 'ok'):
            self.p.process(self.group_key,[(1,11,'тема один'),(2,22,'тема два')])
        self.assertEqual([c[0][1] for c in calls],[11,22])
        self.assertEqual([len(c[1]) for c in calls],[1,1])

    def test_unknown_topics_do_not_get_batched_together(self):
        calls=[]
        with patch.object(self.p,'_process',lambda key,batch:calls.append(list(batch)) or 'ok'):
            self.p.process(self.group_key,[(1,11,'один'),(2,22,'два')])
        self.assertEqual(len(calls),2)
        self.assertTrue(all(len(c)==1 for c in calls))
        partitions=self.p._group_batches(self.group_key,[(None,11,'первый'),(None,22,'второй')])
        self.assertEqual(len(partitions),2)

    def test_live_group_batch_replies_in_source_topics_and_plain_mode_has_group_rules(self):
        self.p.settings.update(humanize=False,typing_delay=False,group_need_question=False,disclosure=False,
                               skip_ack=False,owner_active='0')
        one=self.row(21,11,'первый вопрос?',topic=11)
        two=self.row(22,22,'второй вопрос?',topic=22)
        for row in [one,two]:
            row['date']=self.clock[0]
            self.p._handle_dict(0,GROUP,row)
        CLIENT.ai_result=lambda messages:'готово'
        self.fire_timers()
        self.assertEqual([m[2] for m in CLIENT.sent],[21,22])
        self.assertEqual(len(CLIENT.ai_calls),2)
        self.assertIn('multi-person group',CLIENT.ai_calls[0]['system'])
        self.assertNotIn('второй вопрос?',str(CLIENT.ai_calls[0]['messages']))
        self.assertNotIn('первый вопрос?',str(CLIENT.ai_calls[1]['messages']))

    def test_stale_user_type_on_negative_group_peer_cannot_change_it_to_private(self):
        CLIENT.info['type']='user'
        self.p.settings.update(group_need_question=False,typing_delay=False)
        row=self.row(12,11,'как дела?');row['date']=self.clock[0]
        self.p._handle_dict(0,GROUP,row)
        self.fire_timers()
        self.assertEqual(CLIENT.ai_calls,[])
        self.assertEqual(CLIENT.sent,[])

    def test_confirmed_plain_group_keeps_ordinary_multi_person_history(self):
        rows=[self.row(1,11,'первая реплика'),self.row(2,22,'вторая реплика')]
        for row in rows:row.pop('topic_id');row['is_forum']=False
        messages=self.p.build_messages(self.group_key,0,GROUP,[(2,22,'вторая реплика')],hist=rows)
        self.assertIn('первая реплика',str(messages));self.assertIn('вторая реплика',str(messages))

    def test_group_gender_override_is_not_applied_to_everyone(self):
        self.p.settings['gender_'+self.p._sk(self.group_key)]=2
        self.p.settings['owner_gender']=0
        block=self.p._gender_block(self.group_key,[])
        self.assertIn('not one interlocutor',block)
        self.assertNotIn(mod.GENDER_RULES['f'],block)
        self.assertNotIn(mod.GENDER_RULES['m'],block)

    def test_old_flat_group_memory_and_learned_facts_do_not_leak_into_prompt(self):
        sk=self.p._sk(self.group_key)
        self.p.settings['memory_'+sk]=True
        self.p.settings['learned_'+sk]='Алекс 34, живёт в чужой теме'
        self.p.settings['lore_'+sk]='Обсуждаем проект'
        self.assertFalse(self.p._memory_flag(self.group_key))
        self.assertNotIn('34',self.p._lore_block(self.group_key))
        self.assertIn('Обсуждаем проект',self.p._lore_block(self.group_key))
        self.p.settings['lore_learn']=True
        self.p._learn_notes(self.group_key,self.p._state(self.group_key))
        self.assertEqual(CLIENT.ai_calls,[])

    def test_group_settings_do_not_offer_one_gender_or_unscoped_memory(self):
        self.p._open_key=self.group_key
        keys={getattr(i,'key',None) for i in chats_screen(self.p)}
        sk=self.p._sk(self.group_key)
        self.assertNotIn('gender_'+sk,keys);self.assertNotIn('memory_'+sk,keys)
        self.assertNotIn('learned_'+sk,keys)

    def test_account_and_chat_cache_keys_prevent_same_message_id_collision(self):
        self.p._remember_group_metadata(self.group_key,self.row(1,11,'первая',topic=11))
        other=self.p.chat_key(1,GROUP)
        self.p._chats[other]={'enabled':True,'type':'group','account':1,'dialog_id':GROUP}
        row=self.row(1,22,'другая',topic=22);row['account']=1
        self.p._remember_group_metadata(other,row)
        self.assertEqual(self.p._group_meta[(self.group_key,1)]['topic_id'],11)
        self.assertEqual(self.p._group_meta[(other,1)]['topic_id'],22)

    def test_anonymous_or_missing_senders_are_not_guessed_as_a_named_user(self):
        self.assertEqual(self.p._speaker(self.group_key,{'id':1,'from_id':-123}),'chat:123')
        self.assertNotEqual(self.p._speaker(self.group_key,{'id':1}),self.p._speaker(self.group_key,{'id':2}))
        block=self.p.build_system(self.group_key,{})
        self.assertIn('not a verified personal identity',block)

    def test_native_header_can_supply_topic_while_ordinary_reply_id_cannot(self):
        header=SimpleNamespace(forum_topic=True,reply_to_msg_id=5,reply_to_top_id=11)
        mo=SimpleNamespace(messageOwner=SimpleNamespace(reply_to=header,peer_id=SimpleNamespace(chat_id=0)))
        message=self.p._with_group_metadata({'id':6,'reply_to':5},mo)
        self.assertEqual(message['topic_id'],11)
        header.forum_topic=False
        self.assertIsNone(self.p._topic_of(self.p._with_group_metadata({'id':6,'reply_to':5},mo)))

    def test_reply_target_is_not_dropped_when_old_host_cannot_support_it(self):
        with patch.object(CLIENT,'send_text',lambda did,text:None):
            with self.assertRaises(RuntimeError):self.p.send(GROUP,'reply',123,account=0)

    def test_public_broadcast_channel_remains_disallowed(self):
        self.assertEqual(self.p.check_info({'type':'channel','username':'public_channel'}),'channel')
        self.p._chats[self.group_key]['type']='channel'
        self.assertFalse(self.p._is_group(self.group_key))


class TestPrivateContextUnchanged(Base):
    def test_private_history_does_not_gain_group_labels_or_topic_requirements(self):
        self.enable()
        hist=[{'id':1,'from_id':DID,'out':False,'date':1,'text':'привет'},
              {'id':2,'from_id':99,'out':True,'date':2,'text':'привет и тебе'}]
        messages=self.p.build_messages(self.key(),0,DID,[(3,DID,'как дела?')],hist=hist)
        self.assertEqual(messages[-1]['content'],'как дела?')
        self.assertIn({'role':'user','content':'привет'},messages)
        self.assertNotIn('reply_sender',str(messages))

