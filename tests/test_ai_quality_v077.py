"""0.7.7: human-like text quality. Fake Zephyr, no network, no real AI calls.

1. hard length limit without '…': the rest of the text goes as the next message;
2. no line break in the middle of a sentence;
3. no relatives/illness/death that nobody mentioned, owner and other person kept apart;
4. laughter not in every message and never at sad news;
5. quiz questions get a short human answer, not a reference text.
"""
import random
import re
import unittest

from test_ai_autoreply import Base, CLIENT, DID, all_settings, mod

TEXT = (u"Сьогодні залишаюся вдома, спокійно дороблю свої справи. Завтра вже зможу приїхати і все показати "
        u"на місці. Тоді й домовимося про зручний час зустрічі.")


class Chat(Base):
    def setUp(self):
        super().setUp()
        self.enable()
        self.p.settings.update(disclosure=False, owner_active="0")

    def answer(self, reply, text=u"шо там?"):
        CLIENT.ai_result = (lambda m, **kw: reply) if isinstance(reply, str) else reply
        before = len(CLIENT.sent)
        self.clock[0] += 3600
        self.incoming(text=text)
        self.fire_timers()
        return [s[1] for s in CLIENT.sent[before:]]


# ---------------------------------------------------------------- 1. length limit
class TestChunking(unittest.TestCase):
    def check(self, chunks, limit, source):
        self.assertTrue(chunks)
        for c in chunks:
            self.assertLessEqual(len(c), limit, c)
            self.assertNotIn(u"…", c)
            self.assertFalse(c.endswith((",", "-", u"—", " ")), c)
            self.assertFalse(c.startswith((",", "-", u"—", " ")), c)
        # nothing lost and no word cut: the words come back in the same order
        self.assertEqual(re.findall(r"\w+", " ".join(chunks)), re.findall(r"\w+", source))

    def test_limits_50_80_120(self):
        for limit in (50, 80, 120):
            chunks = mod.chunk_text(TEXT, limit)
            self.check(chunks, limit, TEXT)
        self.assertEqual(mod.chunk_text(TEXT, 80)[0], u"Сьогодні залишаюся вдома, спокійно дороблю свої справи.")
        # a sentence end inside the limit wins over a comma
        self.assertTrue(mod.chunk_text(TEXT, 120)[0].endswith(u"на місці."))

    def test_text_without_punctuation(self):
        text = u"ну я короче сегодня никуда не пойду потому что устал как собака и вообще дождь " * 3
        for limit in (50, 80, 120):
            self.check(mod.chunk_text(text, limit), limit, text)

    def test_clause_before_word(self):
        text = u"я сегодня занят до вечера, но завтра точно смогу заехать и всё показать"
        self.assertEqual(mod.chunk_text(text, 50)[0], u"я сегодня занят до вечера")

    def test_one_long_word_is_never_broken(self):
        word = u"а" * 90
        self.assertEqual(mod.chunk_text(word, 50), [word])
        self.assertEqual(mod.chunk_text(word + u" ок", 50), [word, u"ок"])

    def test_decimal_point_is_not_a_boundary(self):
        chunks = mod.chunk_text(u"стоимость 3.14 тысячи и ещё всякое разное по мелочи плюс доставка", 40)
        self.assertNotEqual(chunks[0], u"стоимость 3.")

    def test_fit_parts_respects_max_messages(self):
        parts = mod.fit_parts([TEXT], 50, 2)
        self.assertEqual(len(parts), 2)
        for p in parts:
            self.assertLessEqual(len(p), 50)
            self.assertNotIn(u"…", p)
        # short neighbours are merged instead of dropped when they fit together
        self.assertEqual(mod.fit_parts([u"ок.", u"давай.", u"завтра."], 50, 2), [u"ок. давай.", u"завтра."])

    def test_one_message_mode(self):
        parts = mod.fit_parts([TEXT], 80, 1)
        self.assertEqual(parts, [u"Сьогодні залишаюся вдома, спокійно дороблю свої справи."])


class TestLimitInDelivery(Chat):
    def test_rest_goes_as_next_message_without_dots(self):
        self.p.settings.update(max_reply="80", max_parts="3", short_msgs=False)
        sent = self.answer(TEXT)
        self.assertGreaterEqual(len(sent), 2)
        for s in sent:
            self.assertLessEqual(len(s), 80)
            self.assertNotIn(u"…", s)
        self.assertIn(u"Завтра вже зможу приїхати", " ".join(sent))

    def test_one_message_mode_sends_whole_words_only(self):
        self.p.settings.update(max_reply="50", split_msgs=False)
        sent = self.answer(u"слово " * 100)
        self.assertEqual(len(sent), 1)
        self.assertLessEqual(len(sent[0]), 50)
        self.assertNotIn(u"…", sent[0])
        self.assertTrue(all(w == u"слово" for w in sent[0].split()))

    def test_max_parts_one_is_a_hard_limit(self):
        self.p.settings.update(max_reply="60", max_parts="1", short_msgs=False)
        sent = self.answer(TEXT)
        self.assertEqual(len(sent), 1)
        self.assertLessEqual(len(sent[0]), 60)

    def test_random_limit_between_min_and_max(self):
        self.p.settings.update(max_reply="120", max_reply_min="50")
        seen = {self.p._reply_limit_pick() for _ in range(200)}
        self.assertTrue(all(50 <= x <= 120 for x in seen))
        self.assertGreater(len(seen), 10)
        self.p.settings["max_reply_min"] = ""
        self.assertEqual(self.p._reply_limit_pick(), 120)            # empty = old fixed limit
        self.p.settings["max_reply_min"] = "500"
        self.assertEqual(self.p._reply_limit_pick(), 120)            # a minimum above the maximum is clamped
        self.p.settings["max_reply_min"] = "abc"
        self.assertEqual(self.p._reply_limit_pick(), 120)

    def test_saved_settings_keep_their_meaning(self):
        self.assertEqual(self.p._reply_limit(), 600)
        self.p.settings["max_reply"] = "300"
        self.assertEqual(self.p._reply_limit(), 300)
        self.assertEqual(self.p._reply_limit_pick(), 300)
        rows = {getattr(r, "key", None): r for r in all_settings(self.p)}
        self.assertEqual(rows["max_reply_min"].default, "")
        self.assertEqual(rows["newline_pct"].default, "")
        self.assertIs(rows["laugh_control"].default, True)


# ---------------------------------------------------------------- 2. line breaks
class TestLineBreaks(unittest.TestCase):
    def test_screenshot_case(self):
        self.assertEqual(mod.smooth_breaks(u"норм вроде\nтолько в новых пока тупит"),
                         u"норм вроде, только в новых пока тупит")

    def test_break_after_preposition_or_comma_is_a_space(self):
        self.assertEqual(mod.smooth_breaks(u"я сегодня буду в\nцентре"), u"я сегодня буду в центре")
        self.assertEqual(mod.smooth_breaks(u"ну я хз чтобы\nпрям сразу"), u"ну я хз чтобы прям сразу")
        # a question word at the end of a line ends a thought: 'ты как' is a whole question
        self.assertEqual(mod.smooth_breaks(u"да норм\nты как"), u"да норм, ты как")
        self.assertEqual(mod.smooth_breaks(u"ну короче,\nзавтра"), u"ну короче, завтра")

    def test_break_between_finished_thoughts_only_with_chance(self):
        text = u"ок.\nзавтра наберу"
        self.assertEqual(mod.smooth_breaks(text, keep_pct=0, rng=random.Random(1)), u"ок. завтра наберу")
        self.assertEqual(mod.smooth_breaks(text, keep_pct=100, rng=random.Random(1)), text)
        rng = random.Random(5)
        kept = sum("\n" in mod.smooth_breaks(text, keep_pct=10, rng=rng) for _ in range(1000))
        self.assertTrue(40 < kept < 170, kept)
        # never inside a sentence, whatever the chance
        self.assertNotIn("\n", mod.smooth_breaks(u"норм вроде\nтолько тупит", keep_pct=100, rng=rng))

    def test_capitalised_new_sentence_gets_a_period(self):
        self.assertEqual(mod.smooth_breaks(u"Сьогодні вдома\nЗавтра приїду"), u"Сьогодні вдома. Завтра приїду")

    def test_split_reply_merges_without_inner_break(self):
        self.assertEqual(mod.split_reply(u"норм вроде\nтолько в новых\nпока тупит", 1),
                         [u"норм вроде, только в новых, пока тупит"])


class TestLineBreaksInDelivery(Chat):
    def test_model_break_inside_sentence_never_reaches_the_chat(self):
        self.p.settings.update(max_parts="1")
        sent = self.answer(u"норм вроде\nтолько в новых пока тупит")
        self.assertEqual(sent, [u"норм вроде, только в новых пока тупит"])

    def test_split_off_keeps_one_message_without_inner_break(self):
        self.p.settings.update(split_msgs=False)
        sent = self.answer(u"норм вроде\nтолько в новых пока тупит")
        self.assertEqual(len(sent), 1)
        self.assertNotIn("\n", sent[0])

    def test_lines_can_still_be_separate_messages(self):
        self.p.settings.update(max_parts="2")
        sent = self.answer(u"норм вроде\nтолько в новых пока тупит")
        self.assertEqual(sent, [u"норм вроде", u"только в новых пока тупит"])

    def test_group_post_has_no_inner_break(self):
        self.assertEqual(mod.join_parts([u"норм вроде", u"только тупит"]), u"норм вроде, только тупит")


# ---------------------------------------------------------------- 3. facts and identities
class TestUnsupportedFacts(unittest.TestCase):
    def test_flags_relatives_nobody_mentioned(self):
        self.assertEqual(mod.unsupported_facts(u"а как там бабушка?", u"привет, шо делаешь"), ["grandma"])
        self.assertEqual(mod.unsupported_facts(u"мама болеет ещё?", u"ку"), ["mother", "illness"])

    def test_supported_by_context_or_other_form(self):
        self.assertEqual(mod.unsupported_facts(u"как бабуля?", u"моя бабушка в больнице"), [])
        self.assertEqual(mod.unsupported_facts(u"выздоравливай", u"я заболел"), [])
        self.assertEqual(mod.unsupported_facts(u"давно болеешь?", u"я заболел"), [])

    def test_ordinary_replies_are_not_flagged(self):
        for t in (u"та норм все", u"брат, ну ты даёшь", u"скинь папку с файлами", u"бабки есть?",
                  u"мати час це важливо", u"хочу брати участь", u"ахах ну ти даєш", u"завтра на 7 норм"):
            self.assertEqual(mod.unsupported_facts(t, u"шо там"), [], t)


class TestFactsInGeneration(Chat):
    def test_regenerates_once_then_sends_the_safer_reply(self):
        answers = [u"норм, бабушка как?", u"норм все, а у тебя?"]
        sent = self.answer(lambda m, **kw: answers.pop(0), text=u"як справи?")
        self.assertEqual(sent, [u"норм все, а у тебя?"])
        self.assertIn("relatives", CLIENT.ai_calls[-1]["system"])

    def test_both_attempts_bad_drops_the_risky_message(self):
        self.p.settings.update(max_parts="2")
        sent = self.answer(u"да норм\nа бабушка как?", text=u"як справи?")
        self.assertEqual(sent, [u"да норм"])

    def test_fact_from_conversation_is_fine(self):
        sent = self.answer(u"передавай бабушке привет", text=u"я у бабушки сегодня")
        self.assertEqual(sent, [u"передавай бабушке привет"])
        self.assertEqual(len(CLIENT.ai_calls), 1)

    def test_lore_labels_and_identity_rule(self):
        self.p.settings["lore"] = u"Я Влад, живу в Киеве"
        self.p.settings["lore_" + self.p._sk(self.key())] = u"Аня, подруга с универа"
        self.answer(u"ок", text=u"привет")
        system = CLIENT.ai_calls[-1]["system"]
        self.assertIn(u"YOU / ТЫ (the owner", system)
        self.assertIn(u"THE OTHER PERSON / СОБЕСЕДНИК", system)
        self.assertIn("TWO DIFFERENT PEOPLE", system)
        self.assertIn("relatives, illness", system)

    def test_no_identity_block_without_lore(self):
        self.answer(u"ок", text=u"привет")
        self.assertNotIn("TWO DIFFERENT PEOPLE", CLIENT.ai_calls[-1]["system"])
        self.assertIn("nor relatives, illness or events nobody mentioned", CLIENT.ai_calls[-1]["system"])


# ---------------------------------------------------------------- 4. laughter
class TestLaughHelpers(unittest.TestCase):
    def test_detects_spellings(self):
        for t in (u"ахах", u"хах", u"ахахаха", u"ХАХАХ", u"лол", u"ок)))", u"xD", u"хаха ну да", u"\U0001F602"):
            self.assertTrue(mod.has_laugh(t), t)
        for t in (u"аха понял", u"ок)", u"хорошо", u"ха", u"махать", u"хата"):
            self.assertFalse(mod.has_laugh(t), t)

    def test_strip(self):
        self.assertEqual(mod.strip_laughs(u"ахах ну ты даешь"), u"ну ты даешь")
        self.assertEqual(mod.strip_laughs(u"ну ты даешь ахаха)))"), u"ну ты даешь")
        self.assertEqual(mod.strip_laughs(u"лол, серьёзно?"), u"серьёзно?")
        self.assertEqual(mod.strip_laughs(u"ахахах"), u"")

    def test_very_funny(self):
        self.assertTrue(mod.very_funny(u"АХАХАХ"))
        self.assertTrue(mod.very_funny(u"ахахахахаха"))
        self.assertTrue(mod.very_funny(u"\U0001F923"))
        self.assertFalse(mod.very_funny(u"ахах"))


class TestLaughInDelivery(Chat):
    def test_no_laugh_two_replies_in_a_row(self):
        first = self.answer(u"ахах ну ты даешь", text=u"я опять ключи забыл")
        self.assertEqual(first, [u"ахах ну ты даешь"])
        second = self.answer(u"хаха ну бывает", text=u"и телефон тоже")
        self.assertEqual(second, [u"ну бывает"])
        third = self.answer(u"хах ну ты кадр", text=u"и кошелёк")
        self.assertEqual(third, [u"хах ну ты кадр"])
        self.assertEqual(len(CLIENT.ai_calls), 3)                  # cut out, never regenerated

    def test_window_limit(self):
        st = self.p._state(self.key())
        st.laughs.extend([u"ахах", "", u"хах", ""])
        self.assertEqual(self.answer(u"ахаха жесть", text=u"прикинь"), [u"жесть"])

    def test_no_laugh_at_sad_news(self):
        sent = self.answer(u"ахах, держись там)", text=u"у меня бабушка умерла")
        self.assertEqual(sent, [u"держись там"])

    def test_laugh_allowed_when_they_laugh_about_it(self):
        sent = self.answer(u"ахах жесть", text=u"ахах я чуть не помер со смеху")
        self.assertEqual(sent, [u"ахах жесть"])

    def test_caps_only_for_a_really_funny_message(self):
        self.assertEqual(self.answer(u"АХАХАХ ну ты даешь", text=u"смотри что нашёл"), [u"ахахах ну ты даешь"])
        self.p._state(self.key()).laughs.clear()
        self.assertEqual(self.answer(u"АХАХАХ ну это шедевр", text=u"АХАХАХ смотри"), [u"АХАХАХ ну это шедевр"])

    def test_same_spelling_is_varied(self):
        st = self.p._state(self.key())
        st.laughs.extend([u"ахах", ""])
        sent = self.answer(u"ахах ну да", text=u"прикинь")
        self.assertTrue(sent[0].endswith(u" ну да"))
        self.assertNotEqual(sent[0].split()[0], u"ахах")
        self.assertTrue(mod.has_laugh(sent[0]))

    def test_switch_off_keeps_text(self):
        self.p.settings["laugh_control"] = False
        self.answer(u"ахах ну ты даешь", text=u"я опять ключи забыл")
        self.assertEqual(self.answer(u"хаха ну бывает", text=u"и телефон"), [u"хаха ну бывает"])


# ---------------------------------------------------------------- 5. quiz questions
LECTURE = (u"Столица Австралии — Канберра. Многие думают, что это Сидней, но Канберра является столицей с 1913 "
           u"года, она была построена специально как компромисс между Сиднеем и Мельбурном. Например, там "
           u"находится парламент страны и многие государственные учреждения.")


class TestTrivia(Chat):
    def test_question_detection(self):
        for q in (u"какая столица Австралии?", u"сколько будет 17*23?", u"в каком году была битва?",
                  u"що таке фотосинтез", u"напиши код на питоне", u"кто такой Ньютон"):
            self.assertTrue(mod.is_trivia_question(q), q)
        for q in (u"как дела?", u"шо робиш", u"ты где", u"что такое?", u"кто там?", u"будешь завтра?"):
            self.assertFalse(mod.is_trivia_question(q), q)

    def test_reference_answer_to_quiz_is_shortened(self):
        self.p.settings.update(short_msgs=False, max_parts="2")
        sent = self.answer(LECTURE, text=u"а какая столица Австралии?")
        self.assertEqual(len(sent), 1)
        self.assertLessEqual(len(sent[0]), mod.TRIVIA_SHORT_CHARS)
        self.assertEqual(sent[0], u"Столица Австралии — Канберра.")
        self.assertIn("Quiz-like questions", CLIENT.ai_calls[-1]["system"])

    def test_ordinary_long_answer_is_untouched(self):
        self.p.settings.update(short_msgs=False, max_parts="2")
        sent = self.answer(LECTURE, text=u"расскажи как съездил")
        self.assertGreater(len(" ".join(sent)), 200)
        self.assertNotIn("Quiz-like questions", CLIENT.ai_calls[-1]["system"])

    def test_short_answer_to_quiz_is_untouched(self):
        self.assertEqual(self.answer(u"хз, канберра вроде", text=u"какая столица Австралии?"),
                         [u"хз, канберра вроде"])


if __name__ == "__main__":
    unittest.main()
