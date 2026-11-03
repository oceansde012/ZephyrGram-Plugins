"""Latin nicknames/identifiers are not evidence of switching an ordinary chat to English."""
from test_ai_autoreply import Base, CLIENT, DID, mod


class TestLatinLanguageSignal(Base):
    def test_bare_latin_nickname_and_random_single_token_have_no_language_signal(self):
        for text in ('stasikawp', 'qwertyuiop', 'randomhandle', '@stasikawp', '#stasikawp',
                     'StasikAWP', 'stasik_awp', 'stasik123', 'ZephyrGram', 'telegram'):
            with self.subTest(text=text):
                self.assertFalse(mod.english_signal(text))
                self.assertIsNone(mod.incoming_language([text], []))
                self.assertEqual(mod.detect_lang(text),'Ukrainian')

    def test_url_or_handle_word_pieces_do_not_manufacture_an_english_sentence(self):
        for text in ('https://example.com/help/me', 'www.example.com/what-is-this',
                     't.me/hello_user', 'example.org/hello', '@hello @please',
                     'hello_world', 'can_you_help', 'hello123', 'hello.png', 'this.foo', 'my.file is.value'):
            with self.subTest(text=text):self.assertIsNone(mod.incoming_language([text],[]))

    def test_language_neutral_latin_acknowledgements_do_not_override_recent_ukrainian(self):
        for text in ('ok', 'okay', 'lol', 'gg wp', 'haha', 'hmm', 'yes', 'no'):
            with self.subTest(text=text):
                self.assertEqual(mod.incoming_language([text],['привіт, що робиш?']),'Ukrainian')

    def test_single_nickname_inherits_recent_interlocutor_language(self):
        self.assertEqual(mod.incoming_language(['stasikawp'],['мені це подобається']),'Ukrainian')
        self.assertEqual(mod.incoming_language(['stasikawp'],['мне это нравится']),'Russian')

    def test_multiple_identifier_messages_do_not_form_an_english_batch(self):
        self.assertIsNone(mod.incoming_language(['stasikawp','qwertyuiop','foobar'],[]))
        self.assertIsNone(mod.incoming_language(['stasikawp','stasikawp'],[]))

    def test_real_english_phrases_and_clear_short_english_remain_supported(self):
        for text in ('hello', 'thanks', 'sorry', 'Hello, how are you doing?',
                     'Can you help me?', "I'm working today", "What's up?", 'the plugin crashes',
                     'please reply in English', 'hello StasikAWP', 'Thanks @stasikawp'):
            with self.subTest(text=text):
                self.assertTrue(mod.english_signal(text))
                self.assertEqual(mod.incoming_language([text],['привіт, що робиш?']),'English')
                self.assertEqual(mod.detect_lang(text),'English')

    def test_cyrillic_conversation_with_a_latin_handle_retains_its_language(self):
        self.assertEqual(mod.incoming_language(['як там stasikawp?'],[]),'Ukrainian')
        self.assertEqual(mod.incoming_language(['что там stasikawp?'],[]),'Russian')

    def test_latin_nickname_respects_explicit_reply_language(self):
        self.enable()
        for mode,expected in ((1,'Ukrainian'),(2,'Russian')):
            self.p.settings['reply_lang']=mode
            self.assertEqual(self.p.pick_reply_lang(self.key(),0,DID,'stasikawp'),'Ukrainian' if mode==1 else 'Russian')
            self.assertEqual(self.p.pick_reply_lang(self.key(),0,DID,'Hello, how are you?'),expected)

    def test_nickname_inherits_owner_language_when_incoming_context_has_no_signal(self):
        self.enable();self.p.settings['reply_lang']=3
        CLIENT.history[:]=[{'id':1,'out':True,'text':'мені це дуже подобається','date':1}]
        self.assertEqual(self.p.pick_reply_lang(self.key(),0,DID,'stasikawp'),'Ukrainian')
        CLIENT.history[:]=[{'id':1,'out':True,'text':'мне это очень нравится','date':1}]
        self.assertEqual(self.p.pick_reply_lang(self.key(),0,DID,'stasikawp'),'Russian')

    def test_unknown_group_topic_does_not_switch_to_english_for_nickname(self):
        group=-100500;key=self.p.chat_key(0,group)
        self.p._chats[key]={'enabled':True,'type':'group','account':0,'dialog_id':group}
        self.p.settings['reply_lang']=3
        self.p._work_context.group_scope=(key,None)
        self.assertEqual(self.p.pick_reply_lang(key,0,group,'stasikawp',batch=['stasikawp'],recent=['stasikawp']),'Ukrainian')

