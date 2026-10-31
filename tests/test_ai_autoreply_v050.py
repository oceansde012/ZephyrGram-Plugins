"""0.4.9 tests: emoji reactions (instead of a reply to 'ok / thanks / lol', emoji, stickers; now and then extra).

No real Telegram: the TL request is built from a fake `_jclass` and recorded by a fake client.send_request.
Run: python -m unittest discover -s tests -v
"""
import random
import unittest

from test_ai_autoreply import Base, CLIENT, DID, all_settings, chats_screen, mod

THUMB, HEART, FIRE, GRIN, SAD = u"\U0001F44D", u"❤", u"\U0001F525", u"\U0001F601", u"\U0001F622"


class TlObject(object):
    def __init__(self):
        self.flags = 0
        self.reaction = TlList()


class TlList(list):
    def add(self, x):                       # java.util.ArrayList.add
        self.append(x)


class FakeJava(object):
    """Stands in for chaquopy's jclass: MessagesController, ZephyrConfig and plain TL classes."""

    def __init__(self):
        self.ghost_read = False
        self.updates = []

    def __call__(self, name):
        outer = self
        short = name.split("$")[-1].split(".")[-1]
        if short == "MessagesController":
            class MC(object):
                @staticmethod
                def getInstance(acc):
                    class I(object):
                        @staticmethod
                        def getInputPeer(did):
                            return ("peer", did)

                        @staticmethod
                        def processUpdates(updates, from_queue):
                            outer.updates.append((updates, from_queue))
                    return I
            return MC
        if short == "ZephyrConfig":
            class ZC(object):
                ghostNoRead = outer.ghost_read
                ghostNoTyping = False

                @staticmethod
                def load():
                    pass
            return ZC
        return type(short, (TlObject,), {})


class AlwaysRng(random.Random):
    """A seeded rng whose random() is fixed (the 15% roll of an extra reaction is decided by it)."""

    def __init__(self, value):
        super(AlwaysRng, self).__init__(7)
        self.value = value

    def random(self):
        return self.value


class ReactBase(Base):
    def setUp(self):
        super(ReactBase, self).setUp()
        self.java = FakeJava()
        self._old_jclass = mod._jclass
        mod._jclass = self.java
        self.requests = []
        self.callbacks = []
        self.fail_send = False

        def send_request(req, cb=None, account=None):
            if self.fail_send:
                raise RuntimeError("network down")
            self.requests.append((req, account))
            self.callbacks.append(cb)
            return 1

        CLIENT.send_request = send_request
        self.p.settings.update(stickers=False, cooldown="0", owner_active="0", disclosure=False)
        self.enable()

    def tearDown(self):
        mod._jclass = self._old_jclass
        for a in ("send_request", "send_reaction", "mark_read"):
            if hasattr(CLIENT, a):
                delattr(CLIENT, a)

    def sk(self):
        return self.p._sk(self.key())

    def reactions(self):
        """[(msg_id, emoji)] of the sent messages.sendReaction requests."""
        out = []
        for req, _acc in self.requests:
            if type(req).__name__ == "TL_messages_sendReaction":
                self.assertEqual(req.peer, ("peer", DID))
                self.assertEqual(req.flags & 1, 1)                       # the reaction list is serialized
                self.assertEqual([type(r).__name__ for r in req.reaction], ["TL_reactionEmoji"])
                out.append((req.msg_id, req.reaction[0].emoticon))
        return out

    def say(self, text, mid=None):
        self.clock[0] += 5
        r = self.incoming(text=text, mid=mid)
        self.fire_timers()
        return r

    def log(self):
        return self.p.decisions_text()


class TestPickReaction(unittest.TestCase):
    def test_rules(self):
        cases = {u"дякую": HEART, u"Спасибо!": HEART, u"thx": HEART, u"ок": THUMB, u"ага": THUMB, u"добре": THUMB,
                 u"хахаха": GRIN, u"лол": GRIN, u"сумно": SAD, u"\U0001F602": GRIN, u"❤️": HEART,
                 u"\U0001F44D\U0001F3FB": THUMB, FIRE + FIRE: FIRE, u"\U0001F431": THUMB, u"ну таке": THUMB,
                 u"сумка": THUMB, u"сумніваюсь": THUMB, u"ок " + FIRE: THUMB, u"круто " + FIRE: FIRE}
        for text, emoji in cases.items():
            self.assertEqual(mod.pick_reaction(text), emoji, text)
        self.assertEqual(mod.pick_reaction("[incoming sticker 5]", sticker=True), THUMB)

    def test_only_the_safe_set(self):
        for text in (u"дякую", u"\U0001F602", u"\U0001F431", u"сумно", u"lol", u"\U0001F97A", "x"):
            self.assertIn(mod.pick_reaction(text), mod.REACT_SET)
        self.assertEqual(len(mod.REACT_SET), 9)

    def test_reactable(self):
        for text in (u"дякую", u"ок", u"хаха", u"\U0001F602", u"❤️"):
            self.assertTrue(mod.reactable(text), text)
        for text in (u"як справи?", u"...", u"ок, а коли ти будеш вдома", u"сумно"):
            self.assertFalse(mod.reactable(text), text)


class TestReactionInstead(ReactBase):
    def setUp(self):
        super(TestReactionInstead, self).setUp()
        self.p.settings["reactions"] = 1

    def test_thanks_gets_a_heart_and_no_text(self):
        self.say(u"дякую", mid=501)
        self.assertEqual(self.reactions(), [(501, HEART)])
        self.assertEqual(CLIENT.sent + CLIENT.ai_calls, [])
        self.assertIn("reaction_sent", self.log())
        self.assertIn(501, self.p._state(self.key()).answered)
        rec = [r for r in self.p._decisions if r["r"] == "reaction_sent"][-1]
        self.assertEqual((rec["o"], rec.get("x")), ("sent", HEART))
        self.assertTrue(self.p.decision_sentence(rec).endswith(HEART))
        self.callbacks[-1]("UPDATES", None)                              # the answer feeds the app's updates
        self.assertEqual(self.java.updates, [("UPDATES", False)])
        self.callbacks[-1](None, "ERR")
        self.assertEqual(len(self.java.updates), 1)

    def test_emoji_is_mirrored(self):
        self.say(FIRE, mid=601)
        self.clock[0] += 60
        self.say(u"\U0001F602", mid=602)
        self.assertEqual(self.reactions(), [(601, FIRE), (602, GRIN)])
        self.assertEqual(CLIENT.sent + CLIENT.ai_calls, [])

    def test_regular_message_is_answered_as_before(self):
        self.say(u"як справи, що робиш?", mid=700)
        self.assertEqual(self.reactions(), [])                           # mode 1: no extra reactions
        self.assertEqual(len(CLIENT.sent), 1)

    def test_off_by_default(self):
        self.p.settings.pop("reactions")
        self.say(u"дякую", mid=502)
        self.assertEqual(self.reactions(), [])
        self.assertIn("acknowledgement", self.log())
        self.assertNotIn("reaction", self.log())

    def test_not_in_groups(self):
        CLIENT.info = {"id": -500, "title": "G", "type": "group", "is_bot": False, "username": ""}
        self.enable(did=-500)
        gkey = self.p.chat_key(0, -500)
        self.clock[0] += 5
        self.p.handle_incoming(0, self.msg(text=u"дякую", did=-500, mid=900))
        self.fire_timers()
        self.assertEqual(self.reactions(), [])
        self.assertEqual(self.p._react_mode(gkey, self.p._chats[gkey], -500), 0)
        self.p.settings["react_" + self.p._sk(gkey)] = 2                 # not even when turned on for the chat
        self.assertEqual(self.p._react_mode(gkey, self.p._chats[gkey], -500), 0)

    def test_not_in_draft_or_friend_mode(self):
        for mode in (mod.MODE_DRAFT, mod.MODE_COMMAND):
            self.p.settings["mode_" + self.sk()] = mode
            self.say(u"дякую")
            self.clock[0] += 60
        self.assertEqual(self.reactions(), [])

    def test_not_when_the_chat_or_master_is_off(self):
        self.p.settings["master"] = False
        self.say(u"дякую")
        self.p.settings["master"] = True
        self.p.on_disable_click({"account": 0, "dialog_id": DID})
        self.say(u"дякую")
        self.assertEqual(self.reactions(), [])

    def test_per_chat_selector(self):
        self.p.settings["react_" + self.sk()] = 1                        # off here
        self.say(u"дякую")
        self.assertEqual(self.reactions(), [])
        self.p.settings["reactions"] = 0
        self.p.settings["react_" + self.sk()] = 2                        # on here only
        self.clock[0] += 60
        self.say(u"ок", mid=801)
        self.assertEqual(self.reactions(), [(801, THUMB)])

    def test_owner_activity_keeps_the_old_path(self):
        self.p.settings["owner_active"] = "60"
        self.p._state(self.key()).owner_ts = self.clock[0]
        self.say(u"дякую")
        self.assertEqual(self.reactions(), [])

    def test_quiet_hours(self):
        self.p.settings["quiet_hours"] = "00:01-00:00"                  # all day but one minute
        self.say(u"дякую")
        self.assertEqual(self.reactions(), [])
        self.assertIn("quiet_hours", self.log())

    def test_ghost_mode_hides_reading_so_no_reaction(self):
        self.java.ghost_read = True
        self.say(u"дякую")
        self.assertEqual(self.reactions(), [])
        self.assertIn("reaction_skipped_ghost", self.log())

    def test_helper_of_a_newer_app_is_preferred(self):
        calls = []
        CLIENT.send_reaction = lambda did, mid, emoji, account=None: calls.append((did, mid, emoji, account)) or True
        self.say(u"дякую", mid=503)
        self.assertEqual(calls, [(DID, 503, HEART, 0)])
        self.assertEqual(self.reactions(), [])

    def test_failed_request_falls_back_and_keeps_the_chat_on(self):
        self.fail_send = True
        self.say(u"дякую")
        self.assertIn("reaction_skipped_error", self.log())
        self.assertIn("acknowledgement", self.log())                     # handled as without reactions
        self.assertTrue(self.p.is_enabled(self.key()))
        self.assertEqual(int(self.p._chats[self.key()].get("fails", 0) or 0), 0)
        self.p.settings["skip_ack"] = False                              # an answered 'thanks' still gets its text
        self.clock[0] += 60
        self.say(u"дякую")
        self.assertEqual(len(CLIENT.sent), 1)

    def test_unavailable_java_never_breaks_anything(self):
        mod._jclass = self._old_jclass                                   # the real one: no `java` module here
        self.say(u"дякую")
        self.assertIn("reaction_skipped_error", self.log())
        self.assertTrue(self.p.is_enabled(self.key()))
        self.assertEqual(self.p.errors, [])


class TestLimits(ReactBase):
    def test_hourly_cap_per_chat(self):
        st = self.p._state(self.key())
        for i in range(mod.REACT_CHAT_HOURLY):
            self.clock[0] += 1
            self.assertTrue(self.p._put_reaction(self.key(), st, DID, 0, 100 + i, THUMB))
        self.assertIsNone(self.p._put_reaction(self.key(), st, DID, 0, 200, THUMB))
        self.assertIn("reaction_skipped_hour_cap", self.log())
        self.assertEqual(len(self.reactions()), mod.REACT_CHAT_HOURLY)
        self.clock[0] += 3601
        self.assertTrue(self.p._put_reaction(self.key(), st, DID, 0, 201, THUMB))

    def test_daily_cap_in_all_chats(self):
        self.p.settings["reactions"] = 1
        for i in range(mod.REACT_DAILY):
            self.p._react_day.append(self.clock[0] - 3600 * 5 + i)
        self.say(u"дякую")
        self.assertEqual(self.reactions(), [])
        self.assertIn("reaction_skipped_day_cap", self.log())
        self.assertIn("acknowledgement", self.log())
        self.clock[0] += 86400
        self.say(u"дякую", mid=999)
        self.assertEqual(self.reactions(), [(999, HEART)])

    def test_limits_are_small(self):
        self.assertLessEqual(mod.REACT_CHAT_HOURLY, 12)
        self.assertLessEqual(mod.REACT_DAILY, 60)


class TestExtraReactions(ReactBase):
    def setUp(self):
        super(TestExtraReactions, self).setUp()
        self.p.settings["reactions"] = 2
        self.p._rng = AlwaysRng(0.01)                                   # every roll under 15%

    def test_sometimes_a_reaction_on_an_answered_message(self):
        self.say(u"як справи, що робиш", mid=310)
        self.assertEqual(len(CLIENT.sent), 1)
        self.assertEqual(self.reactions(), [(310, THUMB)])

    def test_no_roll_no_reaction(self):
        self.p._rng = AlwaysRng(0.5)
        self.say(u"як справи, що робиш", mid=311)
        self.assertEqual(len(CLIENT.sent), 1)
        self.assertEqual(self.reactions(), [])
        self.assertNotIn("reaction", self.log())

    def test_pause_between_reactions(self):
        self.say(u"як справи, що робиш", mid=320)
        self.clock[0] += 60
        self.say(u"а ти де зараз", mid=321)
        self.assertEqual(len(CLIENT.sent), 2)
        self.assertEqual(self.reactions(), [(320, THUMB)])
        self.assertIn("reaction_skipped_gap", self.log())
        self.clock[0] += mod.REACT_EXTRA_GAP_MIN * 60
        self.say(u"сумно якось сьогодні", mid=322)
        self.assertEqual(self.reactions(), [(320, THUMB), (322, SAD)])

    def test_not_on_links(self):
        self.p.settings["skip_links"] = False
        self.say(u"глянь https://example.com", mid=330)
        self.assertEqual(len(CLIENT.sent), 1)
        self.assertEqual(self.reactions(), [])
        self.assertIn("reaction_skipped_link", self.log())

    def test_instead_still_works_in_mode_two(self):
        self.say(u"дякую", mid=340)
        self.assertEqual(self.reactions(), [(340, HEART)])
        self.assertEqual(CLIENT.sent, [])

    def test_failed_extra_reaction_never_breaks_the_reply(self):
        self.fail_send = True
        self.say(u"як справи, що робиш", mid=350)
        self.assertEqual(len(CLIENT.sent), 1)
        self.assertIn("reaction_skipped_error", self.log())
        self.assertTrue(self.p.is_enabled(self.key()))
        self.assertEqual(int(self.p._chats[self.key()].get("fails", 0) or 0), 0)

    def test_not_in_draft_mode(self):
        self.p.settings["mode_" + self.sk()] = mod.MODE_DRAFT
        self.say(u"як справи, що робиш", mid=360)
        self.assertEqual(len(CLIENT.drafts), 1)
        self.assertEqual(self.reactions(), [])


class TestLiveTiming(ReactBase):
    def setUp(self):
        super(TestLiveTiming, self).setUp()
        self.p.settings["preset"] = 3                                    # Live: human pauses
        self.p.settings["reactions"] = 1
        self.events, self.sleeps = [], []
        mod.time.sleep = lambda s: self.sleeps.append(s)
        CLIENT.mark_read = lambda did, max_id, account=None: self.events.append(("read", max_id))
        CLIENT.set_typing = lambda did, account=None, cancel=False: self.events.append(("typing", did))
        inner = CLIENT.send_request

        def send_request(req, cb=None, account=None):
            self.events.append(("react", req.msg_id))
            return inner(req, cb, account)
        CLIENT.send_request = send_request

    def tearDown(self):
        if hasattr(CLIENT, "set_typing"):
            delattr(CLIENT, "set_typing")
        super(TestLiveTiming, self).tearDown()

    def test_human_pause_then_read_then_reaction_without_typing(self):
        self.say(u"дякую", mid=410)
        self.assertEqual(self.events, [("read", 410), ("react", 410)])
        self.assertGreater(sum(self.sleeps), 0.4)
        self.assertEqual(CLIENT.sent, [])

    def test_owner_reply_during_the_pause_cancels(self):
        orig = mod.time.sleep

        def sleep(s):
            self.p._state(self.key()).owner_ts = self.clock[0] + 100
        mod.time.sleep = sleep
        try:
            self.say(u"дякую", mid=411)
        finally:
            mod.time.sleep = orig
        self.assertEqual([e for e in self.events if e[0] == "react"], [])


class TestStickerOnly(ReactBase):
    def test_sticker_gets_a_reaction_instead_of_a_sticker(self):
        self.p.settings["reactions"] = 1
        self.p._is_sticker_document = lambda doc: True
        self.p._memory_owner_id = lambda account: 1
        sent = []
        self.p._queue_sticker_document = lambda *a, **kw: sent.append(a) or True
        m = self.msg(text="", mid=77)
        m.update(has_media=True, is_sticker=True, _sticker_document=object())
        self.clock[0] += 5
        self.p._handle_dict(0, DID, m)
        self.fire_timers()
        self.assertEqual(self.reactions(), [(77, THUMB)])
        self.assertEqual(sent + CLIENT.sent, [])


class TestReactionSettings(ReactBase):
    def test_main_section_has_the_general_selector(self):
        rows = {getattr(i, "key", None): i for i in self.p.create_settings()}
        self.assertEqual((type(rows["reactions"]).__name__, rows["reactions"].default, len(rows["reactions"].items)),
                         ("Selector", 0, 3))
        for lang in (1, 2, 3):
            self.p.settings["ui_lang"] = lang
            rows = {getattr(i, "key", None): i for i in self.p.create_settings()}
            for text in rows["reactions"].items + [rows["reactions"].text, rows["reactions"].subtext]:
                self.assertNotIn(text, mod.S)
        self.p.settings["ui_lang"] = 2
        rows = {getattr(i, "key", None): i for i in self.p.create_settings()}
        self.assertEqual(rows["reactions"].items[0], "Выкл.")

    def test_chat_options_have_the_per_chat_selector_and_remove_clears_it(self):
        self.p._open_key = self.key()
        rows = {getattr(i, "key", None): i for i in chats_screen(self.p)}
        sel = rows["react_" + self.sk()]
        self.assertEqual((sel.default, len(sel.items)), (0, 3))
        self.assertEqual(sum(1 for i in all_settings(self.p) if getattr(i, "key", None) == "reactions"), 1)
        self.p.settings["react_" + self.sk()] = 2
        rows["remove_" + self.sk()].on_click()
        self.assertIsNone(self.p.settings.get("react_" + self.sk()))

    def test_reasons_have_texts_in_three_languages(self):
        for code in ("reaction_sent", "reaction_skipped_hour_cap", "reaction_skipped_day_cap",
                     "reaction_skipped_ghost", "reaction_skipped_error", "reaction_skipped_link",
                     "reaction_skipped_gap"):
            row = mod.R[code]
            self.assertEqual(len(row), 3)
            self.assertTrue(all(row))


if __name__ == "__main__":
    unittest.main()
