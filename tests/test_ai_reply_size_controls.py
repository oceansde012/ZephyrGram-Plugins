"""Split controls must affect real delivery in every profile; no AI/network calls."""
import random
from unittest.mock import patch
from test_ai_autoreply import Base, CLIENT, mod, all_settings


class TestReplySizeAndControls(Base):
    TEXT = 'Сьогодні залишаюся вдома, спокійно дороблю свої справи. Завтра вже зможу приїхати і все показати на місці. Тоді й домовимося про зручний час зустрічі.'

    def prepare(self, **settings):
        self.enable()
        self.p.settings.update(disclosure=False, owner_active='0', human_timing=True,
                               split2_pct='100', natural_split=True, **settings)
        CLIENT.ai_result = lambda messages, **kwargs: self.TEXT

    def send_reply(self):
        self.incoming(text='Які плани на завтра?')
        self.fire_timers()
        return [row[1] for row in CLIENT.sent]

    def test_one_message_limit_survives_short_mode_disabled(self):
        self.prepare(short_msgs=False, max_parts='1')
        self.assertEqual(len(self.send_reply()), 1)

    def test_one_message_limit_survives_natural_profile(self):
        self.prepare(natural_chat=True, short_msgs=False, max_parts='1')
        self.assertEqual(len(self.send_reply()), 1)

    def test_disabled_split_switch_prevents_both_split_stages(self):
        self.prepare(split_msgs=False, max_parts='6')
        self.assertEqual(len(self.send_reply()), 1)

    def test_disabled_variation_switch_prevents_random_second_split(self):
        self.prepare(short_msgs=False)
        self.p.settings['natural_split'] = False
        CLIENT.ai_result = lambda messages, **kwargs: 'Сьогодні залишаюся вдома. Завтра зможу приїхати.'
        self.assertEqual(len(self.send_reply()), 1)

    def test_enabled_variation_switch_can_split_under_global_maximum(self):
        self.prepare(short_msgs=False, max_parts='2')
        CLIENT.ai_result = lambda messages, **kwargs: 'Сьогодні залишаюся вдома. Завтра зможу приїхати.'
        self.assertEqual(len(self.send_reply()), 2)

    def test_default_sends_at_most_two_messages_without_dropping_lines(self):
        self.prepare()
        self.p.settings['natural_split'] = False
        CLIENT.ai_result = lambda messages, **kwargs: 'Сьогодні залишаюся вдома\nЗавтра приїду\nТоді все покажу'
        parts = self.send_reply()
        self.assertEqual(len(parts), 2)
        for fragment in ['Сьогодні залишаюся вдома', 'Завтра приїду', 'Тоді все покажу']:
            self.assertIn(fragment, '\n'.join(parts))

    def test_shorter_detail_budgets_keep_explicit_owner_limit(self):
        for detail, expected in [(0,240), (1,600), (2,1600)]:
            self.p.settings['answer_detail'] = detail
            self.assertEqual(self.p._reply_limit(), expected)
        self.p.settings['max_reply'] = '950'
        self.assertEqual(self.p._reply_limit(),950)
        self.p.settings['max_reply'] = 'invalid'
        self.assertEqual(self.p._reply_limit(),1600)

    def test_settings_expose_actual_split_keys_and_current_budget(self):
        rows = all_settings(self.p)
        for key in ['split_msgs','short_msgs','natural_split','max_parts','max_reply','answer_detail']:
            self.assertEqual(sum(getattr(row,'key',None)==key for row in rows),1,key)
        by_key = {getattr(row,'key',None):row for row in rows}
        self.assertEqual(by_key['max_parts'].default,'2')
        self.assertIn('600',by_key['max_reply'].subtext)

    def test_generation_time_is_subtracted_from_total_latency(self):
        self.enable()
        key = self.key();arrival = self.clock[0]-8
        with patch.object(mod,'latency_seconds',return_value=(10,4)):
            timing = self.p._make_timing(key,self.p._state(key),'warm',arrival,[(1,7,'привіт')],['відповідь'],0)
            self.assertEqual(timing['wait'],2)
            self.assertEqual(timing['type'],2)
            self.clock[0] += 5
            self.assertEqual(self.p._make_timing(key,self.p._state(key),'warm',arrival,[],['відповідь'],0)['wait'],0)

    def test_default_cold_timing_has_no_random_minute_long_silence(self):
        rng=random.Random(51)
        for _ in range(500):
            total, typing = mod.latency_seconds(rng,'cold',50,240,mod.PRESET_BASE)
            self.assertLess(total,40)
            self.assertLessEqual(typing,total)
        # Deliberate custom long-wait settings remain available.
        params=dict(mod.PRESET_BASE,lat_long_pct=100,lat_long_min=60,lat_long_max=60)
        self.assertGreaterEqual(mod.latency_seconds(rng,'cold',0,0,params)[0],60)
