import io
from pathlib import Path
import tempfile
import unittest
from retirement_archive import DATABASES, APP_PATHS, safe_source
from retirement_upload import read_part, valid_url


class Chunked(io.BytesIO):
    def read(self, size=-1):
        return super().read(min(size, 3))


class ArchiveTests(unittest.TestCase):
    def test_exact_five_database_scope(self):
        self.assertEqual(DATABASES, ('proclaws_prod', 'test_proclaws_prod_1',
                                    'test_proclaws_prod_2', 'test_proclaws_prod_3',
                                    'test_proclaws_prod_4'))
        self.assertNotIn('/home/akatary', APP_PATHS)
        self.assertNotIn('/var/www', APP_PATHS)

    def test_archive_root_cannot_follow_symlink_into_another_project(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / 'other'; target.mkdir()
            link = Path(folder) / 'vendistri'; link.symlink_to(target)
            with self.assertRaises(RuntimeError):
                safe_source(link)

    def test_short_pipe_reads_preserve_every_byte(self):
        stream = Chunked(b'abcdefghijk')
        self.assertEqual(read_part(stream, 8), b'abcdefgh')
        self.assertEqual(read_part(stream, 8), b'ijk')
        self.assertEqual(read_part(stream, 8), b'')

    def test_urls_cannot_send_archive_to_unreviewed_destinations(self):
        for url in ('http://vendistri-aws-artifacts-artifacts-9clgm8cgzbem.s3.amazonaws.com/x',
                    'https://evil.example/x',
                    'https://vendistri-aws-artifacts-artifacts-9clgm8cgzbem.s3.amazonaws.com.evil.example/x'):
            with self.assertRaises(ValueError):
                valid_url(url)


if __name__ == '__main__':
    unittest.main()
