"""No plugin may define a method or attribute that BasePlugin.__init__ of the app overwrites after the plugin's own __init__.

The app (0.2.5+) calls BasePlugin.__init__(plugin) after creating the plugin, which sets id, name, version, data_dir,
_menus (a dict), _settings and _menu_sequence on the instance. A method named _menus then became a dict and the plugin
failed to load with "TypeError: 'dict' object is not callable" (ai_autoreply 0.9.0 to 0.9.7 on the phone)."""
import ast
import glob
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOST_FIELDS = {"id", "name", "version", "data_dir", "_menus", "_menu_sequence"}
HOST_FIELDS_PROPERTY_OK = {"_settings"}     # allowed only as a property with a setter (ai_autoreply keeps callbacks)


class HostFieldCollisions(unittest.TestCase):
    def test_no_plugin_method_or_class_attribute_shadows_a_host_field(self):
        found = []
        for path in sorted(glob.glob(os.path.join(ROOT, "plugins", "*", "*.plugin"))):
            tree = ast.parse(open(path, encoding="utf-8").read())
            for cls in [n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "Plugin"]:
                for node in cls.body:
                    names = []
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        names = [node.name]
                        is_property = any(isinstance(d, ast.Name) and d.id == "property" for d in node.decorator_list)
                        setter = any(isinstance(d, ast.Attribute) and d.attr == "setter" for d in node.decorator_list)
                        if node.name in HOST_FIELDS_PROPERTY_OK and (is_property or setter):
                            names = []
                    elif isinstance(node, ast.Assign):
                        names = [t.id for t in node.targets if isinstance(t, ast.Name)]
                    for name in names:
                        if name in HOST_FIELDS or name in HOST_FIELDS_PROPERTY_OK:
                            found.append("%s: Plugin.%s" % (os.path.basename(path), name))
        self.assertEqual(found, [])

    def test_the_check_would_catch_the_old_ai_autoreply(self):
        source = "class Plugin(BasePlugin):\n    def _menus(self):\n        pass\n"
        cls = ast.parse(source).body[0]
        self.assertEqual([n.name for n in cls.body if n.name in HOST_FIELDS], ["_menus"])


if __name__ == "__main__":
    unittest.main()
