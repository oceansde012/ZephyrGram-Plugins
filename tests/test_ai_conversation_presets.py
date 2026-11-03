"""Conversation presets: selection boundaries and the actual one-call generation contract."""
import copy
from test_ai_autoreply import Base, CLIENT, DID, mod, screen


class TestConversationPresets(Base):
    def setUp(self):
        super().setUp()
        self.enable()
        self.p.settings.update(natural_chat=True, memory_auto=False, learn_style=False)

    def generate(self, text='як ти?'):
        CLIENT.ai_result=lambda messages:'та нормально'
        self.p.generate(self.key(),0,DID,[{'role':'user','content':text}],
                        self.p._chats[self.key()],self.p._state(self.key()))
        return CLIENT.ai_calls[-1]['system']

    def test_all_four_presets_reach_generation_without_forced_jokes_or_identity_denial(self):
        for i, rule in enumerate(mod.CHAT_PROMPT_PRESETS):
            with self.subTest(preset=i):
                self.p.settings['conversation_style']=i
                before=len(CLIENT.ai_calls)
                system=self.generate()
                self.assertIn(rule,system)
                self.assertEqual(len(CLIENT.ai_calls)-before,1)
                self.assertIn(mod.DISCLOSE_RULE,system)
                self.assertNotIn('a bit of humor',system)
                self.assertNotIn('you ARE the owner',system)

    def test_per_chat_override_does_not_change_other_chat_or_global_choice(self):
        self.p.settings['conversation_style']=2
        self.p.settings['conversation_style_'+self.p._sk(self.key())]=2  # warm: local index 1-based
        other=self.p.chat_key(0,99)
        self.assertEqual(self.p._chat_style_index(self.key()),1)
        self.assertEqual(self.p._chat_style_index(other),2)
        self.p.settings['conversation_style_'+self.p._sk(self.key())]=0
        self.assertEqual(self.p._chat_style_index(self.key()),2)

    def test_corrupt_local_setting_falls_back_without_cross_chat_reconfiguration(self):
        self.p.settings['conversation_style']=3
        for bad in ('oops',None,99,-1):
            self.p.settings['conversation_style_'+self.p._sk(self.key())]=bad
            self.assertEqual(self.p._chat_style_index(self.key()),3)

    def test_selection_changes_only_wording_not_permissions_models_or_timing(self):
        settings=copy.deepcopy(self.p.settings)
        chats=copy.deepcopy(self.p._chats)
        before=self.p._preset()
        for index in range(4):
            self.p.settings['conversation_style']=index
            self.p.build_system(self.key(),{})
            self.assertEqual(self.p._preset(),before)
            self.assertEqual(self.p._chats,chats)
        del self.p.settings['conversation_style']
        self.assertEqual(self.p.settings,settings)

    def test_warm_tone_does_not_require_jokes_or_familiarity(self):
        self.p.settings.update(conversation_style=1,tone=1)
        system=self.generate('мені сьогодні важко')
        self.assertIn('Humor is optional only when it fits',system)
        self.assertIn('Familiarity must come from this chat',system)
        self.assertNotIn('a bit of humor',system)

    def test_latin_handle_keeps_established_language_with_context_rules(self):
        system=self.generate('stasikawp')
        self.assertIn('LANGUAGE OF THIS REPLY',system)
        self.assertIn('Write only in Ukrainian',system)
        self.assertIn('names, handles, URLs, code and quoted',system)
        self.assertIn('do not invent a new topic or explain the token itself',system)

    def test_explicit_language_stays_authoritative_for_each_preset(self):
        self.p.settings['reply_lang']=2
        for index in range(4):
            self.p.settings['conversation_style']=index
            system=self.generate('hi, how are you?')
            self.assertIn('Write only in Russian',system)

    def test_group_addressee_rules_do_not_replace_sender_provenance(self):
        group=self.p.chat_key(0,-100500)
        self.p._chats[group]={'type':'group','enabled':True,'account':0,'dialog_id':-100500}
        system=self.p.build_system(group,{})
        self.assertIn('reply_to/reply_sender to follow the addressee',system)
        self.assertIn('a question between other participants',system)
        self.assertIn('Names may coincide',system)
        self.assertIn('Keep forum topics separate',system)
        self.assertNotIn('reply_to/reply_sender to follow the addressee',self.p.build_system(self.key(),{}))

    def test_selectors_have_four_styles_and_local_inheritance_without_side_effect_callbacks(self):
        row=next(i for i in screen(self.p,'style') if getattr(i,'key',None)=='conversation_style')
        self.assertEqual(len(row.items),4)
        self.assertFalse(hasattr(row,'on_change'))
        self.p._open_key=self.key()
        items=[];self.p._settings_chats(items)
        local=next(i for i in items if getattr(i,'key',None)=='conversation_style_'+self.p._sk(self.key()))
        self.assertEqual(len(local.items),5)
        for key in ('chat_style','chat_style_s','chat_style_default')+tuple('chat_style_%d'%i for i in range(4)):
            self.assertEqual(len(mod.S[key]),3)
            self.assertTrue(all(mod.S[key]))

