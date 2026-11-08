"""Regression checks for costly or unsafe migration defaults, not AWS schemas."""
from pathlib import Path
import subprocess
import unittest
import yaml


class Loader(yaml.SafeLoader):
    pass


def intrinsic(loader, tag, node):
    if isinstance(node, yaml.ScalarNode):
        value = loader.construct_scalar(node)
    elif isinstance(node, yaml.SequenceNode):
        value = loader.construct_sequence(node)
    else:
        value = loader.construct_mapping(node)
    return {tag: value}


Loader.add_multi_constructor("!", intrinsic)


class FoundationDefaultsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.template = yaml.load(Path(__file__).with_name("foundation.yaml").read_text(), Loader=Loader)
        cls.resources = cls.template["Resources"]

    def test_ha_database_uses_provider_placement_and_stays_private(self):
        database = self.resources["Database"]["Properties"]
        self.assertEqual(database["RelationalDatabaseBundleId"], "small_ha_2_0")
        self.assertNotIn("AvailabilityZone", database)
        self.assertFalse(database["PubliclyAccessible"])
        self.assertTrue(database["BackupRetention"])

    def test_hosts_have_distinct_azs_and_restricted_ssh_only(self):
        zones = []
        for name in ("HostA", "HostB"):
            props = self.resources[name]["Properties"]
            zones.append(props["AvailabilityZone"])
            ports = props["Networking"]["Ports"]
            self.assertEqual(len(ports), 1)
            self.assertEqual((ports[0]["FromPort"], ports[0]["ToPort"]), (22, 22))
            self.assertEqual(ports[0]["Cidrs"], [{"Ref": "OperatorCidr"}])
            self.assertIn("systemctl mask vendistri-celery-beat.service", props["UserData"])
            self.assertIn("vendistri-telemetry-intake.service", props["UserData"])
        self.assertNotEqual(*zones)
        self.assertIn("DistinctZones", self.template["Rules"])

    def test_no_traffic_cutover_or_application_attachment(self):
        self.assertNotIn("AttachedInstances", self.resources["LoadBalancer"]["Properties"])
        self.assertFalse(any(r["Type"].startswith("AWS::Route53::") for r in self.resources.values()))

    def test_initialization_options_work_in_lightsail_posix_wrapper(self):
        for name in ("HostA", "HostB"):
            script = self.resources[name]["Properties"]["UserData"]
            options = next(line for line in script.splitlines() if line.startswith("set "))
            result = subprocess.run(["sh", "-c", options], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_broker_replication_does_not_trade_away_encryption_or_queued_work(self):
        broker = self.resources["Broker"]["Properties"]
        for flag in ("TransitEncryptionEnabled", "AtRestEncryptionEnabled", "AutomaticFailoverEnabled", "MultiAZEnabled"):
            self.assertTrue(broker[flag])
        self.assertEqual(broker["NumCacheClusters"], 2)
        self.assertEqual(broker["ClusterMode"], "disabled")
        self.assertIn("AuthToken", broker)
        self.assertEqual(self.resources["BrokerParameters"]["Properties"]["Properties"]["maxmemory-policy"], "noeviction")

    def test_successful_data_is_retained_but_failed_new_creations_can_rollback(self):
        for name in ("Database", "Broker", "Media", "BrokerSecret"):
            self.assertEqual(self.resources[name]["DeletionPolicy"], "RetainExceptOnCreate")
            self.assertEqual(self.resources[name]["UpdateReplacePolicy"], "Retain")
        self.assertTrue(self.resources["Media"]["Properties"]["Encrypted"])

    def test_media_mount_has_no_anonymous_allow_or_root_access(self):
        policy = self.resources['Media']['Properties']['FileSystemPolicy']['Statement']
        self.assertTrue(all(statement['Effect'] == 'Deny' for statement in policy))
        media = yaml.load(Path(__file__).with_name('media-access.yaml').read_text(), Loader=Loader)
        statement = media['Resources']['IdentityPolicy']['Properties']['PolicyDocument']['Statement'][0]
        self.assertEqual(set(statement['Action']), {'elasticfilesystem:ClientMount', 'elasticfilesystem:ClientWrite'})
        self.assertEqual(statement['Condition']['Bool']['aws:SecureTransport'], 'true')
        self.assertIn('elasticfilesystem:AccessPointArn', statement['Condition']['StringEquals'])

    def test_application_credentials_cannot_administer_aws_or_read_other_queues(self):
        app = yaml.load(Path(__file__).with_name('application-access.yaml').read_text(), Loader=Loader)
        resources = app['Resources']
        for name, parameter in [('EncryptionPolicy', 'ExistingConfigurationKeyArn'),
                                ('IngestPolicy', 'ExistingIngestQueueArn')]:
            statement = resources[name]['Properties']['PolicyDocument']['Statement'][0]
            self.assertEqual(statement['Resource'], {'Ref': parameter})
            self.assertTrue(all('*' not in action for action in statement['Action']))
        self.assertNotIn('sqs:SendMessage', resources['IngestPolicy']['Properties']['PolicyDocument']['Statement'][0]['Action'])


if __name__ == "__main__":
    unittest.main()
