"""Exercise source/static rollback and refuse unreviewed or unsafe artifacts."""
import hashlib
import io
import json
import os
from pathlib import Path
import tarfile
import tempfile
import unittest

from promote_rehearsal import digest, inventory, promote, restore, verify


class RehearsalPromotionTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.root, self.source = self.base / 'installed', self.base / 'candidate'
        self.portal, self.backup = self.base / 'www/fe', self.root / '.migration/rollback-test'
        self.portal.mkdir(parents=True)
        (self.portal / 'index.html').write_text('old portal')
        self.old = self.make_tree(self.root, {'backend/app.py': 'old code', 'backend/removed.py': 'old removed',
                                               '.migration/source-release.json': 'old metadata'}, installed=True)
        self.new = self.make_tree(self.source, {'backend/app.py': 'new code', 'backend/added.py': 'new added',
                                                 'source-release.json': 'new metadata'})
        (self.root / 'backend/.env').write_text('preserved environment')
        (self.root / 'backend/media').mkdir()
        (self.root / 'backend/media/customer-photo.jpg').write_text('preserved media')
        self.archive = self.base / 'portal.tar.gz'
        files = {'fe/index.html': 'new portal', 'fe/static/app.js': 'new javascript',
                 'fe/asset-manifest.json': json.dumps({'files': {'main.js': '/static/app.js'}})}
        with tarfile.open(self.archive, 'w:gz') as archive:
            for name, content in files.items():
                member = tarfile.TarInfo(name)
                member.size, member.mode = len(content.encode()), 0o644
                archive.addfile(member, io.BytesIO(content.encode()))
        self.events = []

    def make_tree(self, root, files, installed=False):
        lines = []
        for name, content in files.items():
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
            managed = 'source-release.json' if installed and name.startswith('.migration/') else name
            lines.append(digest(path) + '  ' + managed)
        target = root / ('previous.sha256' if installed else 'source.sha256')
        target.write_text('\n'.join(lines) + '\n')
        return target

    def promote(self, health=None):
        return promote(self.root, self.source, self.old, self.portal, self.archive,
                       digest(self.archive), self.backup,
                       lambda: self.events.append('stop'), lambda: self.events.append('start'),
                       health or (lambda: self.events.append('healthy')),
                       new_identity=(os.getuid(), os.getgid()))

    def assert_preserved(self):
        self.assertEqual((self.root / 'backend/.env').read_text(), 'preserved environment')
        self.assertEqual((self.root / 'backend/media/customer-photo.jpg').read_text(), 'preserved media')

    def test_promotion_and_explicit_rollback_preserve_configuration_and_data(self):
        receipt = self.promote()
        self.assertEqual(receipt['state'], 'active')
        verify(self.root, inventory(self.new))
        self.assertEqual((self.portal / 'index.html').read_text(), 'new portal')
        self.assertFalse((self.root / 'backend/removed.py').exists())
        self.assert_preserved()
        restore(self.root, self.backup, self.portal, lambda: None, lambda: None, lambda: None)
        verify(self.root, inventory(self.old))
        self.assertEqual((self.portal / 'index.html').read_text(), 'old portal')
        self.assertFalse((self.root / 'backend/added.py').exists())
        self.assertEqual(json.loads((self.backup / 'receipt.json').read_text())['state'], 'rolled_back')
        self.assert_preserved()

    def test_failed_new_release_readiness_restores_source_and_portal(self):
        calls = []
        def health():
            calls.append(True)
            if len(calls) == 1:
                raise RuntimeError('new release unhealthy')
        with self.assertRaisesRegex(RuntimeError, 'new release unhealthy'):
            self.promote(health)
        verify(self.root, inventory(self.old))
        self.assertEqual((self.portal / 'index.html').read_text(), 'old portal')
        self.assertEqual(len(calls), 2)
        self.assert_preserved()

    def test_modified_installed_source_is_rejected_before_stopping_services(self):
        (self.root / 'backend/app.py').write_text('unexpected live edit')
        with self.assertRaisesRegex(ValueError, 'checksum mismatch'):
            self.promote()
        self.assertEqual(self.events, [])
        self.assertFalse(self.backup.exists())

    def test_unmanaged_source_collision_is_preserved(self):
        (self.root / 'backend/added.py').write_text('unmanaged content')
        with self.assertRaisesRegex(ValueError, 'Unmanaged file'):
            self.promote()
        self.assertEqual((self.root / 'backend/added.py').read_text(), 'unmanaged content')
        self.assertEqual(self.events, [])

    def test_bad_archive_is_rejected_before_stopping_services(self):
        with self.archive.open('ab') as stream:
            stream.write(b'unexpected change')
        with self.assertRaisesRegex(ValueError, 'Portal archive checksum'):
            promote(self.root, self.source, self.old, self.portal, self.archive, '0' * 64,
                    self.backup, lambda: self.events.append('stop'), lambda: None, lambda: None)
        self.assertEqual(self.events, [])

    def test_path_escape_and_symlink_sources_are_rejected(self):
        unsafe = self.base / 'unsafe.sha256'
        unsafe.write_text('0' * 64 + '  backend/../../outside\n')
        with self.assertRaises(ValueError):
            inventory(unsafe)
        (self.source / 'backend/app.py').unlink()
        (self.source / 'backend/app.py').symlink_to(self.root / 'backend/app.py')
        with self.assertRaisesRegex(ValueError, 'escapes release or is a symlink'):
            self.promote()
        self.assertEqual(self.events, [])


if __name__ == '__main__':
    unittest.main()
