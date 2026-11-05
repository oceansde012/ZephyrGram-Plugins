"""ai_autoreply 0.9.7: video / round-video frames through client.video_frame, older mentioned video, profile bio; fake bridge."""
import base64
import os
import tempfile

from test_ai_autoreply import Base, CLIENT, DID, mod


class Page(object):
    def __init__(self, key, text, subtext=None, icon=None):
        self.key, self.text, self.subtext, self.icon = key, text, subtext, icon


class VideoBase(Base):
    NAMES = ("get_message_media", "video_frame", "VIDEO_FRAME", "get_user_profile", "USER_PROFILE")

    def setUp(self):
        super().setUp()
        self.enable()
        self.p.settings.update(humanize=False, disclosure=False, typing_delay=False, owner_active="0")
        self.sk = self.p._sk(self.key())
        self.completions, self.frame_calls, self.media_types = [], [], {}
        self._orig = {n: (hasattr(CLIENT, n), getattr(CLIENT, n, None)) for n in self.NAMES + ("ai_complete",)}
        self.tmp = tempfile.mkdtemp()
        self.frame_path = os.path.join(self.tmp, "f.jpg")
        with open(self.frame_path, "wb") as f:
            f.write(b"\xff\xd8frame\xff\xd9")
        self.frame_b64 = base64.b64encode(b"\xff\xd8frame\xff\xd9").decode()

        def complete(messages, **kwargs):
            self.completions.append((messages, kwargs))
            return "ок"

        def media(did, mid, account=None):
            return {"type": self.media_types.get(mid, "video"), "image_b64": "dGh1bWI=", "image_kind": "thumb"}

        def frame(did, mid, account=None, at_ms=None, timeout_s=20):
            self.frame_calls.append((did, mid, account))
            return self.frame_path

        CLIENT.ai_complete = complete
        CLIENT.get_message_media = media
        CLIENT.video_frame = frame
        CLIENT.VIDEO_FRAME = True

    def tearDown(self):
        for n, (ex, v) in self._orig.items():
            if ex:
                setattr(CLIENT, n, v)
            elif hasattr(CLIENT, n):
                delattr(CLIENT, n)
        super().tearDown()

    def video(self, text="", mid=33):
        m = self.msg(text=text, mid=mid)
        m.update(has_media=True)
        self.p._handle_dict(0, DID, m)
        self.fire_timers()


class TestVideoFrame(VideoBase):
    def test_off_by_default_keeps_the_preview(self):
        self.p.settings["see_media_" + self.sk] = True
        self.video()
        self.assertEqual(self.frame_calls, [])
        self.assertEqual(self.completions[0][1]["images"], ["dGh1bWI="])

    def test_switch_on_replaces_preview_with_frame(self):
        self.p.settings["see_media_" + self.sk] = True
        self.p.settings["see_video_" + self.sk] = True
        self.video()
        self.assertEqual(self.frame_calls, [(DID, 33, 0)])
        self.assertEqual(self.completions[0][1]["images"], [self.frame_b64])
        self.assertIn("video frame", self.completions[0][0][-1]["content"])

    def test_old_app_without_flag_behaves_as_before(self):
        del CLIENT.VIDEO_FRAME
        self.p.settings["see_media_" + self.sk] = True
        self.p.settings["see_video_" + self.sk] = True
        self.video()
        self.assertEqual(self.frame_calls, [])
        self.assertEqual(self.completions[0][1]["images"], ["dGh1bWI="])

    def test_failed_frame_falls_back_to_preview(self):
        CLIENT.video_frame = lambda *a, **k: None
        self.p.settings["see_media_" + self.sk] = True
        self.p.settings["see_video_" + self.sk] = True
        self.video()
        self.assertEqual(self.completions[0][1]["images"], ["dGh1bWI="])

    def test_oversized_frame_is_dropped(self):
        with open(self.frame_path, "wb") as f:
            f.write(b"x" * 400001)
        self.p.settings["see_media_" + self.sk] = True
        self.p.settings["see_video_" + self.sk] = True
        self.assertIsNone(self.p._video_frame_b64(DID, 33, 0))

    def test_video_switch_alone_without_see_media_sends_nothing(self):
        self.p.settings["see_video_" + self.sk] = True
        self.video()
        self.assertEqual(self.frame_calls, [])
        self.assertEqual(self.completions, [])

    def test_mentioned_earlier_video_is_attached(self):
        self.p.settings["see_media_" + self.sk] = True
        self.p.settings["see_video_" + self.sk] = True
        old = self.msg(text="", mid=20)
        old.update(has_media=True, dialog_id=DID, account=0, is_service=False, is_secret=False)
        CLIENT.history.append(old)
        self.media_types[20] = "video"
        self.p._handle_dict(0, DID, self.msg(text="ты посмотрел видео которое я скинул?", mid=40))
        self.fire_timers()
        self.assertIn((DID, 20, 0), self.frame_calls)
        self.assertEqual(self.completions[0][1]["images"], [self.frame_b64])
        self.assertIn("talking about a video", self.completions[0][0][-1]["content"])

    def test_no_video_words_no_extra_frame(self):
        self.p.settings["see_media_" + self.sk] = True
        self.p.settings["see_video_" + self.sk] = True
        old = self.msg(text="", mid=20)
        old.update(has_media=True, dialog_id=DID, account=0, is_service=False, is_secret=False)
        CLIENT.history.append(old)
        self.p._handle_dict(0, DID, self.msg(text="как дела", mid=40))
        self.fire_timers()
        self.assertEqual(self.frame_calls, [])


class TestProfileBio(VideoBase):
    def test_public_call_is_used_when_flag_present(self):
        CLIENT.USER_PROFILE = True
        CLIENT.get_user_profile = lambda uid, account=None: {"bio": "люблю кофе"}
        self.assertEqual(self.p._peer_bio(0, DID), "люблю кофе")

    def test_without_flag_falls_back_silently(self):
        CLIENT.get_user_profile = lambda uid, account=None: {"bio": "x"}
        self.assertNotEqual(self.p._peer_bio(0, DID), "x")


class TestPages(VideoBase):
    def setUp(self):
        super().setUp()
        self._pg = (mod.Page, getattr(CLIENT, "SETTINGS_PAGES", None))
        mod.Page, CLIENT.SETTINGS_PAGES = Page, True

    def tearDown(self):
        mod.Page = self._pg[0]
        if self._pg[1] is None:
            del CLIENT.SETTINGS_PAGES
        else:
            CLIENT.SETTINGS_PAGES = self._pg[1]
        super().tearDown()

    def test_xmedia_page_lists_media_switches_and_fits_limit(self):
        self.p.settings["ui_mode"] = 1
        items = self.p.create_settings("pg_xmedia:" + self.key())
        keys = [getattr(i, "key", None) for i in items]
        for k in ("see_media_" + self.sk, "see_video_" + self.sk, "transcribe_voice_" + self.sk):
            self.assertIn(k, keys)
        self.assertLessEqual(len(items), 14)
        access = [getattr(i, "key", None) for i in self.p.create_settings("pg_access:" + self.key())]
        self.assertIn("pg_xmedia:" + self.key(), access)
