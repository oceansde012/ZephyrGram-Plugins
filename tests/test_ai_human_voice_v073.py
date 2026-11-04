"""0.7.3: replies in the owner's voice again. The prompt opens with the owner's voice (not 'an automatic assistant'),
the owner's style section (measured style + real messages) closes it right before the language rule, and the
prompt_max guard shrinks lore and rules before it drops style examples. Fake Zephyr, no network."""
import re

from test_ai_autoreply import CLIENT, DID, mod
from test_ai_autoreply_v053 import Fakes, total_chars

OWNER = [u"та норм все", u"хз, ще не думав", u"ахах ну ти даєш", u"я вже вдома", u"завтра скину",
         u"нє, сьогодні не вийде", u"давай в суботу краще", u"бля забув зовсім", u"щас гляну", u"ок, тоді на 7",
         u"та він знову тупить", u"не, машина в сервісі ще", u"кажуть до пятниці", u"ну такоє",
         u"я хз шо там по грошах", u"скинь фотку", u"о, норм виглядає", u"ваще кайф", u"ага",
         u"слухай, а шо там з квартирою", u"я пізніше наберу", u"на роботі завал", u"короч не встигаю",
         u"давай без мене цього разу", u"ну ок", u"та ладно тобі", u"шо по матчу вчора", u"капец вони злили",
         u"я ж казав", u"в неділю точно вільний"]
OTHER = [u"привіт, шо робиш?", u"ти де?", u"підеш завтра?", u"а коли зможеш?", u"шо з машиною?",
         u"скільки ще ремонт?", u"ну шо там", u"бачив новини?", u"го в суботу", u"о 7 норм?"]
LORE = u"Я Влад, працюю в ДСНС, живу в Києві, люблю CS і котів, маю машину. " * 40
OWN_PROMPT = u"Пиши коротко, без офіціозу, як я з друзями, не вигадуй планів. " * 70


def examples_in(system):
    m = re.search(r"STYLE EXAMPLES ONLY.*?:\n((?:- .*\n?)+)", system)
    return m.group(1).strip().split("\n") if m else []


class TestOwnerVoice(Fakes):
    def setUp(self):
        super().setUp()
        self.p.settings.update(memory_auto=False, learn_style=True)
        now = int(self.clock[0])
        rows = []
        for i in range(70):
            out = i % 7 not in (0, 3)
            text = OWNER[i % len(OWNER)] if out else OTHER[i % len(OTHER)]
            rows.append({"id": i + 1, "date": now - 7000 + i * 60, "text": text, "out": out,
                         "from_id": 111 if out else 7, "dialog_id": DID, "account": 0})
        CLIENT.history[:] = rows

    def system(self):
        self.reply(u"слухай а ти завтра на матч підеш? і шо там з машиною?")
        calls = self.reply_calls()
        self.assertTrue(calls)
        return calls[0]

    def test_prompt_opens_with_the_owner_voice_and_keeps_the_honest_answer(self):
        system = self.system()["system"]
        self.assertTrue(system.startswith("Write the next message of this Telegram account's owner"))
        self.assertNotIn("You are an automatic assistant", system)
        self.assertNotIn("you ARE the owner", system)
        self.assertIn("Use their texting style without claiming to be them", system)
        self.assertIn("not like an assistant", system)
        self.assertIn("honestly say this is an automatic AI assistant", system)
        self.assertIn("never claim to be a human or the account owner and never deny automation", system)

    def test_style_section_is_last_before_the_language_rule(self):
        system = self.system()["system"]
        style = system.index("How the owner writes")
        examples = system.index("STYLE EXAMPLES ONLY")
        lang = system.rindex("LANGUAGE OF THIS REPLY")
        self.assertLess(style, examples)
        self.assertLess(examples, lang)
        for earlier in ("Current UTC time:", "GENDER.", "Message format", "Conversation style:"):
            if earlier in system:
                self.assertLess(system.index(earlier), style, earlier)
        self.assertIn("reads like one more message of this list", system[examples:lang])
        self.assertEqual(len(examples_in(system)), 24)
        self.assertTrue(system.rstrip().endswith(mod.lang_rule("Ukrainian").rstrip()))

    def test_typical_request_does_not_cost_more_than_before(self):
        """0.7.1 sent ~7270 characters for this chat (system ~6740); 0.7.3 must stay within +10%."""
        call = self.system()
        self.assertLess(len(call["system"]), 6740 * 1.1)
        self.assertLess(total_chars(call), 7270 * 1.1)
        self.assertFalse(any(d.get("r") == "prompt_trimmed" for d in self.p._decisions))

    def test_lore_and_own_prompt_are_cut_before_the_style_examples(self):
        """0.7.1 dropped all 24 examples (24 -> 12 -> 6 -> 0) before touching lore or the owner's prompt."""
        self.p.settings.update(lore=LORE, default_prompt=OWN_PROMPT)
        call = self.system()
        system = call["system"]
        cap = int((mod.PROMPT_MAX_DEFAULT - mod.RETRY_RESERVE) * mod.SYSTEM_SHARE)
        self.assertLessEqual(len(system), cap)
        self.assertLessEqual(total_chars(call), mod.PROMPT_MAX_DEFAULT)
        self.assertGreaterEqual(len(examples_in(system)), mod.STYLE_MIN_EXAMPLES)
        self.assertIn("How the owner writes", system)
        self.assertIn("Extra instructions from the owner", system)
        self.assertIn("LANGUAGE OF THIS REPLY", system[system.index("STYLE EXAMPLES ONLY"):])
        self.assertTrue(any(d.get("r") == "prompt_trimmed" for d in self.p._decisions))

    def test_smallest_budget_keeps_rules_language_and_bounds_the_style_share(self):
        self.p.settings.update(lore=LORE, default_prompt=OWN_PROMPT, prompt_max="8000")
        long_own = [u"довге моє повідомлення номер %d " % i + u"ж" * 160 for i in range(40)]
        self.p.get_profile = lambda *a, **k: {"examples": long_own, "style": mod.compute_style(long_own)}
        call = self.system()
        system = call["system"]
        cap = int((8000 - mod.RETRY_RESERVE) * mod.SYSTEM_SHARE)
        self.assertLessEqual(len(system), cap)
        self.assertLessEqual(total_chars(call), 8000)
        self.assertIn(mod.HUMAN_PROMPT[:60], system)
        self.assertIn("LANGUAGE OF THIS REPLY", system)
        style_part = system[system.index("How the owner writes"):system.rindex("LANGUAGE OF THIS REPLY")]
        self.assertLessEqual(len(style_part), cap * mod.STYLE_MAX_SHARE + 10)
        self.assertGreater(len(examples_in(system)), 0)

    def test_huge_inputs_never_exceed_the_hard_limits(self):
        self.p.settings.update(lore=LORE * 3, default_prompt=OWN_PROMPT * 3, context_chars="48000",
                               context_n="100")
        big = [u"приклад мого стилю " * 10 for _ in range(40)]
        self.p.get_profile = lambda *a, **k: {"examples": big, "style": {}}
        for limit, expected in (("", mod.PROMPT_MAX_DEFAULT), ("8000", 8000), ("999999", mod.PROMPT_MAX_HARD)):
            self.calls[:] = []
            self.p.settings["prompt_max"] = limit
            self.clock[0] += 100
            self.reply(u"ПИТАННЯ " + u"z" * 30000 + u" КІНЕЦЬ?")
            for call in self.reply_calls():
                self.assertLessEqual(total_chars(call), expected, limit)
                self.assertIn("LANGUAGE OF THIS REPLY", call["system"], limit)

    def test_message_count_in_the_format_rule_matches_the_split_maximum(self):
        self.assertIn("into 1-2 SHORT separate chat messages", self.system()["system"])
        self.p.settings["max_parts"] = "4"
        self.p._profiles.clear()
        self.assertIn("into 1-4 SHORT separate chat messages", self.p.build_system(self.key(), {}))
        self.p.settings["max_parts"] = "1"
        self.assertIn("into 1-2 SHORT separate chat messages", self.p.build_system(self.key(), {}))

    def test_dated_context_is_compact(self):
        system = self.system()["system"]
        block = system[system.index("Current UTC time:"):]
        block = block[:block.index("\n\n")]
        self.assertNotIn("message_id", block)
        self.assertIn('"speaker":"owner"', block)
        self.assertIn(u"шо там з машиною", block)

    def test_natural_profile_also_writes_in_the_owner_voice(self):
        self.p._natural_profile_changed(True)
        self.p.settings["memory_auto"] = False
        system = self.system()["system"]
        self.assertTrue(system.startswith("Write the next message of this Telegram account's owner"))
        self.assertIn(mod.NATURAL_CHAT_PROMPT, system)
        self.assertIn(mod.DISCLOSE_RULE, system)
        self.assertLess(system.index("STYLE EXAMPLES ONLY"), system.rindex("LANGUAGE OF THIS REPLY"))

    def test_build_system_without_style_leaves_the_section_to_fit_prompt(self):
        profile = {"examples": OWNER, "style": mod.compute_style(OWNER)}
        full = self.p.build_system(self.key(), profile)
        bare = self.p.build_system(self.key(), profile, with_style=False)
        self.assertIn("STYLE EXAMPLES ONLY", full)
        self.assertNotIn("STYLE EXAMPLES ONLY", bare)
        self.assertNotIn("How the owner writes", bare)
        self.assertTrue(full.endswith(self.p._style_block(profile, 24)))


if __name__ == "__main__":
    import unittest
    unittest.main()
