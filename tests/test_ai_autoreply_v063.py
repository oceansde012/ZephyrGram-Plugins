"""Group burst regression cases: fake timers and no paid provider calls."""
from unittest.mock import patch
from test_ai_autoreply import Base, CLIENT, mod

GROUP = -100700


class TestGroupBurst(Base):
    def setUp(self):
        super().setUp()
        CLIENT.info = {'id': GROUP, 'title': 'Group', 'type': 'group', 'is_bot': False}
        self.enable(did=GROUP)
        self.k = self.p.chat_key(0, GROUP)
        self.p.settings.update(debounce='0', cooldown='0', owner_active='0',
                               group_need_question=False, skip_ack=False,
                               humanize=False, typing_delay=False, disclosure=False)

    def receive(self, mid, text, topic=None):
        row = self.msg(mid=mid, text=text, did=GROUP)
        if topic is not None:
            row['topic_id'] = topic
        self.p._handle_dict(0, GROUP, row)

    def test_unknown_topic_burst_replies_only_to_newest_without_combining_topics(self):
        for mid in range(1, 7):
            self.receive(mid, 'fragment %s?' % mid)
        CLIENT.ai_result = lambda messages: 'one response'
        self.fire_timers()
        self.assertEqual(len(CLIENT.ai_calls), 1)
        self.assertEqual([s[2] for s in CLIENT.sent], [6])
        self.assertIn('fragment 6?', str(CLIENT.ai_calls[0]['messages']))
        self.assertNotIn('fragment 1?', str(CLIENT.ai_calls[0]['messages']))
        self.assertTrue(set(range(1, 7)).issubset(self.p._state(self.k).answered))

    def test_known_topics_wait_between_sends_even_when_cooldown_is_zero(self):
        times = []
        original_send = self.p.send
        def send(*args, **kwargs):
            times.append(self.clock[0])
            return original_send(*args, **kwargs)
        self.receive(1, 'first topic?', 11)
        self.receive(2, 'second topic?', 22)
        CLIENT.ai_result = lambda messages: 'a response'
        with patch.object(self.p, 'send', send):
            self.fire_timers()
        self.assertEqual([s[2] for s in CLIENT.sent], [1, 2])
        self.assertGreaterEqual(times[1] - times[0], 20)
        self.assertNotIn('second topic?', str(CLIENT.ai_calls[0]['messages']))
        self.assertNotIn('first topic?', str(CLIENT.ai_calls[1]['messages']))

    def test_new_group_message_after_reply_cannot_bypass_pause(self):
        CLIENT.ai_result = lambda messages: 'a response'
        self.receive(1, 'first?', 11)
        self.fire_timers()
        sent_at = self.clock[0]
        self.receive(2, 'second?', 11)
        self.fire_once()
        self.assertEqual(len(CLIENT.sent), 1)
        self.fire_timers()
        self.assertEqual(len(CLIENT.sent), 2)
        self.assertGreaterEqual(self.clock[0] - sent_at, 20)

    def test_group_parts_are_delivered_as_one_message(self):
        st = self.p._state(self.k)
        self.p.deliver(self.k, self.p._chats[self.k], st, GROUP,
                       ['first', 'second', 'third'], [(1, 7, 'question?')], False)
        self.assertEqual(CLIENT.sent, [(GROUP, 'first\nsecond\nthird', 1)])

    def test_private_parts_are_still_separate(self):
        CLIENT.info = {'id': 42, 'title': 'Alice', 'type': 'user', 'is_bot': False}
        self.enable(did=42)
        k = self.p.chat_key(0, 42)
        self.p.deliver(k, self.p._chats[k], self.p._state(k), 42,
                       ['first', 'second'], [(1, 7, 'question?')], False)
        self.assertEqual([s[1] for s in CLIENT.sent], ['first', 'second'])

    def test_optional_after_text_sticker_cannot_add_another_group_post(self):
        with patch.object(self.p, '_send_sticker') as send_sticker:
            self.p.deliver(self.k, self.p._chats[self.k], self.p._state(self.k), GROUP,
                           ['answer'], [(1, 7, 'question?')], False,
                           sticker={'id': 123, 'set': 'example'})
        send_sticker.assert_not_called()
        self.assertEqual(len(CLIENT.sent), 1)
