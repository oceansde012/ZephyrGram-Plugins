"""0.7.4: service text of the model (tool-call remnants, empty quote pairs) never reaches a chat reply."""
import unittest

from test_ai_autoreply import mod


class TestLeak(unittest.TestCase):
    def test_screenshot_case(self):
        raw = u'иди зохавай булку, поплачь там если надо, только сушняком не давись\nпоследи.То "" not possible in tool'
        self.assertTrue(mod.has_leak(raw))
        out = mod.clean_humanized(raw, 300, preserve_filler=True)
        self.assertNotIn("tool", out)
        self.assertNotIn('""', out)
        self.assertTrue(out.endswith(u"последи."))

    def test_markers(self):
        for raw in (u'ну да <tool_call>x', u'ок function_call foo', u'ага [TOOL_RESULT] 1', u'да "" ладно'):
            self.assertTrue(mod.has_leak(raw), raw)

    def test_normal_text_untouched(self):
        for raw in (u'та норм все', u'скинь фотку, ахах', u'he said "ok" and left', u'ну погнали, tool у мене є'):
            self.assertFalse(mod.has_leak(raw), raw)
            self.assertEqual(mod.strip_leak(raw), raw)

    def test_cut_without_sentence_end(self):
        self.assertEqual(mod.strip_leak(u'ок давай "" not possible in tool'), u'ок давай')


if __name__ == "__main__":
    unittest.main()
