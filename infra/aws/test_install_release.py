"""Reject runtime archives outside the audited non-Git asset boundary."""
import hashlib
import io
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch
from install_release import install_runtime_assets


class RuntimeAssetsTest(unittest.TestCase):
    def archive(self, directory, name):
        path = directory / 'assets.tar.gz'
        with tarfile.open(path, 'w:gz') as archive:
            member = tarfile.TarInfo(name)
            member.size = 4
            archive.addfile(member, io.BytesIO(b'test'))
        return path, hashlib.sha256(path.read_bytes()).hexdigest()

    @patch('install_release.os.chown')
    def test_verified_asset_is_installed_once(self, chown):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive, digest = self.archive(root, 'private_data/dbip-city.mmdb')
            install_runtime_assets(archive, digest, root / 'backend')
            self.assertEqual((root / 'backend/private_data/dbip-city.mmdb').read_bytes(), b'test')
            with self.assertRaises(SystemExit):
                install_runtime_assets(archive, digest, root / 'backend')

    def test_unreviewed_file_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive, digest = self.archive(root, 'private_data/unreviewed.json')
            with self.assertRaises(SystemExit):
                install_runtime_assets(archive, digest, root / 'backend')
            self.assertFalse((root / 'backend').exists())

    def test_bad_checksum_is_rejected_before_extraction(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive, _ = self.archive(root, 'private_data/dbip-city.mmdb')
            with self.assertRaises(SystemExit):
                install_runtime_assets(archive, '0' * 64, root / 'backend')
            self.assertFalse((root / 'backend').exists())


if __name__ == '__main__':
    unittest.main()
