import hashlib
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch
import target_restore as target


def archive(path, members):
    with tarfile.open(path,'w:gz') as out:
        for name,value in members:
            item=tarfile.TarInfo(name);item.size=len(value)
            out.addfile(item,io.BytesIO(value))


class RestoreSafety(unittest.TestCase):
    def snapshot(self, folder):
        archive(folder/'media.tar.gz',[('media/file',b'public'),('private_media/file',b'private')])
        archive(folder/'scheduler.tar.gz',[('celerybeat-schedule',b'closed-state')])
        for name in ['database.dump','database-inventory.json','redis.json']:(folder/name).write_bytes(b'fixture')
        manifest={p.name:{'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in folder.iterdir()}
        (folder/'manifest.json').write_text(json.dumps(manifest))
    def test_corrupt_transfer_is_rejected(self):
        with tempfile.TemporaryDirectory() as name:
            folder=Path(name);self.snapshot(folder);(folder/'database.dump').write_bytes(b'changed')
            with self.assertRaisesRegex(RuntimeError,'checksum mismatch'):target.verify(folder)
    def test_unsafe_archive_member_rejected(self):
        with tempfile.TemporaryDirectory() as name:
            folder=Path(name);archive(folder/'media.tar.gz',[('../outside',b'bad')])
            with patch.object(target,'verify'):
                with self.assertRaisesRegex(RuntimeError,'Unsafe archive'):target.stage_files(folder)
            self.assertFalse((folder.parent/'outside').exists())
    def test_files_are_staged_without_changing_live_paths(self):
        with tempfile.TemporaryDirectory() as name:
            folder=Path(name);self.snapshot(folder)
            result=target.stage_files(folder)
            self.assertEqual(result['staged_files'],{'media.tar.gz':2,'scheduler.tar.gz':1})
            self.assertFalse(result['live_media_or_scheduler_changed'])
            self.assertEqual((folder/'files/media/private_media/file').read_bytes(),b'private')
    def test_existing_database_is_never_replaced(self):
        config={'database':{'name':'vendistri_production','user':'proclaws_app'}}
        with patch.object(target,'verify'),patch.object(target,'database_command',return_value=[[1]]) as command:
            with self.assertRaisesRegex(RuntimeError,'already exists'):target.restore_database(config,Path('/unused'),'private')
            self.assertEqual(command.call_count,1)


if __name__=='__main__':unittest.main()
