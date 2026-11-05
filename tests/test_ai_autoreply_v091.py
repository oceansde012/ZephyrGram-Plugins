"""0.9.1: short human-like replies. Fake Zephyr, no network, no real AI calls.

1. a reply mirrors the length of the incoming message: about 2x its text (at least MIRROR_MIN), PART_CAP per part;
2. a too long answer gets one rewrite request with the total limit, then it is cut at a sentence end;
3. Live / natural chat send at most 2 parts;
4. no dashes and no quotation marks in human replies;
5. annoyance or "stop" in the last message: the prompt says to acknowledge and drop the topic, the reply is tiny;
6. Detailed answers are not mirrored.
"""
import unittest

from test_ai_autoreply import Base, CLIENT, mod

LONG = (u"Слухай, тут така історія вийшла. Я вчора довго думав про це все і зрозумів кілька речей. "
        u"По-перше, треба менше працювати вечорами. По-друге, варто частіше гуляти. "
        u"І ще одне: ми давно не бачились, тож треба це виправити найближчим часом. "
        u"Загалом, у мене все добре, просто багато думок назбиралось за тиждень.")


class Chat(Base):
    def setUp(self):
        super().setUp()
        self.enable()
        self.p.settings.update(disclosure=False, owner_active="0")

    def answer(self, reply, text=u"як ти?"):
        CLIENT.ai_result = (lambda m, **kw: reply) if isinstance(reply, str) else reply
        before, calls = len(CLIENT.sent), len(CLIENT.ai_calls)
        self.clock[0] += 3600
        self.incoming(text=text)
        self.fire_timers()
        self.calls = CLIENT.ai_calls[calls:]
        return [s[1] for s in CLIENT.sent[before:]]


class TestMirrorTrim(unittest.TestCase):
    def test_parts_stop_at_the_total(self):
        self.assertEqual(mod.mirror_trim([u"ок", u"давай завтра"], 60), [u"ок", u"давай завтра"])
        out = mod.mirror_trim([u"Перше речення тут. Друге речення теж є. Третє.", u"ще одна частина"], 30)
        self.assertEqual(out, [u"Перше речення тут."])

    def test_never_empty(self):
        self.assertEqual(mod.mirror_trim([u"a", u"b"], 0), [u"a"])


class TestMirrorLength(Chat):
    def test_short_message_gets_a_short_reply(self):
        sent = self.answer(LONG, text=u"як ти?")
        self.assertLessEqual(len(" ".join(sent)), mod.MIRROR_MIN + 5)
        self.assertTrue(sent)
        self.assertTrue(sent[-1].rstrip()[-1:] in u".!?)" or len(sent[-1]) < 20, sent)

    def test_long_reply_is_asked_to_be_shorter_once(self):
        self.answer(LONG, text=u"як ти?")
        self.assertGreaterEqual(len(self.calls), 2)
        self.assertIn(u"whole reply under %d characters" % mod.MIRROR_MIN, self.calls[1]["system"])

    def test_a_short_answer_needs_no_rewrite(self):
        sent = self.answer(u"нормально, а ти?", text=u"як ти?")
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(sent, [u"нормально, а ти?"])

    def test_longer_message_allows_longer_reply(self):
        text = u"Розкажи, як пройшла поїздка, що бачили, де жили і чи сподобалось місто взагалі?"
        sent = self.answer(LONG, text=text)
        total = len(" ".join(sent))
        self.assertGreater(total, mod.MIRROR_MIN)
        self.assertLessEqual(total, 2 * len(text) + 5)

    def test_part_cap(self):
        text = u"а " * 200
        sent = self.answer(LONG + u" " + LONG, text=text.strip())
        for s in sent:
            self.assertLessEqual(len(s), mod.PART_CAP)

    def test_rule_in_system_prompt(self):
        self.answer(u"ок")
        self.assertIn(mod.MIRROR_RULE, self.calls[0]["system"])

    def test_detailed_answers_are_not_mirrored(self):
        self.p.settings["answer_detail"] = "2"
        sent = self.answer(LONG, text=u"як ти?")
        self.assertNotIn(mod.MIRROR_RULE, self.calls[0]["system"])
        self.assertGreater(len(" ".join(sent)), 2 * mod.MIRROR_MIN)


class TestPartsCap(Chat):
    def three(self):
        return u"\n".join([u"перше", u"друге", u"третє"])

    def test_live_sends_at_most_two_parts(self):
        self.p.settings.update(human_timing=True, max_parts="4")
        self.assertLessEqual(len(self.answer(self.three())), 2)

    def test_natural_sends_at_most_two_parts(self):
        self.p.settings.update(natural_chat=True, max_parts="4")
        self.assertLessEqual(len(self.answer(self.three())), 2)

    def test_short_mode_keeps_its_parts(self):
        self.p.settings.update(human_timing=False, natural_chat=False, short_msgs=True, max_parts="4")
        self.assertEqual(len(self.answer(self.three())), 3)


class TestPunctuation(unittest.TestCase):
    def test_dashes_become_commas(self):
        self.assertEqual(mod.clean_humanized(u"ну так — нормально"), u"ну так, нормально")
        self.assertEqual(mod.clean_humanized(u"ну так, – нормально"), u"ну так, нормально")
        self.assertEqual(mod.clean_humanized(u"— привіт"), u"привіт")

    def test_quotes_removed(self):
        self.assertEqual(mod.clean_humanized(u"дивився «Дюну» вчора"), u"дивився Дюну вчора")
        self.assertEqual(mod.clean_humanized(u"він сказав „ок“ і пішов"), u"він сказав ок і пішов")

    def test_hyphen_in_words_is_kept(self):
        self.assertEqual(mod.clean_humanized(u"будь-ласка, де-небудь"), u"будь-ласка, де-небудь")



class TestSentPunctuation(Chat):
    def test_sent_reply_has_no_dash_or_quotes(self):
        sent = " ".join(self.answer(u"та нормально — дивлюсь «Дюну»", text=u"що робиш?"))
        self.assertNotIn(u"—", sent)
        self.assertNotIn(u"«", sent)


class TestAnnoyed(Chat):
    def test_detection(self):
        for t in (u"хватит уже", u"досить про це", u"отстань", u"набридло", u"стоп", u"Stop it"):
            self.assertTrue(mod.ANNOYED_RE.search(t), t)
        for t in (u"як справи?", u"остановка автобуса", u"достатньо часу"):
            self.assertFalse(mod.ANNOYED_RE.search(t), t)

    def test_rule_and_tiny_reply(self):
        sent = self.answer(LONG, text=u"хватит, надоело про это")
        self.assertIn(mod.ANNOYED_RULE, self.calls[0]["system"])
        self.assertLessEqual(len(" ".join(sent)), mod.MIRROR_MIN + 5)

    def test_no_rule_for_a_normal_message(self):
        self.answer(u"ок", text=u"як справи?")
        self.assertNotIn(mod.ANNOYED_RULE, self.calls[0]["system"])


if __name__ == "__main__":
    unittest.main()
