"""0.4.6: forms of address follow the other person's gender; pauses between parts follow their length."""
from test_ai_autoreply import Base, CLIENT, DID, chats_screen, mod


class TestDetectGender(Base):
    def test_feminine_masculine_and_unsure(self):
        self.assertEqual(mod.detect_gender([u"я була вдома", u"я зробила уроки"]), "f")
        self.assertEqual(mod.detect_gender([u"я сделал это", u"я пошёл домой"]), "m")
        self.assertIsNone(mod.detect_gender([u"я була вдома"]))                       # one word is not enough
        self.assertIsNone(mod.detect_gender([u"я була вдома", u"я був там"]))        # mixed
        self.assertIsNone(mod.detect_gender([u"привіт", u"я тут", u"я в школі"]))

    def test_name_is_only_a_weak_hint(self):
        self.assertEqual(mod.name_gender_hint(u"Надя ❤"), "f")
        self.assertEqual(mod.name_gender_hint(u"Анна Петрівна"), "f")
        for name in (u"Микита", u"cherish", u"Андрій", u"Саша", u"Данила"):
            self.assertIsNone(mod.name_gender_hint(name), name)


class TestGenderInPrompt(Base):
    def setUp(self):
        super().setUp()
        self.enable()
        self.p.settings["owner_active"] = "0"
        self.sk = self.p._sk(self.key())

    def system(self, text="привіт, як ти"):
        self.incoming(text=text)
        self.fire_timers()
        return CLIENT.ai_calls[-1]["system"]

    def test_her_own_words_switch_to_feminine_forms(self):
        CLIENT.history[:] = [
            {"id": 1, "out": False, "date": int(self.clock[0]) - 90, "text": u"я була на парах", "dialog_id": DID, "from_id": 7},
            {"id": 2, "out": True, "date": int(self.clock[0]) - 80, "text": u"і як там", "dialog_id": DID},
            {"id": 3, "out": False, "date": int(self.clock[0]) - 70, "text": u"я втомилась, я зробила все", "dialog_id": DID, "from_id": 7},
        ]
        system = self.system(u"а ти що робив")
        self.assertIn("The other person is a woman", system)

    def test_without_evidence_the_bot_is_told_not_to_assume_a_man(self):
        system = self.system()
        self.assertIn("NOT known", system)
        self.assertNotIn("The other person is a woman", system)
        self.assertNotIn("The other person is a man", system)

    def test_name_alone_gives_only_a_hedged_hint(self):
        self.p._commit(self.key(), set={"title": u"Надя"})
        system = self.system()
        self.assertIn("name suggests", system)
        self.assertNotIn("The other person is a woman", system)

    def test_manual_choice_wins(self):
        self.p.settings["gender_" + self.sk] = 2
        self.assertIn("The other person is a woman", self.system())
        self.p.settings["gender_" + self.sk] = 1
        self.assertIn("The other person is a man", self.system(u"ще раз привіт"))

    def test_owner_gender_setting(self):
        self.p.settings["owner_gender"] = 1
        self.assertIn("The owner is a man", self.system())

    def test_gender_applies_to_commands_too(self):
        self.p.settings["gender_" + self.sk] = 2
        CLIENT.ai_result = lambda m, **kw: "привіт, як ти"
        self.p._run_command(0, DID, self.key(), False, "")
        self.assertIn("The other person is a woman", CLIENT.ai_calls[-1]["system"])

    def test_chat_options_have_the_selector(self):
        self.p._open_key = self.key()
        keys = [getattr(i, "key", None) for i in chats_screen(self.p)]
        self.assertIn("gender_" + self.sk, keys)


class TestPauseFollowsLength(Base):
    def setUp(self):
        super().setUp()
        self.enable()
        self.sleeps = []
        mod.time.sleep = lambda s: self.sleeps.append(s)
        self.p.settings.update(owner_active="0", human_timing=True, split_gap_min="1", split_gap_max="1", type_ms="40")
        self.p.settings["disclosure"] = False

    def send_parts(self, *parts):
        CLIENT.ai_result = lambda m, **kw: "\n".join(parts)
        self.incoming(text="розкажи щось")
        self.fire_timers()

    def waits_between_sends(self):
        marks = []
        original = CLIENT.send_text

        def send(did, text, reply_to=None, **kw):
            marks.append(sum(self.sleeps))
            return original(did, text, reply_to)
        CLIENT.send_text = send
        return marks, original

    def test_a_long_part_waits_longer_than_a_short_one(self):
        marks, original = self.waits_between_sends()
        try:
            self.send_parts("перше", "ок", ("а " * 100).strip())       # 3 parts, the last one ~200 chars (~8 s at 40 ms)
        finally:
            CLIENT.send_text = original
        self.assertEqual(len(marks), 3)
        short_wait, long_wait = marks[1] - marks[0], marks[2] - marks[1]
        self.assertLessEqual(short_wait, 3.0)
        self.assertGreaterEqual(long_wait, 6.0)

    def test_pause_is_capped(self):
        self.send_parts("перше", "б" * 3000)
        self.assertLessEqual(max(self.sleeps), mod.TYPING_REFRESH_SEC + 1e-6)   # slept in chunks, never one long block
        self.assertLessEqual(sum(x for x in self.sleeps if x <= mod.TYPING_REFRESH_SEC), 3600)

    def test_first_wait_counts_only_the_first_part(self):
        p = self.p
        batch = [(1, 7, "привіт")]
        t_one = p._make_timing(self.key(), p._state(self.key()), "warm", self.clock[0], batch, ["ок"], 0)
        t_many = p._make_timing(self.key(), p._state(self.key()), "warm", self.clock[0], batch, ["ок", "x" * 2000], 0)
        self.assertLess(abs(t_many["type"] - t_one["type"]), 6.0)
