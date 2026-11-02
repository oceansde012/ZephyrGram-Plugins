import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
import zipfile

_client = types.SimpleNamespace(run_in_bg=lambda fn: fn(), run_on_ui=lambda fn, **kw: None, bulletin=lambda text: None)
_zephyr = types.ModuleType('zephyr')
_zephyr.BasePlugin = type('BasePlugin', (), {})
_zephyr.MenuItem = lambda *a, **kw: (a, kw)
_zephyr.MenuType = types.SimpleNamespace(CHAT_ACTION='chat')
_zephyr.client = _client
_ui = types.ModuleType('zephyr.ui')
for name in ('Header', 'Text', 'Divider'):
    setattr(_ui, name, lambda *a, **kw: types.SimpleNamespace())
_saved = {key: sys.modules.get(key) for key in ('zephyr', 'zephyr.ui')}
sys.modules.update({'zephyr': _zephyr, 'zephyr.ui': _ui})
_path = Path(__file__).resolve().parents[1] / 'plugins/chat_history_export/chat_history_export.plugin'
_loader = importlib.machinery.SourceFileLoader('chat_history_export_tests_module', str(_path))
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
mod = importlib.util.module_from_spec(_spec)
_loader.exec_module(mod)
for key, value in _saved.items():
    if value is None:
        sys.modules.pop(key, None)
    else:
        sys.modules[key] = value


def message(mid, text='Текст', topic=0):
    return types.SimpleNamespace(id=mid, date=mid * 100, message=text, from_id=types.SimpleNamespace(user_id=42),
        reply_to=types.SimpleNamespace(reply_to_top_id=topic, reply_to_msg_id=topic, forum_topic=bool(topic)),
        media=None, action=None)


def response(messages=(), topics=(), count=0, create_order=False):
    return types.SimpleNamespace(messages=list(messages), topics=list(topics), count=count, order_by_create_date=create_order)


class ExportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.plugin = types.SimpleNamespace(data_dir=self.temp.name, _active=True, _status='', _last_file='',
            _notice=lambda text: None, set_setting=lambda *args: None)
        self.peer = types.SimpleNamespace(channel_id=3946151263, access_hash=999999)

    def session(self):
        value = mod.Session(self.plugin, {'account': 0, 'dialog_id': -3946151263}, {'title': 'Рабочая группа'}, self.peer, True, 42)
        value.valid = lambda: not value.stopped
        value.scheduled = []
        value.schedule = lambda fn, seconds=0.6: value.scheduled.append(seconds)
        return value

    def read_archive(self):
        with zipfile.ZipFile(self.plugin._last_file) as archive:
            self.assertEqual(set(archive.namelist()), {'result.json', 'manifest.json', 'history.txt'})
            return json.loads(archive.read('result.json')), json.loads(archive.read('manifest.json')), archive.read('history.txt').decode()

    def test_unicode_text_and_replies_are_preserved_without_access_credentials(self):
        msg = message(9, 'Помилка: привіт 🙂', 3)
        msg.media = types.SimpleNamespace(document=types.SimpleNamespace(mime_type='text/plain', size=12,
            access_hash='NEVER_EXPORT', file_reference='NEVER_EXPORT', attributes=[types.SimpleNamespace(file_name='example.txt')]))
        record = mod.message_record(msg)
        self.assertEqual(record['topic_id'], 3)
        self.assertEqual(record['reply_to_message_id'], 3)
        self.assertEqual(record['attachment']['file_name'], 'example.txt')
        self.assertNotIn('NEVER_EXPORT', json.dumps(record))

    def test_forum_root_and_direct_topic_reply_are_identified(self):
        msg = message(12)
        msg.action = type('TL_messageActionTopicCreate', (), {'title': 'Ошибки'})()
        self.assertEqual(mod.message_record(msg)['topic_id'], 12)
        msg.action = None
        msg.reply_to = types.SimpleNamespace(forum_topic=True, reply_to_msg_id=7)
        self.assertEqual(mod.message_record(msg)['topic_id'], 7)

    def test_duplicates_across_history_and_topic_pages_are_removed(self):
        s = self.session()
        s.archive.add([mod.message_record(message(10)), mod.message_record(message(10), 7), mod.message_record(message(11, 'Другой текст', 7))])
        s.archive.add_topics([{'id': 7, 'title': 'Ошибки'}])
        s.finish(True, 'done')
        data, manifest, text = self.read_archive()
        self.assertEqual(len(data['messages']), 2)
        self.assertEqual(data['messages'][0]['topic_id'], 7)
        self.assertEqual(manifest['message_count'], 2)
        self.assertTrue(manifest['complete'])
        self.assertIn('Другой текст', text)
        self.assertEqual(data['bot_api_chat_id'], -1003946151263)

    def test_short_history_page_is_not_silently_treated_as_full_history(self):
        s = self.session()
        s.process(response([message(100), message(80)]), None)
        self.assertFalse(s.stopped)
        self.assertEqual(s.offset, 80)
        self.assertEqual(s.stage, 'history')
        s.process(response([]), None)
        self.assertEqual(s.stage, 'topics')
        s.finish(False, 'test cleanup')

    def test_short_topic_page_keeps_pagination_and_requests_each_topic(self):
        s = self.session()
        s.snapshot = 100
        s.stage = 'topics'
        topic = types.SimpleNamespace(id=7, title='Первая', date=1, top_message=80)
        s.process(response([message(80)], [topic], count=3), None)
        self.assertEqual(s.stage, 'topics')
        self.assertEqual(s.topic_offsets, (8000,80,7))
        s.process(response([], [types.SimpleNamespace(id=8,title='Вторая',date=2,top_message=90)], count=3, create_order=True), None)
        self.assertEqual(s.topic_offsets, (2,90,8))
        s.process(response([], [], count=3), None)
        self.assertEqual(s.stage, 'replies')
        self.assertEqual(s.reply_ids, [7,8])
        s.finish(False, 'test cleanup')

    def test_topic_root_does_not_cause_infinite_pagination(self):
        s = self.session()
        s.stage = 'replies'
        s.reply_ids = [7]
        s.snapshot = 100
        s.process(response([message(9,topic=7), message(7,topic=7)]), None)
        self.assertEqual(s.offset, 9)
        s.process(response([message(7,topic=7)]), None)
        self.assertTrue(s.stopped)
        data, manifest, _ = self.read_archive()
        self.assertTrue(manifest['complete'])
        self.assertEqual(len(data['messages']), 2)

    def test_stalled_cursor_and_timeout_create_explicit_partial_archive(self):
        for error in ('REQUEST_TIMEOUT', None):
            s = self.session()
            s.offset = 10
            s.process(response([message(10)]), error)
            self.assertTrue(s.stopped)
            _, manifest, text = self.read_archive()
            self.assertFalse(manifest['complete'])
            self.assertIn('НЕПОЛНЫЙ ЭКСПОРТ', text)

    def test_flood_wait_is_honored_without_busy_retries(self):
        s = self.session()
        s.process(None, types.SimpleNamespace(text='FLOOD_WAIT_130'))
        self.assertFalse(s.stopped)
        self.assertEqual(s.scheduled, [131])
        s.finish(False, 'test cleanup')

    def test_late_or_duplicate_callbacks_are_ignored(self):
        s = self.session()
        s.nonce = 2
        s.awaiting = True
        s.deliver(1, response([message(9)]), None)
        self.assertEqual(s.archive.count, 0)
        s.deliver(2, response([message(9)]), None)
        s.deliver(2, response([message(8)]), None)
        self.assertEqual(s.archive.count, 1)
        s.finish(False, 'test cleanup')

    def test_account_change_stops_export_without_another_history_request(self):
        s = self.session()
        s.valid = lambda: False
        s.request()
        self.assertTrue(s.stopped)
        self.assertFalse(self.read_archive()[1]['complete'])

    def test_no_ai_or_automatic_send_permissions(self):
        self.assertNotIn('ai.complete', mod.__permissions__)
        self.assertNotIn('messages.send', mod.__permissions__)
        self.assertNotIn('internet', mod.__permissions__)


if __name__ == '__main__':
    unittest.main()
