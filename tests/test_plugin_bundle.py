import json
import unittest
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[1]
PLUGIN = PROJECT / "plugins" / "papermeld"


class PaperMeldPluginBundleTest(unittest.TestCase):
    def test_plugin_and_marketplace_point_to_the_single_skill_source(self):
        manifest = json.loads((PLUGIN / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
        marketplace = json.loads((PROJECT / ".agents" / "plugins" / "marketplace.json").read_text(encoding="utf-8"))
        skill = PLUGIN / "skills" / "papermeld" / "SKILL.md"
        repo_skill = PROJECT / ".agents" / "skills" / "papermeld" / "SKILL.md"

        self.assertEqual(manifest["name"], "papermeld")
        self.assertEqual(manifest["skills"], "./skills/")
        self.assertEqual(marketplace["name"], "papermeld")
        self.assertEqual(marketplace["plugins"][0]["name"], "papermeld")
        self.assertEqual((PROJECT / marketplace["plugins"][0]["source"]["path"]).resolve(), PLUGIN.resolve())
        self.assertEqual(repo_skill.resolve(), skill.resolve())
        contents = skill.read_text(encoding="utf-8")
        self.assertTrue(contents.startswith("---\nname: papermeld\n"))
        self.assertNotIn("[TODO", contents)


if __name__ == "__main__":
    unittest.main()
