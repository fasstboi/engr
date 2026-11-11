import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch
from arduino import Arduino, command_for_result, detect_port

class ArduinoTests(unittest.TestCase):
    def test_mapping_fails_centered(self):
        self.assertEqual(command_for_result('RECYCLING'), 'LEFT')
        self.assertEqual(command_for_result('TRASH'), 'RIGHT')
        for category in ('UNSURE', 'UNSURE-TRASH', '', 'unknown'):
            self.assertEqual(command_for_result(category), 'CENTER')
        self.assertEqual(command_for_result('TRASH', 'error'), 'CENTER')
        self.assertEqual(command_for_result('RECYCLING', 'error'), 'CENTER')

    def test_detection_requires_unique_candidate(self):
        board = SimpleNamespace(device='/dev/cu.usbmodem1', description='Arduino', vid=0x2341)
        self.assertEqual(detect_port([board]), board.device)
        for ports in ([], [board, board]):
            with self.assertRaises(RuntimeError):
                detect_port(ports)

    def link(self):
        link = Arduino(port='fake', baud=115200, timeout=7)
        link.connection = Mock()
        link.connection.write.side_effect = lambda data: len(data)
        return link

    def test_ack_and_done_required(self):
        link = self.link()
        with patch.object(link, '_line', side_effect=['DONE', 'ACK LEFT', 'DONE']):
            self.assertTrue(link.move('LEFT'))
        link.connection.write.assert_called_once_with(b'LEFT\n')

    def test_timeout_never_retries_and_latches_failure(self):
        link = self.link()
        connection = link.connection
        with patch.object(link, '_line', return_value=''), patch('arduino.time.monotonic', side_effect=[0, 0, 8]):
            self.assertFalse(link.move('RIGHT'))
        self.assertFalse(link.move('RIGHT'))
        connection.write.assert_called_once_with(b'RIGHT\n')
        connection.close.assert_called_once()

    def test_disconnect_does_not_escape_to_app(self):
        link = self.link()
        link.connection.write.side_effect = OSError('disconnected')
        self.assertFalse(link.move('CENTER'))
        self.assertTrue(link.failed)

    def test_busy_and_reset_abort_without_retry(self):
        for response in ('BUSY', 'READY', 'INVALID'):
            link = self.link()
            connection = link.connection
            with patch.object(link, '_line', return_value=response):
                self.assertFalse(link.move('LEFT'))
            connection.write.assert_called_once()

    def test_concurrent_command_rejected(self):
        link = self.link()
        link.lock.acquire()
        try:
            self.assertFalse(link.move('RIGHT'))
            link.connection.write.assert_not_called()
        finally:
            link.lock.release()
