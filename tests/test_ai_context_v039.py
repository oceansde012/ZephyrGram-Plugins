"""Recent-context, answer-detail and style isolation tests; no AI server or Telegram network."""
from test_ai_autoreply import Base, CLIENT, DID, mod


class TestContextV039(Base):
    def setUp(self):
        super().setUp()
        self.enable()
        self.original_history = CLIENT.get_recent_messages

    def tearDown(self):
        CLIENT.get_recent_messages = self.original_history

    def row(self, mid, text, out=False, date=None, **extra):
        return dict(id=mid, text=text, out=out, date=mid if date is None else date,
                    dialog_id=DID, account=0, from_id=7, **extra)

    def test_default_context_fetches40_and_accepts_explicit100(self):
        calls = []
        CLIENT.get_recent_messages = lambda did, limit=20, account=None: calls.append((did, limit, account)) or []
        self.p.build_messages(self.key(), 0, DID, [(200, 7, "current question")])
        self.assertEqual(calls[-1], (DID, 40, 0))
        self.p.settings["context_n"] = "100"
        self.p.build_messages(self.key(), 0, DID, [(201, 7, "new question")])
        self.assertEqual(calls[-1][1], 100)
        self.p.settings["context_n"] = "9999"
        self.p.build_messages(self.key(), 0, DID, [(202, 7, "another question")])
        self.assertEqual(calls[-1][1], 100)

    def test_old_explicit_context_count_is_preserved(self):
        self.p.settings["context_n"] = "10"
        calls = []
        CLIENT.get_recent_messages = lambda did, limit=20, account=None: calls.append(limit) or []
        self.p.build_messages(self.key(), 0, DID, [(1, 7, "question")])
        self.assertEqual(calls, [10])

    def test_history_wrong_chat_account_and_service_are_excluded(self):
        rows = [self.row(1, "correct"), dict(self.row(2, "wrong chat"), dialog_id=999),
                dict(self.row(3, "wrong account"), account=1), self.row(4, "secret", is_secret=True),
                self.row(5, "service", is_service=True)]
        CLIENT.get_recent_messages = lambda *args, **kw: rows
        got = self.p._load_history(self.key(), 0, DID, 100)
        self.assertEqual([h["text"] for h in got], ["correct"])
        self.assertEqual(self.p._load_history(self.key(), 1, DID, 100), [])

    def test_history_order_and_duplicates_are_normalized(self):
        CLIENT.get_recent_messages = lambda *args, **kw: [self.row(3, "third"), self.row(2, "second"),
                                                          self.row(1, "first"), self.row(2, "second")]
        self.assertEqual([h["id"] for h in self.p._load_history(self.key(), 0, DID, 40)], [1, 2, 3])

    def test_interleaved_current_parts_preserve_speaker_roles_and_order(self):
        hist = [self.row(12, "second question"), self.row(11, "owner clarification", out=True), self.row(10, "first question")]
        messages = self.p.build_messages(self.key(), 0, DID,
                                        [(12, 7, "second question"), (10, 7, "first question")], hist)
        self.assertEqual([(m["role"], m["content"]) for m in messages],
                         [("user", "first question"), ("assistant", "owner clarification"), ("user", "second question")])

    def test_missing_earlier_part_is_not_appended_after_later_part(self):
        got = self.p.build_messages(self.key(), 0, DID, [(12, 7, "part two"), (11, 7, "part one")],
                                    [self.row(12, "part two", date=int(self.clock[0]))])
        self.assertEqual([m["content"] for m in got], ["part one", "part two"])

    def test_owner_already_answered_is_not_turned_into_new_question(self):
        got = self.p.build_messages(self.key(), 0, DID, [(10, 7, "question")],
                                    [self.row(10, "question"), self.row(11, "answered", out=True)])
        self.assertEqual(got, [])

    def test_budget_preserves_all_current_parts_before_old_context(self):
        self.p.settings["context_chars"] = "2000"
        messages = [{"role": "user", "content": "old" * 2000}, {"role": "assistant", "content": "old reply"},
                    {"role": "user", "content": "first question"}, {"role": "user", "content": "Q" * 1500}]
        got = self.p._bound_context(messages, [2, 3])
        self.assertLessEqual(sum(len(m["content"]) for m in got), 2000)
        self.assertEqual(got[-2:], messages[-2:])

    def test_oversized_latest_question_keeps_its_start_and_end_with_explicit_marker(self):
        self.p.settings["context_chars"] = "2000"
        text = "LATEST QUESTION START " + "x" * 7000 + " IMPORTANT QUESTION END?"
        got = self.p._bound_context([{"role": "user", "content": "old"}, {"role": "user", "content": text}])
        self.assertLessEqual(sum(len(m["content"]) for m in got), 2000)
        self.assertTrue(got[-1]["content"].startswith("LATEST QUESTION START"))
        self.assertTrue(got[-1]["content"].endswith("IMPORTANT QUESTION END?"))
        self.assertIn("[context trimmed]", got[-1]["content"])

    def test_default_budget_does_not_shorten_question_just_because_history_has_many_user_messages(self):
        messages = [{"role": "user", "content": "history"} for _ in range(39)]
        messages.append({"role": "user", "content": "question " * 500})
        got = self.p._bound_context(messages)
        self.assertEqual(got[-1], messages[-1])

    def test_reply_detail_modes_and_explicit_limit(self):
        self.assertEqual(self.p._answer_detail(), 1)
        self.assertEqual(self.p._reply_limit(), 1200)
        self.assertIn("Balanced answer", self.p._detail_rule())
        self.p.settings["answer_detail"] = 2
        self.assertEqual(self.p._reply_limit(), 3000)
        self.assertIn("all parts", self.p._detail_rule())
        self.p.settings["answer_detail"] = 0
        self.assertEqual(self.p._reply_limit(), 400)
        self.p.settings["max_reply"] = "300"
        self.p.settings["answer_detail"] = 2
        self.assertEqual(self.p._reply_limit(), 300)

    def test_prompts_distinguish_style_from_facts_and_do_not_force_one_line(self):
        style = mod.compute_style(["так, буду" for _ in range(10)])
        system = self.p.build_system(self.key(), {"examples": ["style example"], "style": style})
        self.assertNotIn("3-12 words", system)
        self.assertNotIn("no explanations", system)
        self.assertIn("STYLE EXAMPLES ONLY, not factual memory", system)
        self.assertIn("current question", system)
        self.assertIn("Balanced answer", system)

    def test_style_borrowing_off_by_default_and_opt_in_never_crosses_accounts(self):
        self.p._chats["0:77"] = dict(enabled=True, account=0, dialog_id=77)
        self.p._chats["1:88"] = dict(enabled=True, account=1, dialog_id=88)
        calls = []

        def history(did, limit=20, account=None):
            calls.append((account, did))
            return [dict(self.row(1, "mine" if did == DID else "other style", out=True), dialog_id=did, account=account)]

        CLIENT.get_recent_messages = history
        self.p.get_profile(self.key(), 0, DID)
        self.assertEqual(calls, [(0, DID)])
        calls.clear()
        self.p.settings["style_share"] = True
        self.p.get_profile(self.key(), 0, DID)
        self.assertIn((0, 77), calls)
        self.assertNotIn((1, 88), calls)

    def test_context_detail_settings_are_localized_and_have_safe_defaults(self):
        for lang in [1, 2, 3]:
            self.p.settings["ui_lang"] = lang
            rows = {getattr(i, "key", None): i for i in self.p.create_settings()}
            self.assertEqual(rows["context_n"].default, "40")
            self.assertEqual(rows["context_chars"].default, "16000")
            self.assertEqual(rows["answer_detail"].default, 1)
            self.assertEqual(rows["max_reply"].default, "")
            self.assertFalse(rows["style_share"].default)
            self.assertNotEqual(self.p.t("answer_detail"), "answer_detail")
