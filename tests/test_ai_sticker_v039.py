"""Mandatory sticker replies: deterministic selection and scoped native fallback; no real Telegram/network."""
import sys
import types
from unittest.mock import patch

from test_ai_autoreply import Base, CLIENT, DID, mod


class Sticker:
    def __init__(self, ident=991):
        self.id = ident


class TestMandatoryStickerReply(Base):
    def setUp(self):
        super().setUp()
        self.enable()
        self.p.settings.update(humanize=False, disclosure=False, typing_delay=False,
                               owner_active="0", cooldown="0", stickers=False, sticker_pct="0")
        self.native, self.stickers, self.lookups = [], [], []
        self.originals = {name: getattr(CLIENT, name, None) for name in
                          ("get_recent_stickers", "send_sticker", "get_recent_messages")}
        self.original_jclass = mod._jclass
        CLIENT.get_recent_stickers = lambda limit=30, account=None: []
        CLIENT.send_sticker = lambda did, sid, account=None, reply_to=None: self.stickers.append((did, sid, account, reply_to)) or True
        self.p._is_sticker_document = lambda doc: isinstance(doc, Sticker)
        self.owner_ids = {0: 123}
        self.p._memory_owner_id = lambda account: self.owner_ids.get(int(account))
        self.p._cached_sticker_document = lambda account, did, mid: self.lookups.append((account, did, mid)) or None
        self.p._queue_sticker_document = lambda key, st, did, account, doc, parent=None: self.native.append((key, did, account, doc.id)) or True

    def tearDown(self):
        for name, value in self.originals.items():
            if value is None:
                if hasattr(CLIENT, name):
                    delattr(CLIENT, name)
            else:
                setattr(CLIENT, name, value)
        mod._jclass = self.original_jclass

    def incoming_sticker(self, mid=33, document=None, **extra):
        m = self.msg(text="", mid=mid)
        m.update(has_media=True, is_sticker=True, _sticker_document=document or Sticker(mid + 1000))
        m.update(extra)
        return self.p._handle_dict(int(m.get("account", 0)), int(m.get("dialog_id", DID)), m)

    def test_no_recent_stickers_uses_incoming_document_without_ai_or_text(self):
        self.incoming_sticker()
        self.fire_timers()
        self.assertEqual(self.native, [(self.key(), DID, 0, 1033)])
        self.assertEqual(CLIENT.ai_calls + CLIENT.sent + CLIENT.drafts, [])
        self.assertIn(33, self.p._state(self.key()).answered)

    def test_probability_zero_and_ai_decline_do_not_suppress_sticker(self):
        CLIENT.get_recent_stickers = lambda **kw: [{"id": 100, "emoji": "🙂", "set_title": "recent"}]
        CLIENT.ai_result = lambda *a, **kw: '{"use_sticker":false,"index":0}'
        self.p.settings.update(skip_emoji=True, skip_ack=True, ack_reply_pct="0")
        self.incoming_sticker()
        self.fire_timers()
        self.assertEqual(self.stickers, [(DID, 100, 0, None)])
        self.assertEqual(CLIENT.ai_calls + CLIENT.sent, [])
        self.assertEqual(self.native, [])

    def test_repeated_recent_candidate_still_selected(self):
        CLIENT.get_recent_stickers = lambda **kw: [{"id": 100}]
        self.p._state(self.key()).last_sticker = (100, "old")
        self.p._sticker_hist.append(100)
        self.incoming_sticker()
        self.fire_timers()
        self.assertEqual(len(self.stickers), 1)
        self.assertEqual(CLIENT.ai_calls + CLIENT.sent, [])

    def test_failed_recent_candidate_falls_back_to_original(self):
        CLIENT.get_recent_stickers = lambda **kw: [{"id": 100}]
        CLIENT.send_sticker = lambda *a, **kw: False
        self.incoming_sticker()
        self.fire_timers()
        self.assertEqual(self.native[0][-1], 1033)
        self.assertEqual(CLIENT.sent, [])

    def test_all_sticker_batch_replies_once_not_once_per_sticker(self):
        self.incoming_sticker(33)
        self.incoming_sticker(34)
        self.fire_timers()
        self.assertEqual(len(self.native), 1)
        self.assertEqual(self.native[0][-1], 1034)
        self.assertTrue({33, 34}.issubset(set(self.p._state(self.key()).answered)))
        self.assertEqual(CLIENT.ai_calls + CLIENT.sent, [])

    def test_mixed_text_and_sticker_uses_normal_text_path(self):
        self.incoming_sticker()
        self.incoming(text="як справи?", mid=34)
        self.fire_timers()
        self.assertEqual(self.native + self.stickers, [])
        self.assertTrue(CLIENT.ai_calls)
        self.assertTrue(CLIENT.sent)

    def test_captioned_sticker_uses_normal_text_path(self):
        self.incoming_sticker(text="поясни цей стікер")
        self.fire_timers()
        self.assertEqual(self.native, [])
        self.assertTrue(CLIENT.ai_calls)

    def test_blank_photo_or_video_is_not_classified_as_sticker(self):
        m = self.msg(text="", mid=33)
        m.update(has_media=True, mime="video/webm")
        result = self.p._prepare_sticker_message(self.key(), m)
        self.assertNotIn("is_sticker", result)
        self.assertFalse(self.p._sticker_only_batch(self.key(), [(33, 7, "")]))
        self.assertEqual(self.lookups, [])

    def test_nonsticker_event_does_not_query_database_on_network_hook(self):
        mo = types.SimpleNamespace(
            currentAccount=0, getDialogId=lambda: DID, isSticker=lambda: False,
            isAnimatedSticker=lambda: False, isVideoSticker=lambda: False)
        m = self.msg(text="", mid=33)
        m.update(has_media=True)
        m = self.p._sticker_event(0, DID, mo, m)
        self.p._handle_dict(0, DID, m)
        self.assertEqual(self.lookups, [])

    def test_scan_classifies_only_exact_locally_cached_sticker(self):
        def lookup(account, did, mid):
            self.lookups.append((account, did, mid))
            return Sticker(998) if (account, did, mid) == (0, DID, 33) else None
        self.p._cached_sticker_document = lookup
        m = self.msg(text="", mid=33)
        m.update(has_media=True)
        self.p._handle_dict(0, DID, m, via_scan=True)
        self.fire_timers()
        self.assertEqual(self.lookups, [(0, DID, 33)])
        self.assertEqual(self.native[0][-1], 998)

    def test_event_uses_raw_message_not_localized_sticker_display_label(self):
        document = Sticker()
        mo = types.SimpleNamespace(
            currentAccount=0, getDialogId=lambda: DID, isSticker=lambda: True,
            isAnimatedSticker=lambda: False, isVideoSticker=lambda: False,
            getDocument=lambda: document, messageText="🙂 Стикер",
            messageOwner=types.SimpleNamespace(message=""))
        m = self.msg(text="🙂 Стикер", mid=33)
        m = self.p._sticker_event(0, DID, mo, m)
        self.assertEqual(m["text"], "")
        self.assertIs(m["_sticker_parent"], mo)
        self.p._handle_dict(0, DID, m)
        self.fire_timers()
        self.assertEqual(len(self.native), 1)
        self.assertEqual(CLIENT.ai_calls + CLIENT.sent, [])

    def test_disabled_master_and_chat_do_not_send(self):
        self.p.settings["master"] = False
        self.incoming_sticker()
        self.fire_timers()
        self.assertEqual(self.native + self.stickers + CLIENT.sent, [])
        self.p.settings["master"] = True
        self.p.chat_off(self.key(), remove=False)
        self.incoming_sticker(34)
        self.fire_timers()
        self.assertEqual(self.native + self.stickers + CLIENT.sent, [])

    def test_explicit_draft_and_command_modes_do_not_auto_send(self):
        for mode in (mod.MODE_DRAFT, mod.MODE_COMMAND):
            self.p.settings["mode_" + self.p._sk(self.key())] = mode
            self.incoming_sticker(33 + mode)
            self.fire_timers()
        self.assertEqual(self.native + self.stickers + CLIENT.sent + CLIENT.drafts, [])

    def test_group_question_gate_does_not_drop_sticker_only(self):
        self.p._chats[self.key()]["type"] = "group"
        self.p.settings["group_need_question"] = True
        self.incoming_sticker()
        self.fire_timers()
        self.assertEqual(len(self.native), 1)
        self.assertEqual(CLIENT.sent, [])

    def test_cancellation_after_candidate_lookup_discards_late_result(self):
        def recent(**kw):
            self.p.on_app_event("settings_changed")
            return [{"id": 100}]
        CLIENT.get_recent_stickers = recent
        self.incoming_sticker()
        self.fire_timers()
        self.assertEqual(self.native + self.stickers + CLIENT.sent, [])

    def test_settings_change_before_debounce_does_not_fall_back_to_plain_text(self):
        self.incoming_sticker()
        self.p.on_app_event("settings_changed")
        self.fire_timers()
        self.assertEqual(self.native + self.stickers + CLIENT.sent + CLIENT.ai_calls, [])

    def test_account_owner_change_before_debounce_never_uses_old_sticker(self):
        self.incoming_sticker()
        self.owner_ids[0] = 456
        self.fire_timers()
        self.assertEqual(self.native + self.stickers + CLIENT.sent + CLIENT.ai_calls, [])

    def test_unknown_owner_never_queues_sticker_or_falls_back_to_text(self):
        self.owner_ids[0] = None
        self.incoming_sticker()
        self.fire_timers()
        self.assertEqual(self.native + self.stickers + CLIENT.sent + CLIENT.ai_calls, [])

    def test_account_slot_reuse_during_recent_lookup_cancels_send(self):
        def recent(**kw):
            self.owner_ids[0] = 456
            return [{"id": 100}]
        CLIENT.get_recent_stickers = recent
        self.incoming_sticker()
        self.fire_timers()
        self.assertEqual(self.native + self.stickers + CLIENT.sent, [])

    def test_cross_account_payload_is_not_registered(self):
        m = self.msg(text="", mid=33)
        m.update(has_media=True, is_sticker=True, account=2, _sticker_document=Sticker())
        self.p._prepare_sticker_message(self.key(), m)
        self.assertFalse(self.p._sticker_only_batch(self.key(), [(33, 7, "")]))
        self.assertEqual(self.lookups, [])

    def test_native_fallback_queues_same_outbox_path_and_rechecks_epoch(self):
        sent, skipped, params_args = [], [], []
        params = object()
        classes = {
            "org.telegram.messenger.SendMessagesHelper$SendMessageParams": types.SimpleNamespace(of=lambda *args: params_args.append(args) or params),
            "org.telegram.messenger.SendMessagesHelper": types.SimpleNamespace(getInstance=lambda account: types.SimpleNamespace(sendMessage=lambda value: sent.append((account, value)))),
            "org.telegram.messenger.zephyr.plugins.PluginHooks": types.SimpleNamespace(skipHooks=lambda value: skipped.append(value))}
        mod._jclass = lambda name: classes[name]
        st = self.p._state(self.key())
        self.assertTrue(mod.Plugin._queue_sticker_document(self.p, self.key(), st, DID, 0, Sticker()))
        self.assertEqual(params_args[0][3], DID)
        self.assertEqual(skipped, [params])
        self.p.on_app_event("settings_changed")
        self.fire_timers()
        self.assertEqual(sent, [])

    def test_native_queue_success_keeps_account_and_parent_reference(self):
        sent, args_seen = [], []
        params, parent = object(), object()
        classes = {
            "org.telegram.messenger.SendMessagesHelper$SendMessageParams": types.SimpleNamespace(of=lambda *args: args_seen.append(args) or params),
            "org.telegram.messenger.SendMessagesHelper": types.SimpleNamespace(getInstance=lambda account: types.SimpleNamespace(sendMessage=lambda value: sent.append((account, value)))),
            "org.telegram.messenger.zephyr.plugins.PluginHooks": types.SimpleNamespace(skipHooks=lambda value: None)}
        mod._jclass = lambda name: classes[name]
        st = self.p._state(self.key())
        self.assertTrue(mod.Plugin._queue_sticker_document(self.p, self.key(), st, DID, 0, Sticker(), parent=parent))
        self.fire_timers()
        self.assertEqual(sent, [(0, params)])
        self.assertIs(args_seen[0][14], parent)

    def test_native_ui_queue_rejects_reused_account_slot_without_epoch_change(self):
        sent = []
        classes = {
            "org.telegram.messenger.SendMessagesHelper$SendMessageParams": types.SimpleNamespace(of=lambda *args: object()),
            "org.telegram.messenger.SendMessagesHelper": types.SimpleNamespace(getInstance=lambda account: types.SimpleNamespace(sendMessage=lambda value: sent.append(value))),
            "org.telegram.messenger.zephyr.plugins.PluginHooks": types.SimpleNamespace(skipHooks=lambda value: None)}
        mod._jclass = lambda name: classes[name]
        st = self.p._state(self.key())
        self.assertTrue(mod.Plugin._queue_sticker_document(self.p, self.key(), st, DID, 0, Sticker()))
        self.owner_ids[0] = 456
        self.fire_timers()
        self.assertEqual(sent, [])

    def test_native_local_cache_lookup_never_borrows_another_account_message(self):
        document = Sticker()
        mo = types.SimpleNamespace(currentAccount=1, getDialogId=lambda: DID, getId=lambda: 33, getDocument=lambda: document)
        array = types.SimpleNamespace(size=lambda: 1, get=lambda i: mo)
        mc = types.SimpleNamespace(dialogMessage=types.SimpleNamespace(get=lambda did: array))
        classes = {"org.telegram.messenger.MessagesController": types.SimpleNamespace(getInstance=lambda account: mc),
                   "android.os.Looper": types.SimpleNamespace(myLooper=lambda: 1, getMainLooper=lambda: 1)}
        mod._jclass = lambda name: classes[name]
        self.assertIsNone(mod.Plugin._cached_sticker_document(self.p, 0, DID, 33))
        mo.currentAccount = 0
        self.assertIs(mod.Plugin._cached_sticker_document(self.p, 0, DID, 33), document)

    def test_scan_storage_lookup_reads_exact_scoped_row_and_releases_resources(self):
        document, query, cleanup = Sticker(), [], []
        raw_message = types.SimpleNamespace(out=False)
        data = types.SimpleNamespace(readInt32=lambda exception: 123, reuse=lambda: cleanup.append("buffer"))
        cursor = types.SimpleNamespace(next=lambda: True, byteBufferValue=lambda col: data,
                                       dispose=lambda: cleanup.append("cursor"))
        database = types.SimpleNamespace(queryFinalized=lambda sql: query.append(sql) or cursor)
        storage = types.SimpleNamespace(getDatabase=lambda: database,
                                       getStorageQueue=lambda: types.SimpleNamespace(postRunnable=lambda task: task.run()))
        class Latch:
            def __init__(self, count):
                self.done = False
            def countDown(self):
                self.done = True
            def __getattr__(self, name):
                if name == "await":
                    return lambda timeout, unit: self.done
                raise AttributeError(name)
        classes = {
            "org.telegram.messenger.MessagesController": types.SimpleNamespace(getInstance=lambda account: types.SimpleNamespace(dialogMessage=types.SimpleNamespace(get=lambda did: None))),
            "android.os.Looper": types.SimpleNamespace(myLooper=lambda: 1, getMainLooper=lambda: 2),
            "java.lang.Runnable": object,
            "java.util.concurrent.CountDownLatch": Latch,
            "java.util.concurrent.TimeUnit": types.SimpleNamespace(SECONDS=1),
            "org.telegram.messenger.MessagesStorage": types.SimpleNamespace(getInstance=lambda account: storage),
            "org.telegram.tgnet.TLRPC$Message": types.SimpleNamespace(TLdeserialize=lambda *args: raw_message),
            "org.telegram.messenger.MessageObject": types.SimpleNamespace(getDocument=lambda message: document)}
        mod._jclass = lambda name: classes[name]
        java = types.ModuleType("java")
        java.dynamic_proxy = lambda interface: object
        with patch.dict(sys.modules, {"java": java}):
            found = mod.Plugin._cached_sticker_document(self.p, 0, DID, 33)
        self.assertIs(found, document)
        self.assertEqual(query, ["SELECT data FROM messages_v2 WHERE uid = 42 AND mid = 33"])
        self.assertEqual(cleanup, ["buffer", "cursor"])

    def test_no_available_sender_reports_failure_and_never_generates_text(self):
        self.p._queue_sticker_document = lambda *args, **kwargs: False
        self.incoming_sticker()
        self.fire_timers()
        self.assertEqual(CLIENT.sent + CLIENT.ai_calls, [])
        self.assertNotIn(33, self.p._state(self.key()).answered)
        self.assertIn("sticker_reply_unavailable", [d["r"] for d in self.p._decisions])

    def test_chat_rate_cap_never_substitutes_polite_plain_text(self):
        self.p.settings["chat_hourly"] = "1"
        self.p.settings["polite_stop"] = True
        self.p._state(self.key()).sent_h.append(self.clock[0])
        self.incoming_sticker()
        self.fire_timers()
        self.assertEqual(self.native + self.stickers + CLIENT.sent + CLIENT.ai_calls, [])
