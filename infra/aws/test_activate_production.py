import unittest
from unittest.mock import patch
import activate_production as activation


class ActivationGuards(unittest.TestCase):
    def test_start_requires_aws_commit_before_any_action(self):
        with patch.object(activation,'run') as run:
            with self.assertRaises(RuntimeError):activation.start('a',{'phase':'snapshot-complete','authority':'source'})
            run.assert_not_called()
    def test_prepare_requires_complete_source_snapshot(self):
        with patch.object(activation,'run') as run:
            with self.assertRaises(RuntimeError):activation.prepare('a',{'phase':'prepared','authority':'source'})
            run.assert_not_called()
    def test_release_changes_only_known_gate_and_preserves_private_denial(self):
        match='<LocationMatch "^/(?!vendistri/be/health/ready/?$)">\n Require local\n</LocationMatch>'
        private='<LocationMatch "^/vendistri/be/private_media(?:/|$)">\nRequire all denied\n</LocationMatch>'
        body=match+'\n'+match+'\n<Location />\nRequire local\n</Location>\n'+private
        result=activation.release_config(body)
        self.assertEqual(result.count('Require all granted'),3)
        self.assertIn(private,result)
    def test_unknown_gate_layout_is_rejected(self):
        with self.assertRaises(RuntimeError):activation.release_config('<Location />\nRequire local\n</Location>')


if __name__=='__main__':unittest.main()
