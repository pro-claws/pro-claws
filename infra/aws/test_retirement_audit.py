import unittest
from datetime import datetime, timezone
from retirement_audit import traffic_counts


class TrafficTests(unittest.TestCase):
    def test_counts_boundaries_without_disclosing_request_or_identity(self):
        rows = [
            'sensitive-client [28/Oct/2026:20:30:00 -0400] "GET /private?token=secret HTTP/1.1" 200',
            'other [28/Oct/2026:18:00:00 -0400] "GET /older HTTP/1.1" 200',
            'old [26/Oct/2026:18:00:00 -0400] "GET /old HTTP/1.1" 200',
            'future [29/Oct/2026:18:00:00 -0400] "GET /future HTTP/1.1" 200',
        ]
        result = traffic_counts(rows, datetime(2026, 10, 29, 1, tzinfo=timezone.utc))
        self.assertEqual(result['requests_last_hour'], 1)
        self.assertEqual(result['requests_last_24h'], 2)
        self.assertNotIn('secret', str(result))
        self.assertNotIn('sensitive-client', str(result))

    def test_malformed_timestamps_cannot_be_treated_as_zero_traffic(self):
        result = traffic_counts(['broken', '[bad date] GET /'],
                                datetime.now(timezone.utc))
        self.assertEqual(result['unparseable_lines'], 2)
        self.assertIsNone(result['latest_request_utc'])


if __name__ == '__main__':
    unittest.main()
