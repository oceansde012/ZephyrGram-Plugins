"""Ordinary confirmations must not cost a cosmetic retry or lose their first words."""
from test_ai_autoreply import Base, CLIENT, DID


class TestLegacyAcknowledgements(Base):
    def setUp(self):
        super().setUp()
        self.enable()
        self.p.settings.update(natural_chat=False,memory_auto=False,learn_style=False,short_msgs=False)

    def generate(self,answer,question='сьогодні важкий день'):
        CLIENT.ai_result=lambda messages:answer
        return self.p.generate(self.key(),0,DID,[{'role':'user','content':question}],
                               self.p._chats[self.key()],self.p._state(self.key()),split=False)

    def test_ukrainian_and_russian_empathy_keep_their_meaning_with_one_request(self):
        for answer in ('розумію, день був важкий','понимаю, день был тяжелый',
                       'звісно, можу пояснити','конечно, расскажу','це дійсно важливо'):
            with self.subTest(answer=answer):
                CLIENT.ai_calls.clear()
                parts,why=self.generate(answer)
                self.assertEqual(parts,[answer])
                self.assertEqual(why,'')
                self.assertEqual(len(CLIENT.ai_calls),1)

    def test_conversation_presets_do_not_restore_automatic_phrase_retries(self):
        for preset in range(4):
            self.p.settings['conversation_style']=preset
            self.assertEqual(self.p.reply_problems('розумію, звісно, це важливо',None,'як справи?'),[])

    def test_explicit_owner_ban_still_retries_and_replacement_is_kept(self):
        self.p.settings['banned_words']='розумію'
        replies=iter(['розумію, день був важкий','важкий день вийшов'])
        CLIENT.ai_result=lambda messages:next(replies)
        parts,why=self.p.generate(self.key(),0,DID,[{'role':'user','content':'як справи?'}],
                                 self.p._chats[self.key()],self.p._state(self.key()),split=False)
        self.assertEqual(len(CLIENT.ai_calls),2)
        self.assertEqual(parts,['важкий день вийшов'])
        self.assertIn('banned:розумію',CLIENT.ai_calls[1]['system'])

    def test_direct_truthful_identity_answer_is_kept_in_legacy_without_disclosure_prefix(self):
        self.p.settings['disclosure']=False
        answer='так, це автоматичний AI-помічник'
        parts,why=self.generate(answer,'це бот відповідає?')
        self.assertEqual(parts,[answer])
        self.assertEqual(len(CLIENT.ai_calls),1)

    def test_wrong_language_and_explicit_bans_are_still_reported(self):
        self.assertIn('wrong-lang',self.p.reply_problems('你好世界',None,'як справи?'))
        self.assertEqual(self.p.reply_problems('розумію',None,extra=['розумію']),['banned:розумію'])
