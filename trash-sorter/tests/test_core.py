import json
import unittest
from unittest.mock import Mock
from classifier import Classifier, validate_response
from triggers import KeyboardTrigger

class ValidationTests(unittest.TestCase):
    def test_categories(self):
        for category in ('TRASH', 'RECYCLING', 'UNSURE-TRASH'):
            self.assertEqual(validate_response(json.dumps({'classification': category})), category)

    def test_invalid_response_fails_closed(self):
        for text in (None, '', 'TRASH', '[]', 'null', '{}', '{"classification": []}', '{"classification":"UNSURE"}',
                     '{"classification":"trash"}', '{"classification":"COMPOST"}',
                     '{"classification":"TRASH","extra":1}'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                validate_response(text)

    def test_request_failure_returns_unsure_once(self):
        classifier = Classifier.__new__(Classifier)
        classifier.types = Mock()
        classifier.client = Mock()
        classifier.model = 'test-model'
        classifier.rules = 'test rules'
        classifier.client.models.generate_content.side_effect = TimeoutError()
        result = classifier.classify(b'jpeg')
        self.assertEqual(result.classification, 'UNSURE-TRASH')
        self.assertTrue(result.error)
        self.assertGreaterEqual(result.latency, 0)
        classifier.client.models.generate_content.assert_called_once()

class ModelErrorTests(unittest.TestCase):
    def test_404_has_actionable_model_diagnostic(self):
        classifier = Classifier.__new__(Classifier)
        classifier.types = Mock()
        classifier.client = Mock()
        classifier.model, classifier.rules = 'missing-model', 'test rules'
        error = RuntimeError('provider details must not be logged')
        error.code = 404
        classifier.client.models.generate_content.side_effect = error
        result = classifier.classify(b'jpeg')
        self.assertEqual(result.classification, 'UNSURE-TRASH')
        self.assertIn('missing-model', result.error)
        self.assertIn('GEMINI_MODEL=gemini-3.5-flash', result.error)
        self.assertNotIn('provider details', result.error)
        classifier.client.models.generate_content.assert_called_once()

class TriggerTests(unittest.TestCase):
    def setUp(self):
        self.now = 0
        self.trigger = KeyboardTrigger(clock=lambda: self.now)

    def test_only_space(self):
        for key in (-1, ord('a'), ord('q')):
            self.assertFalse(self.trigger.capture_requested(key))
        self.assertTrue(self.trigger.capture_requested(32))

    def test_held_space_does_not_repeat(self):
        self.assertTrue(self.trigger.capture_requested(32))
        for tick in range(1, 101):
            self.now = tick * 0.1
            self.assertFalse(self.trigger.capture_requested(32))
        self.now += 1
        self.assertTrue(self.trigger.capture_requested(32))

    def test_busy_press_is_dropped_not_queued(self):
        self.assertFalse(self.trigger.capture_requested(32, busy=True))
        self.now = 0.1
        self.assertFalse(self.trigger.capture_requested(32))
        self.assertFalse(self.trigger.capture_requested(-1))
        self.now = 1
        self.assertTrue(self.trigger.capture_requested(32))

    def test_cooldown(self):
        self.assertTrue(self.trigger.capture_requested(32))
        self.now = 0.5
        self.assertFalse(self.trigger.capture_requested(32))
        self.now = 1.5
        self.assertTrue(self.trigger.capture_requested(32))

if __name__ == '__main__':
    unittest.main()
