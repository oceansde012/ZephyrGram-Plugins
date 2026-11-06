"""ai_autoreply 0.9.9: saved GIF after the text (flag-guarded, off by default), two-tap memory reset, news at the bottom."""
from test_ai_autoreply import Base, CLIENT, DID, mod

NAMES = ("send_saved_gif", "get_saved_gifs", "SEND_GIF", "SAVED_GIFS")


class GifBase(Base):
    def setUp(self):
        super().setUp()
        self.enable()
        self.p.settings.update(humanize=False, disclosure=False, typing_delay=False, owner_active="0",
                               cooldown="0", stickers=False, sticker_pct="0")
        self._orig = {n: (hasattr(CLIENT, n), getattr(CLIENT, n, None)) for n in NAMES}
        self.gifs = []
        CLIENT.get_saved_gifs = lambda limit=100, account=None: [{"id": 501}, {"id": 502}]
        CLIENT.send_saved_gif = lambda did, gid, reply_to=None, account=None, on_done=None: self.gifs.append((did, gid)) or None
        CLIENT.SEND_GIF = True
        CLIENT.SAVED_GIFS = True

    def tearDown(self):
        for n, (ex, v) in self._orig.items():
            if ex:
                setattr(CLIENT, n, v)
            elif hasattr(CLIENT, n):
                delattr(CLIENT, n)
        super().tearDown()

    def talk(self):
        self.incoming(text="today was a long day")
        self.fire_timers()


class TestGif(GifBase):
    def test_off_by_default(self):
        self.p.settings["gif_pct"] = "100"
        self.talk()
        self.assertEqual(self.gifs, [])
        self.assertTrue(CLIENT.sent)

    def test_on_sends_after_the_text(self):
        self.p.settings.update(gifs=True, gif_pct="100")
        self.talk()
        self.assertEqual(len(self.gifs), 1)
        self.assertEqual(self.gifs[0][0], DID)
        self.assertIn(self.gifs[0][1], (501, 502))
        self.assertTrue(CLIENT.sent)

    def test_flag_missing_does_nothing(self):
        self.p.settings.update(gifs=True, gif_pct="100")
        CLIENT.SEND_GIF = False
        self.talk()
        self.assertEqual(self.gifs, [])
        self.assertTrue(CLIENT.sent)

    def test_old_app_without_the_call(self):
        self.p.settings.update(gifs=True, gif_pct="100")
        del CLIENT.send_saved_gif
        self.assertEqual(self.p._gif_rows(), [])
        self.talk()
        self.assertTrue(CLIENT.sent)

    def test_rows_only_with_flag(self):
        self.assertEqual([r.key for r in self.p._gif_rows()], ["gifs", "gif_pct"])
        CLIENT.SAVED_GIFS = False
        self.assertEqual(self.p._gif_rows(), [])

    def test_recent_gif_not_repeated(self):
        self.p._gif_hist.append(501)
        self.p.settings.update(gifs=True, gif_pct="100")
        self.talk()
        self.assertEqual([g[1] for g in self.gifs], [502])


class TestConfirm(GifBase):
    def test_two_taps(self):
        calls = []
        cb = self.p._confirm_cb("k", lambda: calls.append(1))
        cb()
        self.assertEqual(calls, [])
        self.assertTrue(CLIENT.bulletins)
        cb()
        self.assertEqual(calls, [1])
        cb()
        self.assertEqual(calls, [1])

    def test_expires(self):
        calls = []
        cb = self.p._confirm_cb("k", lambda: calls.append(1))
        cb()
        self.clock[0] += 10
        cb()
        self.assertEqual(calls, [])

    def test_wording_without_about(self):
        for lang in (1, 2, 3):
            self.assertNotIn("около", mod.tr(lang, "react_mode_2"))


class FakePage(object):
    def __init__(self, key, text=None, subtext=None, icon=None):
        self.key, self.text, self.subtext, self.icon = key, text, subtext, icon


class TestNewsBottom(GifBase):
    def setUp(self):
        super().setUp()
        self._page = getattr(mod, "Page", None)
        mod.Page = FakePage

    def tearDown(self):
        mod.Page = self._page
        super().tearDown()

    def test_news_after_the_pages(self):
        self.p.settings["news_seen"] = ""
        rows = self.p._pg_root({"master": mod.Switch(key="master", text="m")}, None)
        keys = [getattr(r, "key", "") for r in rows]
        self.assertEqual(keys[-1], "pg_news")
