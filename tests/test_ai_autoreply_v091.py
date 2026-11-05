"""0.9.1: short human-like replies. Fake Zephyr, no network, no real AI calls.

1. a reply mirrors the length of the incoming message: about 2x its text (at least MIRROR_MIN), PART_CAP per part;
2. a too long answer gets one rewrite request with the total limit, then it is cut at a sentence end;
3. Live / natural chat send at most 2 parts;
4. no dashes and no quotation marks in human replies;
5. annoyance or "stop" in the last message: the prompt says to acknowledge and drop the topic, the reply is tiny;
6. Detailed answers are not mirrored.
7. (#47) quote the message answered when several are new; otherwise quote_pct;
8. (#46) a sticker gets words most of the time, a sticker back only STICKER_BACK_PCT;
9. (#44) typing is shown at least TYPING_SHOWN_MIN and refreshed every few seconds;
10. (#18) after a pause the reply reads what was written meanwhile and does not answer what the owner answered.
"""
import unittest
from unittest.mock import patch

from test_ai_autoreply import Base, CLIENT, DID, mod

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

    def test_short_msgs_off_sends_at_most_two_parts(self):
        self.p.settings.update(human_timing=False, natural_chat=False, short_msgs=False, max_parts="4")
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
        for t in (u"хватит уже", u"хватит, надоело", u"досить", u"досить про це", u"отстань", u"набридло", u"стоп",
                  u"Stop it", u"достали уже", u"годі!"):
            self.assertTrue(mod.ANNOYED_RE.search(t), t)
        for t in (u"як справи?", u"остановка автобуса", u"достатньо часу", u"стопудово приду", u"стопка книг",
                  u"мне досталось", u"хватит ли денег", u"яка відстань до міста", u"it stopped raining",
                  u"досить добре"):
            self.assertFalse(mod.ANNOYED_RE.search(t), t)

    def test_rule_and_tiny_reply(self):
        sent = self.answer(LONG, text=u"хватит, надоело про это")
        self.assertIn(mod.ANNOYED_RULE, self.calls[0]["system"])
        self.assertLessEqual(len(" ".join(sent)), mod.MIRROR_MIN + 5)

    def test_annoyed_long_message_caps_at_its_length(self):
        text = u"хватит уже, я тебе сто раз говорил что мне это не интересно и не надо больше об этом писать мне"
        sent = self.answer(LONG, text=text)
        self.assertLessEqual(len(" ".join(sent)), len(text) + 5)
        self.assertGreater(len(text), mod.MIRROR_MIN)

    def test_no_rule_for_a_normal_message(self):
        self.answer(u"ок", text=u"як справи?")
        self.assertNotIn(mod.ANNOYED_RULE, self.calls[0]["system"])



class TestQuote(Chat):
    def replies_to(self):
        return [s[2] for s in CLIENT.sent]

    def test_answer_to_the_last_message_follows_the_chance(self):
        self.p.settings["quote_pct"] = "0"
        CLIENT.ai_result = lambda m, **kw: u"норм"
        self.incoming(text=u"привіт", mid=511)
        self.incoming(text=u"як справи?", mid=512)
        self.fire_timers()
        self.assertEqual(self.replies_to(), [None])

    def test_group_quotes_the_last_message(self):
        self.assertEqual(self.p._quote_target({"type": "group"}, [(1, 7, u"коли?"), (2, 7, u"ок")]), 2)

    def test_several_new_messages_quote_the_question(self):
        self.p.settings["quote_pct"] = "0"
        CLIENT.ai_result = lambda m, **kw: u"о сьомій"
        self.incoming(text=u"привіт", mid=501)
        self.incoming(text=u"коли приїдеш?", mid=502)
        self.incoming(text=u"я вдома", mid=503)
        self.fire_timers()
        self.assertEqual(self.replies_to()[:1], [502])

    def test_single_message_follows_the_chance(self):
        self.p.settings["quote_pct"] = "0"
        self.answer(u"ок")
        self.assertEqual(self.replies_to(), [None])
        CLIENT.sent[:] = []
        self.p.settings["quote_pct"] = "100"
        self.answer(u"ок")
        self.assertIsNotNone(self.replies_to()[0])

    def test_only_the_first_part_quotes(self):
        self.p.settings.update(quote_pct="100", max_parts="3", short_msgs=True)
        self.answer(u"перше\nдруге")
        self.assertEqual(len(CLIENT.sent), 2)
        self.assertIsNone(CLIENT.sent[1][2])

    def test_setting_on_the_page(self):
        self.assertIn("quote_pct", mod.Plugin.PAGES["style_adv"].split())
        self.assertIn("quote_pct", self.p._rows())


class Sticker:
    id = 1777


class TestStickerGetsWords(Chat):
    def setUp(self):
        super().setUp()
        self.native = []
        self.p._is_sticker_document = lambda doc: isinstance(doc, Sticker)
        self.p._memory_owner_id = lambda account: 123
        self.p._cached_sticker_document = lambda *a: None
        self.p._queue_sticker_document = lambda *a, **kw: self.native.append(a) or True

    def sticker(self):
        m = self.msg(text="", mid=601)
        m.update(has_media=True, is_sticker=True, _sticker_document=Sticker())
        CLIENT.ai_result = lambda m, **kw: u"ахах, точно"
        self.p._handle_dict(0, DID, m)
        self.fire_timers()

    def test_words_when_the_dice_say_so(self):
        with patch.object(mod, "STICKER_BACK_PCT", 0):
            self.sticker()
        self.assertEqual(self.native, [])
        self.assertEqual([s[1] for s in CLIENT.sent], [u"ахах, точно"])
        self.assertIn(mod.STICKER_TEXT_RULE, CLIENT.ai_calls[0]["system"])

    def test_sticker_back_sometimes(self):
        with patch.object(mod, "STICKER_BACK_PCT", 100):
            self.sticker()
        self.assertEqual(len(self.native), 1)
        self.assertEqual(CLIENT.sent, [])

    def test_mostly_words_by_default(self):
        self.assertLessEqual(mod.STICKER_BACK_PCT, 40)


class TestTypingVisible(Chat):
    def setUp(self):
        super().setUp()
        self.sleeps, self.typing = [], []
        orig = mod.time.sleep
        mod.time.sleep = lambda s: self.sleeps.append(s)
        self.addCleanup(setattr, mod.time, "sleep", orig)
        self.p._send_typing = lambda did, account, cancel=False: self.typing.append(cancel) or True

    def test_short_reply_types_long_enough_to_be_seen(self):
        self.p.settings.update(human_timing=False, typing_delay=True)
        self.answer(u"ок")
        self.assertIn(False, self.typing)
        self.assertGreaterEqual(sum(self.sleeps), 1.9)   # at least ~2 s of visible typing

    def test_live_typing_is_visible_and_refreshed(self):
        self.p.settings.update(human_timing=True, type_ms="40")
        self.p._live_wait(self.key(), self.p._chats[self.key()], self.p._state(self.key()), DID, 0,
                          {"wait": 0.5, "type": 0.3, "arr": self.clock[0]})
        self.assertGreaterEqual(sum(self.sleeps), 1.9)   # at least ~2 s of visible typing
        self.assertIn(False, self.typing)
        self.assertLessEqual(mod.TYPING_REFRESH_SEC, 5.0)

    def test_long_text_types_longer(self):
        self.p.settings.update(human_timing=False, typing_delay=True, answer_detail="2")
        self.answer(u"ок")
        short = sum(self.sleeps)
        self.sleeps[:] = []
        self.answer(u"а " * 120)
        self.assertGreater(sum(self.sleeps), short)


class TestAfterPause(Chat):
    def test_resumed_chat_reads_what_was_written_meanwhile(self):
        self.p.chat_off(self.key(), remove=False)
        CLIENT.history[:] = [
            {"id": 701, "from_id": 7, "out": False, "date": int(self.clock[0]) - 600, "text": u"я переїхав у Львів"},
            {"id": 702, "from_id": 1, "out": True, "date": int(self.clock[0]) - 500, "text": u"о, круто"},
        ]
        self.enable()
        self.answer(u"ок", text=u"як тобі там?")
        contents = " ".join(str(m.get("content")) for m in self.calls[0]["messages"])
        self.assertIn(u"Львів", contents)
        self.assertIn(u"круто", contents)

    def test_scan_skips_what_the_owner_already_answered(self):
        self.p.chat_off(self.key(), remove=False)
        now = int(self.clock[0])
        CLIENT.history[:] = [
            {"id": 711, "from_id": 7, "out": False, "date": now - 300, "text": u"ти де?"},
            {"id": 712, "from_id": 1, "out": True, "date": now - 200, "text": u"вдома"},
        ]
        self.enable()
        self.assertEqual(self.p._scan_all(), 0)
        self.assertEqual(CLIENT.ai_calls, [])


if __name__ == "__main__":
    unittest.main()
