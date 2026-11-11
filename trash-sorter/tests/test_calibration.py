import unittest
from unittest.mock import Mock, patch
from calibrate_center import requested_pulse, set_pulse

class CalibrationTests(unittest.TestCase):
    def test_adjustments(self):
        for text, value in [('+',1505),('-',1495),('++',1520),('--',1480),
                            ('+1',1501),('-1',1499),('1523',1523),('reset',1500)]:
            self.assertEqual(requested_pulse(text,1500),value)
        with self.assertRaises(ValueError):
            requested_pulse('invalid',1500)

    def test_limits_reject_without_writing(self):
        connection=Mock()
        for pulse in (1299,1701):
            with self.assertRaises(ValueError):
                set_pulse(connection,pulse)
        connection.write.assert_not_called()

    def test_exact_ack_required(self):
        connection=Mock()
        connection.write.side_effect=lambda data:len(data)
        connection.read_until.side_effect=[b'CAL_DONE 1500\n', b'CAL_DONE 1510\n']
        set_pulse(connection,1510)
        connection.write.assert_called_once_with(b'SET 1510\n')

    def test_timeout_does_not_repeat(self):
        connection=Mock()
        connection.write.side_effect=lambda data:len(data)
        with patch('calibrate_center.time.monotonic',side_effect=[0,7]):
            with self.assertRaises(TimeoutError):
                set_pulse(connection,1501)
        connection.write.assert_called_once()
