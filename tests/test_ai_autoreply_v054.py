"""Natural chat profile: explicit opt-in, no new recipients or consent, no cosmetic paid rewrites."""
from test_ai_autoreply import Base, CLIENT, DID, mod, screen


class TestNaturalProfile(Base):
    def setUp(self):
        super().setUp()
        self.enable()
        self.p.settings["memory_auto"] = False

    def test_existing_installation_is_not_silently_reconfigured(self):
        self.assertFalse(self.p.get_setting("natural_chat", False))
        self.assertEqual(self.p._model_for("reply"), "")

    def test_activation_sets_models_without_enabling_chats_or_media(self):
        self.p.settings.update(master=False, reply_all=False, style_share=False,
                               memory_auto=False, see_media_0_42=False,
                               transcribe_voice_0_42=False)
        before = dict(self.p._chats)
        old_epoch = self.p._config_epoch
        self.p._natural_profile_changed(True)
        self.assertEqual(self.p._model_for("reply"), "glm-5.3")
        self.assertEqual(self.p._model_for("memory"), "DeepSeek-V4.1-Flash")
        self.assertEqual(self.p.get_setting("temperature"), "0.85")
        self.assertFalse(self.p.get_setting("short_msgs"))
        self.assertTrue(self.p.get_setting("disclosure"))
        self.assertEqual(before, self.p._chats)
        for key in ("master", "reply_all", "style_share", "memory_auto", "see_media_0_42", "transcribe_voice_0_42"):
            self.assertFalse(self.p.get_setting(key), key)
        self.assertGreater(self.p._config_epoch, old_epoch)

    def test_switch_off_keeps_explicit_model_changes(self):
        self.p._natural_profile_changed(True)
        self.p.settings["model"] = "my-choice"
        self.p._natural_profile_changed(False)
        self.assertFalse(self.p.get_setting("natural_chat"))
        self.assertEqual(self.p._model_for("reply"), "my-choice")

    def test_natural_prompt_does_not_force_tiny_sentences_or_human_identity(self):
        self.p._natural_profile_changed(True)
        # An old saved short/disclosure preference cannot contradict the profile.
        self.p.settings.update(short_msgs=True, disclosure=False)
        system = self.p.build_system(self.key(), {})
        self.assertIn(mod.NATURAL_CHAT_PROMPT, system)
        self.assertNotIn(mod.SHORT_RULE, system)
        self.assertNotIn("you ARE the owner", system)
        self.assertIn(mod.DISCLOSE_RULE, system)

    def test_normal_empathy_is_not_a_reason_to_pay_for_another_generation(self):
        self.p._natural_profile_changed(True)
        CLIENT.ai_result = lambda messages: "розумію, день видався важкий"
        messages = [{"role": "user", "content": "сьогодні якийсь дуже важкий день"}]
        parts, why = self.p.generate(self.key(), 0, DID, messages, self.p._chats[self.key()],
                                     self.p._state(self.key()))
        self.assertEqual(len(CLIENT.ai_calls), 1)
        self.assertTrue(parts[0].startswith("розумію"))
        self.assertEqual(why, "")

    def test_explicit_bans_and_wrong_language_still_apply(self):
        self.p._natural_profile_changed(True)
        self.assertEqual(self.p.reply_problems("розумію, звісно", None, "як ти?"), [])
        self.assertTrue(any(p.startswith("banned:") for p in
                            self.p.reply_problems("ось заборонене", None, extra=["заборонене"])))
        self.assertIn("wrong-lang", self.p.reply_problems("你好世界", None, "як ти?"))
        self.assertEqual(self.p.reply_problems("це автоматичний помічник", None, "це бот?"), [])

    def test_switch_is_available_on_style_screen(self):
        item = next(i for i in screen(self.p, "style") if getattr(i, "key", None) == "natural_chat")
        self.assertEqual(item.on_change, self.p._natural_profile_changed)
        for key in ("natural_chat", "natural_chat_s"):
            self.assertEqual(len(mod.S[key]), 3)
            self.assertTrue(all(mod.S[key]))
