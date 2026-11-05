"""inline_as_own 1.0.0: which inline results go out as own messages, caption switch, logged fallbacks."""
import importlib.machinery
import importlib.util
from pathlib import Path
import sys
import types
import unittest


class _BasePlugin(object):
    def __init__(self):
        self.settings, self.logs, self.hooks = {}, [], []

    def get_setting(self, key, default=None):
        return self.settings.get(key, default)

    def log(self, message):
        self.logs.append(message)

    def add_inline_result_hook(self, priority=0):
        self.hooks.append(priority)


class _InlineAction(object):
    @staticmethod
    def send_as_own(caption=None):
        return ("own", caption)


_locale = {"value": "ru"}
_zephyr = types.ModuleType('zephyr')
_zephyr.BasePlugin = _BasePlugin
_zephyr.InlineAction = _InlineAction
_zephyr.client = types.SimpleNamespace(app_locale=lambda: _locale["value"])
_ui = types.ModuleType('zephyr.ui')
for _name in ('Header', 'Switch', 'Text'):
    setattr(_ui, _name, lambda _n=_name, **kw: types.SimpleNamespace(kind=_n, **kw))
_saved = {key: sys.modules.get(key) for key in ('zephyr', 'zephyr.ui')}
sys.modules.update({'zephyr': _zephyr, 'zephyr.ui': _ui})
_path = Path(__file__).resolve().parents[1] / 'plugins/inline_as_own/inline_as_own.plugin'
_loader = importlib.machinery.SourceFileLoader('inline_as_own_tests_module', str(_path))
mod = importlib.util.module_from_spec(importlib.util.spec_from_loader(_loader.name, _loader))
_loader.exec_module(mod)
for _key, _value in _saved.items():
    if _value is None:
        sys.modules.pop(_key, None)
    else:
        sys.modules[_key] = _value


def info(**extra):
    base = {"type": "gif", "kind": "media", "message_kind": "media_auto", "caption": "secret caption text",
            "dialog_id": 123456, "secret": False, "file_path": "/cache/a.mp4", "can_send_as_own": True}
    base.update(extra)
    return base


class InlineAsOwn(unittest.TestCase):
    def setUp(self):
        self.p = mod.Plugin()
        self.p.on_plugin_load()

    def test_manifest(self):
        self.assertEqual(mod.__id__, "inline_as_own")
        self.assertEqual(mod.__permissions__, ["inline.hook"])
        self.assertEqual(mod.__min_app_version__, "0.2.5")
        self.assertEqual(self.p.hooks, [0])

    def test_media_goes_as_own_with_bot_caption_by_default(self):
        self.assertEqual(self.p.on_inline_result_send(0, info()), ("own", None))

    def test_caption_switch_removes_media_caption(self):
        self.p.settings["strip_caption"] = True
        self.assertEqual(self.p.on_inline_result_send(0, info()), ("own", ""))

    def test_caption_switch_never_empties_a_text_result(self):
        self.p.settings["strip_caption"] = True
        r = self.p.on_inline_result_send(0, info(type="article", kind="none", message_kind="text"))
        self.assertEqual(r, ("own", None))

    def test_disabled_sends_unchanged(self):
        self.p.settings["enabled"] = False
        self.assertIsNone(self.p.on_inline_result_send(0, info()))
        self.assertEqual(self.p.logs, [])

    def test_fallbacks_are_logged_without_private_data(self):
        cases = [
            (info(secret=True), "secret chat"),
            (info(type="game"), "game"),
            (info(type="geo", message_kind="geo"), "location"),
            (info(message_kind="contact"), "contact"),
            (info(message_kind="invoice"), "invoice"),
            (info(type="photo", kind="external"), "external photo"),
            (info(type="video", kind="external", file_path=None), "external file not downloaded yet"),
        ]
        for data, reason in cases:
            data["can_send_as_own"] = False
            self.p.logs.clear()
            self.assertIsNone(self.p.on_inline_result_send(0, data), reason)
            self.assertEqual(len(self.p.logs), 1)
            self.assertIn(reason, self.p.logs[0])
            self.assertNotIn("secret caption text", self.p.logs[0])
            self.assertNotIn("123456", self.p.logs[0])

    def test_settings_in_three_languages(self):
        for lang, word in (("ru", "своё"), ("uk", "своє"), ("en", "own"), ("de", "own")):
            _locale["value"] = lang
            rows = self.p.create_settings()
            self.assertEqual([r.kind for r in rows], ["Header", "Switch", "Switch", "Text"])
            self.assertEqual([getattr(r, "key", None) for r in rows], [None, "enabled", "strip_caption", None])
            self.assertIn(word, rows[1].text)
        _locale["value"] = "ru"


if __name__ == '__main__':
    unittest.main()
