"""LAMP (JFP-T19): Jellyfin Poster's settings and key through MindAttic Vault, one test per setting.

Run: python -m unittest discover -s tests
"""
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import vault  # noqa: E402

LIBRARY_SETTINGS = {
    "moviesLibraryName": ("JF_MOVIES_LIBRARY_NAME", "movies", "Movies"),
    "tvLibraryName": ("JF_TV_LIBRARY_NAME", "tvshows", "TV Shows"),
    "booksLibraryName": ("JF_BOOKS_LIBRARY_NAME", "books", "Books"),
    "musicLibraryName": ("JF_MUSIC_LIBRARY_NAME", "music", "Music"),
}


class VaultTestCase(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="jfp-vault-")
        self._saved = {k: os.environ.get(k) for k in ("MINDATTIC_VAULT_ROAMING_ROOT", "MINDATTIC_VAULT_LOCAL_ROOT")}
        os.environ["MINDATTIC_VAULT_ROAMING_ROOT"] = os.path.join(self.root, "roaming")
        os.environ["MINDATTIC_VAULT_LOCAL_ROOT"] = os.path.join(self.root, "local")

    def tearDown(self):
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(self.root, ignore_errors=True)

    def save(self, **values):
        settings = vault.load_settings()
        settings.update(values)
        vault._write_json_atomic(vault.settings_path(), settings)

    def read(self, *parts):
        with open(os.path.join(self.root, "roaming", *parts), encoding="utf-8") as f:
            return json.load(f)


class SettingTests(VaultTestCase):
    def check_library(self, prop):
        env_var, media, default = LIBRARY_SETTINGS[prop]
        vault.import_env_once({env_var: "Imported " + media})
        self.assertEqual(vault.load_settings()[prop], "Imported " + media, "today's .env value imported")
        self.save(**{prop: "Edited " + media})
        self.assertEqual(self.read("JellyFinPoster", "settings.json")[prop], "Edited " + media, "saved under its manifest name")
        self.assertEqual(vault.resolve({})[2][media], "Edited " + media, "the script uses it")
        self.save(**{prop: ""})
        self.assertEqual(vault.resolve({})[2][media], default, "blank falls back to the old default")

    def test_Setting_jfUrl_ImportsRoundTripsAndIsTheServerTheScriptCalls(self):
        vault.import_env_once({"JF_URL": "http://10.0.0.5:8096/"})
        self.assertEqual(vault.load_settings()["jfUrl"], "http://10.0.0.5:8096/")
        self.save(jfUrl="http://media.local:8096/")
        self.assertEqual(vault.resolve({})[0], "http://media.local:8096", "trailing slash trimmed for the requests")

    def test_Setting_moviesLibraryName_ImportsRoundTripsAndIsUsed(self):
        self.check_library("moviesLibraryName")

    def test_Setting_tvLibraryName_ImportsRoundTripsAndIsUsed(self):
        self.check_library("tvLibraryName")

    def test_Setting_booksLibraryName_ImportsRoundTripsAndIsUsed(self):
        self.check_library("booksLibraryName")

    def test_Setting_musicLibraryName_ImportsRoundTripsAndIsUsed(self):
        self.check_library("musicLibraryName")

    def test_EverySettingHasItsOwnTest(self):
        names = [n for n in dir(self) if n.startswith("test_Setting_")]
        for field in vault.manifest()["fields"]:
            self.assertTrue(any(n.startswith("test_Setting_" + field["property"] + "_") for n in names), field["property"])


class KeyTests(VaultTestCase):
    def test_EnvKey_IsImportedOnceAsANamedKeyAndAssigned(self):
        vault.import_env_once({"JF_API_KEY": "jf-123"})
        vault.import_env_once({"JF_API_KEY": "jf-123"})
        providers = self.read("LLM", "providers.json")
        self.assertEqual(providers["jellyfin"]["apiKey"], "jf-123")
        self.assertEqual([e["label"] for e in providers["jellyfin"]["apiKeys"]], ["JellyFinPoster (imported)"])
        self.assertEqual(self.read("Vault", "key-assignments.json")["JellyFinPoster"]["jellyfin"], ["JellyFinPoster (imported)"])
        self.assertEqual(vault.resolve({})[1], "jf-123")

    def test_KeyEditedInVault_WinsOverTheEnvironment(self):
        vault._add_named_key("jellyfin", "home", "jf-vault")
        self.assertEqual(vault.resolve({"JF_API_KEY": "jf-env"})[1], "jf-vault")

    def test_AssignedOrderDisabledAndUnhealthyKeysAreRespected(self):
        vault._add_named_key("jellyfin", "a", "jf-a")
        vault._add_named_key("jellyfin", "b", "jf-b")
        vault._add_named_key("jellyfin", "c", "jf-c")
        vault._assign_first("jellyfin", "b")
        self.assertEqual(vault.get_key(), "jf-b")
        health = os.path.join(self.root, "local", "Vault", "key-health.json")
        vault._write_json_atomic(health, {"jellyfin": {"b": {"failed": True}}})
        self.assertIsNone(vault.get_key(), "only b is assigned and it failed")
        os.remove(os.path.join(self.root, "roaming", "Vault", "key-assignments.json"))
        self.assertEqual(vault.get_key(), "jf-a", "shared order, skipping the failed key")

    def test_UnlabeledKeysAreNamedLikeVault(self):
        vault._write_json_atomic(os.path.join(self.root, "roaming", "LLM", "providers.json"),
                                 {"jellyfin": {"apiKey": "x", "apiKeys": [{"key": "x"}, {"key": "y", "label": "Team"}, {"key": "z"}]}})
        self.assertEqual([n for n, _, _ in vault.named_keys()], ["key1", "Team", "key2"])

    def test_OtherProvidersAreLeftIntact(self):
        vault._write_json_atomic(os.path.join(self.root, "roaming", "LLM", "providers.json"), {"claude": {"type": "anthropic", "apiKey": "sk"}})
        vault.import_env_once({"JF_API_KEY": "jf"})
        self.assertEqual(self.read("LLM", "providers.json")["claude"], {"type": "anthropic", "apiKey": "sk"})


class ManifestTests(VaultTestCase):
    def test_ManifestIsWrittenOnceAndMatchesTheVaultSchema(self):
        path = vault.write_manifest()
        first = os.path.getmtime(path)
        vault.write_manifest()
        self.assertEqual(os.path.getmtime(path), first, "unchanged content isn't rewritten")
        m = self.read("JellyFinPoster", "settings.manifest.json")
        self.assertEqual((m["schemaVersion"], m["appId"], m["configurationPrefix"]), (1, "JellyFinPoster", "MindAttic:Settings:JellyFinPoster"))
        self.assertTrue(all(f["label"] and f["help"] and f["name"] == "MindAttic:Settings:JellyFinPoster:" + f["property"] for f in m["fields"]))
        self.assertEqual(m["credentials"][0]["providerId"], "jellyfin")

    def test_FreshMachineSeedsTodaysDefaults(self):
        vault.import_env_once({})
        self.assertEqual(self.read("JellyFinPoster", "settings.json"), vault.defaults())

    def test_ExistingSettingsAreNeverOverwrittenByTheEnvironment(self):
        self.save(jfUrl="http://kept")
        vault.import_env_once({"JF_URL": "http://other"})
        self.assertEqual(vault.load_settings()["jfUrl"], "http://kept")

    def test_CorruptSettingsFallBackToDefaults(self):
        os.makedirs(vault.app_dir(), exist_ok=True)
        with open(vault.settings_path(), "w") as f:
            f.write("{ nope")
        self.assertEqual(vault.load_settings(), vault.defaults())


if __name__ == "__main__":
    unittest.main()
