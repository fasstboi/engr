import csv
import tempfile
import unittest
from pathlib import Path
from feedback import CaptureLog, correction_for_key

class FeedbackTests(unittest.TestCase):
    def test_key_mapping(self):
        for key, expected in [('y', 'RECYCLING'), ('Y', 'RECYCLING'), ('t', 'TRASH'),
                              ('R', 'RECYCLING'), ('u', 'UNSURE-TRASH')]:
            self.assertEqual(correction_for_key(ord(key), 'RECYCLING'), expected)
        for key in (-1, ord('q'), ord(' '), 500):
            self.assertIsNone(correction_for_key(key, 'TRASH'))

    def test_persistent_capture_feedback_and_corrections(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'capture_feedback.csv'
            log = CaptureLog(path)
            row = ['now', 'captures/test.jpg', 'RECYCLING', '1.2', '1.3', 'success', '']
            first = log.add(row)
            second = log.add(row)
            self.assertNotEqual(first, second)
            self.assertEqual(log.update(first, 'TRASH'), 'incorrect')
            # Feedback can be changed while the image remains displayed.
            self.assertEqual(log.update(first, 'RECYCLING'), 'correct')
            with path.open(newline='') as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0]['classification'], 'RECYCLING')
            self.assertEqual(rows[0]['image_filename'], 'captures/test.jpg')
            self.assertEqual(rows[0]['feedback'], 'correct')
            self.assertEqual(rows[0]['corrected_category'], 'RECYCLING')
            self.assertTrue(rows[0]['feedback_timestamp'])
            self.assertEqual(rows[1]['feedback'], 'unanswered')
            self.assertEqual(rows[1]['corrected_category'], '')
            with self.assertRaises(ValueError):
                log.update(first, 'INVALID')
            with self.assertRaises(ValueError):
                log.update('missing', 'TRASH')
