import hashlib
import io
import tarfile
import unittest
from verify_retirement_archive import verify


def fixture():
    output = io.BytesIO()
    dumps = []
    with tarfile.open(fileobj=output, mode='w:gz') as archive:
        for name in ('home/akatary/pro_claws', 'var/www/vendistri'):
            info = tarfile.TarInfo(name); info.type = tarfile.DIRTYPE
            archive.addfile(info)
        for name in ('proclaws_prod', *('test_proclaws_prod_' + str(n) for n in range(1, 5))):
            data = ('Synthetic fixture ' + name).encode()
            info = tarfile.TarInfo('var/lib/vendistri-retirement-20261028/databases/' + name + '.dump')
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))
            dumps.append({'database': name, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()})
    body = output.getvalue()
    return body, {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest(), 'database_dumps': dumps}


class VerificationTests(unittest.TestCase):
    def test_full_archive_and_five_database_digests(self):
        body, expected = fixture()
        result = verify(io.BytesIO(body), expected)
        self.assertEqual(result['database_payloads_verified'], 5)
        self.assertEqual(result['files_extracted'], 0)

    def test_valid_archive_with_wrong_payload_hash_is_rejected(self):
        body, expected = fixture()
        expected['database_dumps'][0]['sha256'] = '0' * 64
        with self.assertRaises(RuntimeError):
            verify(io.BytesIO(body), expected)

    def test_truncation_is_rejected(self):
        body, expected = fixture()
        with self.assertRaises((EOFError, OSError, tarfile.TarError)):
            verify(io.BytesIO(body[:-7]), expected)

    def test_wrong_compressed_digest_is_rejected(self):
        body, expected = fixture()
        expected['sha256'] = '0' * 64
        with self.assertRaises(RuntimeError):
            verify(io.BytesIO(body), expected)


if __name__ == '__main__':
    unittest.main()
