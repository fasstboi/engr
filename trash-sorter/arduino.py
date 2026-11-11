"""Single-command USB serial link. Never retries a movement after failure."""
import logging
import os
import threading
import time


def command_for_result(classification, status='success'):
    if status != 'success':
        return 'CENTER'
    return {'RECYCLING': 'LEFT', 'TRASH': 'RIGHT'}.get(classification, 'CENTER')


def detect_port(ports):
    candidates = []
    for port in ports:
        text = ' '.join(str(getattr(port, field, '') or '') for field in ('device', 'description', 'manufacturer')).lower()
        if ('arduino' in text or 'usbmodem' in text or 'usbserial' in text or
                getattr(port, 'vid', None) in {0x2341, 0x2A03, 0x1A86, 0x0403, 0x10C4}):
            candidates.append(port.device)
    if len(candidates) != 1:
        raise RuntimeError('Expected one Arduino serial port; found ' + str(candidates) +
                           '. Set ARDUINO_PORT explicitly (python servo_test.py --list).')
    return candidates[0]


class Arduino:
    def __init__(self, port=None, baud=None, timeout=None):
        self.port = port if port is not None else os.getenv('ARDUINO_PORT', '').strip()
        self.baud = int(baud if baud is not None else os.getenv('ARDUINO_BAUD', '115200'))
        self.timeout = float(timeout if timeout is not None else os.getenv('ARDUINO_TIMEOUT_SECONDS', '7'))
        if self.timeout < 3:
            raise ValueError('ARDUINO_TIMEOUT_SECONDS must be at least 3')
        self.connection = None
        self.lock = threading.Lock()
        self.failed = False

    def _line(self):
        # Bound read size as well as the serial read timeout.
        return self.connection.read_until(b'\n', 128).decode('ascii', errors='replace').strip()

    def _write(self, command):
        data = (command + '\n').encode('ascii')
        if self.connection.write(data) != len(data):
            raise RuntimeError('Incomplete serial write')

    def _connect(self):
        import serial
        from serial.tools import list_ports
        port = self.port or detect_port(list_ports.comports())
        self.connection = serial.Serial(port, self.baud, timeout=0.1, write_timeout=1)
        logging.info('Arduino: opened %s; waiting for USB reset...', port)
        # Uno/Nano reset on open. Firmware centers locally, then emits READY.
        deadline = time.monotonic() + 3.0
        while time.monotonic() < deadline:
            if self._line() == 'READY':
                break
        self.connection.reset_input_buffer()
        self._write('PING')
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline:
            line = self._line()
            if line == 'PONG':
                logging.info('Arduino: PONG; serial firmware ready')
                return
            if line == 'BUSY':
                raise RuntimeError('Arduino is already moving; refusing another command')
        raise TimeoutError('No PONG. Upload serial firmware and close Serial Monitor.')

    def move(self, command):
        if command not in ('LEFT', 'RIGHT', 'CENTER'):
            raise ValueError('Invalid movement command')
        if not self.lock.acquire(blocking=False):
            logging.error('Arduino: movement already in progress; command discarded')
            return False
        try:
            if self.failed:
                logging.error('Arduino disabled after communication failure; restart app after checking hardware')
                return False
            if self.connection is None:
                self._connect()
            self.connection.reset_input_buffer()
            self._write(command)  # Exactly once. Timeout may mean it already moved.
            logging.info('Arduino: sent %s', command)
            deadline = time.monotonic() + self.timeout
            acknowledged = False
            while time.monotonic() < deadline:
                line = self._line()
                if line == 'ACK ' + command:
                    acknowledged = True
                elif line == 'DONE' and acknowledged:
                    logging.info('Arduino: DONE; tray centered')
                    return True
                elif line in ('READY', 'BUSY', 'INVALID'):
                    raise RuntimeError('Unexpected Arduino response: ' + line)
            raise TimeoutError('Timed out waiting for ACK/DONE; movement will NOT be repeated')
        except Exception as exc:
            self.failed = True
            logging.error('Arduino communication failed: %s. No automatic movement retry; check hardware and restart.', exc)
            self.close()
            return False
        finally:
            self.lock.release()

    def close(self):
        if self.connection is not None:
            try:
                self.connection.close()
            except Exception:
                pass
            self.connection = None
