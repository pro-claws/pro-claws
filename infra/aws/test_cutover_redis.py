import base64
import unittest
from cutover_redis import export_client, restore_client


class Fake:
    def __init__(self, rows):
        self.rows = rows; self.calls = []; self.operations = []
    def time(self):
        if self.operations:
            self.operations.append((None, 2)); return self
        return (1000, 0)
    def scan_iter(self, match): return [key for key in self.rows if key.startswith(match[:-1])]
    def pipeline(self, transaction):
        assert transaction; self.operations = []; return self
    def dump(self, key): self.operations.append((key, 0)); return self
    def pttl(self, key): self.operations.append((key, 1)); return self
    def execute(self):
        result = [self.rows[key][index] if index != 2 else (1000, 0) for key, index in self.operations]
        self.operations = []
        return result
    def exists(self, key): return key in self.rows
    def restore(self, key, ttl, value, replace, absttl):
        assert not replace and absttl
        self.calls.append((key, ttl, value))


class CacheTransfer(unittest.TestCase):
    def test_export_excludes_unrelated_and_expired(self):
        source = Fake({b'vendistri:a': (b'dump', 500), b'vendistri:permanent': (b'p', -1),
                       b'vendistri:gone': (None, -2), b'other:private': (b'secret', -1)})
        rows = export_client(source, b'vendistri:')
        self.assertEqual(len(rows), 2)
        self.assertEqual([row['expires_ms'] for row in rows], [1000500, 0])
    def test_restore_preserves_absolute_expiry_skips_expired(self):
        rows = export_client(Fake({b'vendistri:a': (b'd', 500), b'vendistri:p': (b'p', -1)}), b'vendistri:')
        target = Fake({})
        self.assertEqual(restore_client(target, rows, b'vendistri:', 1000600), {'restored': 1, 'expired': 1})
        self.assertEqual(target.calls, [(b'vendistri:p', 0, b'p')])
    def test_refuses_unowned_or_existing_key_before_writes(self):
        rows = export_client(Fake({b'vendistri:a': (b'd', -1), b'vendistri:z': (b'z', -1)}), b'vendistri:')
        target = Fake({b'vendistri:z': (b'other', -1)})
        with self.assertRaises(RuntimeError): restore_client(target, rows, b'vendistri:')
        self.assertEqual(target.calls, [])
        rows[0]['key'] = base64.b64encode(b'other:key').decode()
        with self.assertRaises(RuntimeError): restore_client(Fake({}), rows, b'vendistri:')


if __name__ == '__main__': unittest.main()
