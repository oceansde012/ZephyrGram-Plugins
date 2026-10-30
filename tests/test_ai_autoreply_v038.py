"""Per-chat media opt-in, account isolation and cancellation regression tests; no real network."""
import json

from test_ai_autoreply import Base, CLIENT, DID, mod


class TestScopedAttachments(Base):
    def setUp(self):
        super().setUp()
        self.enable()
        self.p.settings.update(humanize=False, disclosure=False, typing_delay=False, owner_active="0")
        self.sk = self.p._sk(self.key())
        self.media_calls, self.voice_calls, self.transcripts, self.completions = [], [], [], []
        self.original_ai = CLIENT.ai_complete
        self.original_send = CLIENT.send_text
        self.original_account = CLIENT.current_account

        def complete(messages, **kwargs):
            self.completions.append((messages, kwargs))
            return "добре"

        def media(did, mid, account=None):
            self.media_calls.append((did, mid, account))
            return {"type": "photo", "image_b64": "aW1hZ2U=", "image_kind": "photo"}

        def voice(did, mid, account=None):
            self.voice_calls.append((did, mid, account))
            return {"type": "voice", "audio_b64": "YXVkaW8=", "mime": "audio/ogg"}

        def transcribe(audio, **kwargs):
            self.transcripts.append((audio, kwargs))
            return "привіт, як справи?"

        CLIENT.ai_complete = complete
        CLIENT.get_message_media = media
        CLIENT.get_voice = voice
        CLIENT.ai_transcribe = transcribe

    def tearDown(self):
        CLIENT.ai_complete = self.original_ai
        CLIENT.send_text = self.original_send
        CLIENT.current_account = self.original_account
        for name in ("get_message_media", "get_voice", "ai_transcribe"):
            if hasattr(CLIENT, name):
                delattr(CLIENT, name)

    def attachment(self, text="", mid=33, **extra):
        m = self.msg(text=text, mid=mid)
        m.update(has_media=True, **extra)
        self.p._handle_dict(0, DID, m)
        self.fire_timers()

    def test_global_legacy_switch_does_not_grant_chat_consent(self):
        self.p.settings["see_media"] = True
        self.attachment()
        self.assertEqual(self.media_calls + self.voice_calls + self.completions, [])

    def test_photo_only_opted_in_chat_is_sent_with_images_and_explicit_account(self):
        self.p.settings["see_media_" + self.sk] = True
        self.attachment()
        self.assertEqual(self.media_calls, [(DID, 33, 0)])
        self.assertEqual(self.voice_calls, [])
        self.assertEqual(self.completions[0][1]["images"], ["aW1hZ2U="])
        self.assertIn("image/frame attached", self.completions[0][0][-1]["content"])
        self.assertEqual(CLIENT.sent[0][0], DID)

    def test_voice_transcript_only_when_voice_consent_on(self):
        self.p.settings["transcribe_voice_" + self.sk] = True
        self.attachment()
        self.assertEqual(self.media_calls, [])
        self.assertEqual(self.voice_calls, [(DID, 33, 0)])
        self.assertEqual(len(self.transcripts), 1)
        self.assertIn("привіт, як справи?", self.completions[0][0][-1]["content"])
        self.assertNotIn("images", self.completions[0][1])

    def test_transcription_403_does_not_reply_or_disable_chat(self):
        self.p.settings["transcribe_voice_" + self.sk] = True

        def denied(*args, **kwargs):
            raise RuntimeError("HTTP 403 provider access denied")

        CLIENT.ai_transcribe = denied
        self.attachment()
        self.assertEqual(self.completions, [])
        self.assertEqual(CLIENT.sent, [])
        self.assertTrue(self.p.is_enabled(self.key()))
        self.assertEqual(self.p._chats[self.key()].get("fails", 0), 0)
        self.assertIn("voice_transcription_unavailable", [r["r"] for r in self.p._decisions])

    def test_revocation_during_voice_download_prevents_transmission(self):
        self.p.settings["transcribe_voice_" + self.sk] = True

        def download(*args, **kwargs):
            self.p.settings["transcribe_voice_" + self.sk] = False
            return {"type": "voice", "audio_b64": "private"}

        CLIENT.get_voice = download
        self.attachment()
        self.assertEqual(self.transcripts + self.completions, [])
        self.assertEqual(CLIENT.sent, [])

    def test_epoch_change_during_transcription_discards_late_result(self):
        self.p.settings["transcribe_voice_" + self.sk] = True

        def transcribe(*args, **kwargs):
            self.p.on_app_event("settings_changed")
            return "late private transcription"

        CLIENT.ai_transcribe = transcribe
        self.attachment()
        self.assertEqual(self.completions, [])
        self.assertEqual(CLIENT.sent, [])

    def test_revocation_during_image_download_prevents_image_upload(self):
        self.p.settings["see_media_" + self.sk] = True

        def image(*args, **kwargs):
            self.p.settings["see_media_" + self.sk] = False
            return {"type": "photo", "image_b64": "private"}

        CLIENT.get_message_media = image
        self.attachment()
        self.assertEqual(self.completions, [])
        self.assertEqual(CLIENT.sent, [])

    def test_epoch_change_during_completion_prevents_late_reply(self):
        self.p.settings["see_media_" + self.sk] = True

        def complete(*args, **kwargs):
            self.p.on_app_event("settings_changed")
            return "late reply"

        CLIENT.ai_complete = complete
        self.attachment()
        self.assertEqual(CLIENT.sent, [])
        self.assertEqual(self.p._chats[self.key()].get("fails", 0), 0)

    def test_other_chat_or_account_payload_never_fetches_media(self):
        self.p.settings["see_media_" + self.sk] = True
        self.attachment(dialog_id=999)
        self.attachment(mid=34, account=2)
        self.assertEqual(self.media_calls + self.voice_calls + self.completions, [])

    def test_consent_for_another_chat_does_not_apply_here(self):
        self.p.settings["see_media_0_999"] = True
        self.p.settings["transcribe_voice_1_42"] = True
        self.attachment()
        self.assertEqual(self.media_calls + self.voice_calls + self.completions, [])

    def test_secret_media_never_fetched(self):
        self.p.settings["see_media_" + self.sk] = True
        self.p.settings["transcribe_voice_" + self.sk] = True
        self.attachment(is_secret=True)
        self.assertEqual(self.media_calls + self.voice_calls, [])

    def test_per_chat_switches_are_exposed_off_by_default(self):
        self.p._open_key = self.key()
        settings = {getattr(item, "key", None): item for item in self.p.create_settings()}
        self.assertFalse(settings["see_media_" + self.sk].default)
        self.assertFalse(settings["transcribe_voice_" + self.sk].default)
        self.assertNotIn("see_media", settings)

    def test_legacy_account_fallback_cannot_send_as_another_account(self):
        CLIENT.current_account = lambda: 2
        with self.assertRaisesRegex(RuntimeError, "Explicit-account"):
            self.p.send(DID, "private", None, account=0)
        self.assertEqual(CLIENT.sent, [])

    def test_explicit_account_send_uses_requested_account(self):
        calls = []
        CLIENT.send_text = lambda did, text, reply_to=None, account=None: calls.append(account)
        CLIENT.current_account = lambda: 2
        self.p.send(DID, "private", None, account=0)
        self.assertEqual(calls, [0])

    def test_historical_media_is_not_added_to_reply_images(self):
        self.p.settings["see_media_" + self.sk] = True
        CLIENT.history[:] = [{"id": 11, "dialog_id": DID, "out": False, "text": "старе фото",
                              "date": int(self.clock[0] - 30), "has_media": True}]
        self.attachment(mid=33)
        self.assertEqual(self.media_calls, [(DID, 33, 0)])

    def test_unload_during_download_stops_transcription(self):
        self.p.settings["transcribe_voice_" + self.sk] = True

        def download(*args, **kwargs):
            self.p.on_plugin_unload()
            return {"audio_b64": "private", "type": "voice"}

        CLIENT.get_voice = download
        self.attachment()
        self.assertEqual(self.transcripts + self.completions, [])
        self.assertEqual(CLIENT.sent, [])
