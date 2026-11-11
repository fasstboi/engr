import unittest
from unittest.mock import Mock, patch
from classifier import Classifier, retry_delay

class LimitTests(unittest.TestCase):
    def test_structured_retry_delay_and_malformed_data(self):
        error = RuntimeError()
        error.details = {'error': {'details': [{'@type': 'type.googleapis.com/google.rpc.RetryInfo', 'retryDelay': '90.5s'}]}}
        self.assertEqual(retry_delay(error, 60), 90.5)
        error.details = {'error': {'details': [None, {'@type': 'google.rpc.RetryInfo', 'retryDelay': 'nonsense'}]}}
        self.assertEqual(retry_delay(error, 60), 60)

    def test_429_503_do_not_retry_and_block_during_cooldown(self):
        for code, delay in ((429, 60), (503, 15)):
            classifier = Classifier.__new__(Classifier)
            classifier.types = Mock()
            classifier.client = Mock()
            classifier.model, classifier.rules = 'test', 'test'
            error = RuntimeError('private provider data')
            error.code = code
            classifier.client.models.generate_content.side_effect = error
            with patch('classifier.time.monotonic', return_value=100):
                result = classifier.classify(b'jpeg')
                self.assertIn(f'HTTP {code}', result.error)
                self.assertNotIn('private provider data', result.error)
                self.assertEqual(classifier.retry_after, 100 + delay)
                blocked = classifier.classify(b'jpeg')
                self.assertIn('no API request sent', blocked.error)
                classifier.client.models.generate_content.assert_called_once()
