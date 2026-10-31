"""0.4.8: gender from the owner's own forms of address, '.ai gender', neutral default, varied message count."""
import random

from test_ai_autoreply import Base, CLIENT, DID, mod


class TestEvidence(Base):
    def test_owner_addressing_counts(self):
        owner = [u"ти де була вчора", u"а ти що зробила з цим"]
        self.assertEqual(mod.gender_level([], owner), ("f", True))
        self.assertEqual(mod.gender_level([], [u"ти де був вчора", u"а ти що зробив"]), ("m", True))

    def test_one_hit_is_hedged_two_are_firm(self):
        self.assertEqual(mod.gender_level([u"я була вдома"], []), ("f", False))
        self.assertEqual(mod.gender_level([u"я була вдома", u"я зробила все"], []), ("f", True))
        self.assertEqual(mod.gender_level([u"я була вдома", u"я був вдома"], []), (None, False))

    def test_nothing_known(self):
        self.assertEqual(mod.gender_level([u"привіт", u"як справи"], [u"йо", u"що там"]), (None, False))


class TestPromptLevels(Base):
    def setUp(self):
        super().setUp()
        self.enable()
        self.p.settings["owner_active"] = "0"
        self.sk = self.p._sk(self.key())

    def system(self, history, text=u"ну що там у тебе"):
        now = int(self.clock[0])
        CLIENT.history[:] = [dict(id=i + 1, date=now - 200 + i, dialog_id=DID, from_id=7, **h) for i, h in enumerate(history)]
        self.incoming(text=text, mid=900)
        self.fire_timers()
        return CLIENT.ai_calls[-1]["system"]

    def test_owner_wrote_feminine_forms_to_her(self):
        system = self.system([{"out": True, "text": u"ти де була вчора"}, {"out": False, "text": u"в університеті"},
                              {"out": True, "text": u"а ти що зробила з цим"}])
        self.assertIn("The other person is a woman", system)
        self.assertIn("those were wrong", system)

    def test_single_hit_gives_a_hedged_line(self):
        system = self.system([{"out": False, "text": u"я була вдома"}])
        self.assertIn("suggest the other person is a woman", system)

    def test_bots_own_wrong_forms_are_not_evidence(self):
        self.p._remember_bot_text(u"ти де був вчора")
        self.p._remember_bot_text(u"ти що зробив")
        system = self.system([{"out": True, "text": u"ти де був вчора"}, {"out": True, "text": u"ти що зробив"}])
        self.assertNotIn("The other person is a man", system)
        self.assertIn("NOT known", system)

    def test_groups_get_no_gender_line(self):
        self.p._commit(self.key(), set={"type": "group"})
        self.assertNotIn("GENDER", self.system([]))


class TestGenderCommand(Base):
    def run_cmd(self, text):
        return self.p.on_send_message_hook(0, type("P", (), {"message": text, "peer": DID})())

    def test_parse(self):
        for word, want in (("woman", "woman"), ("жінка", None), ("auto", "auto")):
            adm = self.p.parse_admin(".ai gender " + word)
            self.assertEqual(adm[0], "gender")
        self.assertEqual(self.p.parse_admin(".ai пол женщина")[0], "gender")
        self.assertIsNone(self.p.parse_admin(".ai gender a b"))

    def test_sets_the_chat_gender_and_is_not_sent(self):
        self.enable()
        sk = self.p._sk(self.key())
        res = self.run_cmd(".ai gender woman")
        self.assertEqual(res.strategy, 1)
        self.assertEqual(self.p.settings["gender_" + sk], 2)
        self.run_cmd(".ai gender man")
        self.assertEqual(self.p.settings["gender_" + sk], 1)
        self.run_cmd(".ai gender auto")
        self.assertEqual(self.p.settings["gender_" + sk], 0)
        self.assertEqual(CLIENT.sent, [])

    def test_bad_value_changes_nothing(self):
        self.enable()
        self.run_cmd(".ai gender maybe")
        self.assertNotIn("gender_" + self.p._sk(self.key()), self.p.settings)
        self.assertTrue(any("gender" in b.lower() for b in CLIENT.bulletins))

    def test_russian_and_ukrainian_words(self):
        self.enable()
        sk = self.p._sk(self.key())
        self.run_cmd(u".ai стать жінка")
        self.assertEqual(self.p.settings["gender_" + sk], 2)
        self.run_cmd(u".ai пол мужчина")
        self.assertEqual(self.p.settings["gender_" + sk], 1)


class TestVaryParts(Base):
    def test_count_varies_and_text_is_kept(self):
        parts = [u"ок", u"зараз гляну", u"там якась фігня", u"напишу пізніше"]
        counts = set()
        for seed in range(60):
            out = mod.vary_parts(list(parts), random.Random(seed))
            counts.add(len(out))
            joined = " ".join(out).replace(",", "")
            for p in parts:
                self.assertIn(p, joined)
            self.assertTrue(all(o.strip() for o in out))
        self.assertTrue({1, 2, 3} <= counts, counts)

    def test_single_part_untouched(self):
        self.assertEqual(mod.vary_parts([u"привіт"], random.Random(1)), [u"привіт"])

    def test_shortest_neighbours_merge_first(self):
        out = mod.vary_parts([u"ок", u"гаразд", u"а тепер розкажи довге речення про все на світі"], random.Random(3))
        if len(out) == 2:
            self.assertEqual(out[0], u"ок, гаразд")

    def test_setting_controls_it_in_replies(self):
        self.enable()
        self.p.settings["owner_active"] = "0"
        self.p.settings["natural_split"] = True
        seen = set()
        for i in range(30):
            CLIENT.sent[:] = []
            CLIENT.ai_result = lambda m, i=i, **kw: "ага %d\nзараз глянь %d\nпотім напишу %d\nдобре %d" % (i, i, i, i)
            self.clock[0] += 500
            self.incoming(text="питання номер %d давай" % i, mid=1000 + i)
            self.fire_timers()
            seen.add(len(CLIENT.sent))
        self.assertGreaterEqual(len(seen), 2, seen)
        self.p.settings["natural_split"] = False
        CLIENT.sent[:] = []
        CLIENT.ai_result = lambda m, **kw: "один\nдва\nтри\nчотири"
        self.clock[0] += 500
        self.incoming(text="і ще питання", mid=2000)
        self.fire_timers()
        self.assertEqual(len(CLIENT.sent), 4)
