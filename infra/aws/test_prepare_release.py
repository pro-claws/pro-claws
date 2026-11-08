import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

spec = importlib.util.spec_from_file_location("prepare_release", Path(__file__).with_name("prepare_release.py"))
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


class ReleaseIsolationTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.repo = self.root / "backend"
        self.repo.mkdir()
        self.git("init", "--quiet")
        self.git("config", "user.email", "release-test@example.invalid")
        self.git("config", "user.name", "Release Test")
        (self.repo / "app.py").write_text("reviewed = True\n")
        (self.repo / ".env").write_text("TEST_SECRET=do-not-export\n")
        self.commit()
        self.revision = self.git("rev-parse", "HEAD").strip()
        self.manifest = self.root / "release.json"

    def git(self, *args):
        return subprocess.check_output(["git", "-C", str(self.repo), *args], text=True)

    def commit(self):
        self.git("add", ".")
        self.git("commit", "--quiet", "-m", "Fixture")

    def prepare(self, submodules=None):
        self.manifest.write_text(json.dumps({"repositories": {"backend": {
            "revision": self.revision, "submodules": submodules or {}}}}))
        return release.prepare(self.root, self.manifest, self.root / "output")

    def test_exports_reviewed_commit_without_secrets_or_dirty_work(self):
        (self.repo / "app.py").write_text("development = True\n")
        (self.repo / "untracked.py").write_text("unpublished = True\n")
        self.prepare()
        target = self.root / "output" / "backend"
        self.assertEqual((target / "app.py").read_text(), "reviewed = True\n")
        self.assertFalse((target / ".env").exists())
        self.assertFalse((target / "untracked.py").exists())
        self.assertEqual((self.repo / "app.py").read_text(), "development = True\n")
        self.assertIn("backend/app.py", (target.parent / "source.sha256").read_text())

    def test_rejects_hardware_before_creating_output(self):
        (self.repo / "hardware").mkdir()
        (self.repo / "hardware" / "__init__.py").write_text("")
        self.commit()
        self.revision = self.git("rev-parse", "HEAD").strip()
        with self.assertRaisesRegex(ValueError, "Unreleased hardware"):
            self.prepare()
        self.assertFalse((self.root / "output").exists())

    def test_rejects_unreviewed_submodule(self):
        self.git("update-index", "--add", "--cacheinfo", f"160000,{self.revision},packages/ui")
        self.git("commit", "--quiet", "-m", "Add submodule link")
        self.revision = self.git("rev-parse", "HEAD").strip()
        with self.assertRaisesRegex(ValueError, "submodule"):
            self.prepare()

    def test_never_overwrites_existing_package(self):
        self.prepare()
        with self.assertRaises(FileExistsError):
            self.prepare()

    def test_rejects_submodule_path_escape(self):
        for path in ("../escape", "/tmp/escape", "packages/../../escape"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                release.checked_path(path)


if __name__ == "__main__":
    unittest.main()
