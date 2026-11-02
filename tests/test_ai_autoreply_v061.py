"""Natural mode: ordinary conversation, optional label, honest answers about identity."""
from test_ai_autoreply import Base, CLIENT, DID, mod, screen


class TestNaturalIdentity(Base):
    def setUp(self):
        super().setUp()
        self.enable()
        self.p.settings.update(natural_chat=True, memory_auto=False, typing_delay=False)

    def deliver(self, text):
        st = self.p._state(self.key())
        return self.p.deliver(self.key(), self.p._chats[self.key()], st, DID, [text], [], True)

    def test_old_forced_disclosure_does_not_prefix_natural_first_reply(self):
        self.p.settings.update(disclosure=True, disclosure_text='Я нейросеть: ')
        self.deliver('та нормально, а ти як?')
        self.assertEqual(CLIENT.sent[0][1], 'та нормально, а ти як?')

    def test_natural_label_remains_explicitly_available(self):
        self.p.settings.update(natural_disclosure=True, disclosure_text='Автоответ: ')
        self.deliver('сейчас занят')
        self.assertEqual(CLIENT.sent[0][1], 'Автоответ: сейчас занят')

    def test_natural_activation_does_not_override_either_label_choice(self):
        for value in (True, False):
            self.p.settings.update(disclosure=value, natural_disclosure=value)
            self.p._natural_profile_changed(True)
            self.assertEqual(self.p.settings['disclosure'], value)
            self.assertEqual(self.p.settings['natural_disclosure'], value)

    def test_legacy_mode_retains_existing_first_reply_prefix(self):
        self.p.settings.update(natural_chat=False, disclosure=True, disclosure_text='Автоответ: ')
        self.deliver('сейчас занят')
        self.assertEqual(CLIENT.sent[0][1], 'Автоответ: сейчас занят')

    def test_new_label_preference_is_off_by_default_and_visible_in_natural_mode(self):
        row = next(i for i in screen(self.p, 'prompts') if getattr(i, 'key', None) == 'natural_disclosure')
        self.assertFalse(row.default)
        self.assertFalse(self.p._first_reply_disclosure())

    def test_prompt_prevents_unsolicited_introduction_but_requires_truth_if_asked(self):
        prompt = self.p.build_system(self.key(), {})
        self.assertIn('Do not volunteer comments about being an AI', prompt)
        self.assertIn('Do not introduce yourself as an AI', prompt)
        self.assertIn('briefly and honestly say this is an automatic AI assistant', prompt)
        self.assertIn('never claim to be a human or the account owner and never deny automation', prompt)
        self.assertNotIn('deflect briefly', prompt)

    def test_ordinary_reply_needs_one_request_and_is_not_postprocessed_into_a_disclaimer(self):
        CLIENT.ai_result = lambda messages: 'та нормально, день спокійний'
        parts, why = self.p.generate(self.key(), 0, DID, [{'role': 'user', 'content': 'як день?'}],
                                     self.p._chats[self.key()], self.p._state(self.key()))
        self.assertEqual(parts, ['та нормально, день спокійний'])
        self.assertEqual(why, '')
        self.assertEqual(len(CLIENT.ai_calls), 1)

    def test_honest_direct_answer_is_not_removed_or_rewritten(self):
        CLIENT.ai_result = lambda messages: 'так, це автоматичний помічник'
        parts, why = self.p.generate(self.key(), 0, DID, [{'role': 'user', 'content': 'це бот відповідає?'}],
                                     self.p._chats[self.key()], self.p._state(self.key()))
        self.assertEqual(parts, ['так, це автоматичний помічник'])
        self.assertEqual(why, '')
        self.assertEqual(len(CLIENT.ai_calls), 1)

