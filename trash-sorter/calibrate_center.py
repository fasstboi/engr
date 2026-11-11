"""Interactive level-tray calibration. Requires center_calibration.ino, not sorter firmware."""
import argparse
import json
import os
import time
from datetime import datetime
from pathlib import Path
from arduino import detect_port

ROOT = Path(__file__).resolve().parent
LOW_US, HIGH_US = 1300, 1700

def requested_pulse(text, current):
    if text in ('+', '-'):
        return current + (5 if text == '+' else -5)
    if text in ('++', '--'):
        return current + (20 if text == '++' else -20)
    if text in ('+1', '-1'):
        return current + int(text)
    if text == 'reset':
        return 1500
    if text.isdigit():
        return int(text)
    raise ValueError('Use +, -, ++, --, +1, -1, a pulse value, reset, save, or q')

def wait_for(connection, expected, seconds):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        line = connection.read_until(b'\n', 128).decode('ascii', errors='replace').strip()
        if line == expected:
            return
        if line in ('BUSY', 'INVALID', 'RANGE'):
            raise RuntimeError('Arduino rejected command: ' + line)
    raise TimeoutError(f'No {expected}; stopped without retrying. Check calibration firmware/connection.')

def send(connection, text):
    data = (text + '\n').encode('ascii')
    if connection.write(data) != len(data):
        raise RuntimeError('Incomplete serial write; no retry')

def set_pulse(connection, pulse):
    if not LOW_US <= pulse <= HIGH_US:
        raise ValueError(f'Calibration range is {LOW_US}–{HIGH_US} us')
    send(connection, f'SET {pulse}')
    wait_for(connection, f'CAL_DONE {pulse}', 6)

def main():
    from dotenv import load_dotenv
    import serial
    from serial.tools import list_ports
    load_dotenv(ROOT / '.env')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', help='Override automatic Arduino detection')
    parser.add_argument('--list', action='store_true', help='List ports without opening hardware')
    args = parser.parse_args()
    if args.list:
        for port in list_ports.comports():
            print(port.device, '-', port.description)
        return 0
    connection = None
    try:
        port = args.port or os.getenv('ARDUINO_PORT', '').strip() or detect_port(list_ports.comports())
        print('Use an unloaded tray. Opening USB may reset the servo to 1500 us.')
        connection = serial.Serial(port, 115200, timeout=0.1, write_timeout=1)
        # Allow the Uno/Nano bootloader to finish without sending any movement.
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            if connection.read_until(b'\n', 128).strip() == b'CAL_READY':
                break
        connection.reset_input_buffer()
        send(connection, 'PING')
        wait_for(connection, 'CAL_PONG', 2)
        current = 1500
        set_pulse(connection, current)
        print('Adjust until the tray is level (use a bubble level).')
        print('+ / -: 5 us | ++ / --: 20 us | +1 / -1: 1 us | number: exact us')
        print('reset: 1500 us | save: write result and exit | q: exit without saving')
        while True:
            text = input(f'{current} us (offset {current - 1500:+d} us)> ').strip().lower()
            if text == 'q':
                return 0
            if text == 'save':
                result = {'center_us': current, 'offset_us': current - 1500,
                          'timestamp': datetime.now().astimezone().isoformat(), 'port': port}
                path = ROOT / 'logs' / 'center_calibration.json'
                path.parent.mkdir(exist_ok=True)
                path.write_text(json.dumps(result, indent=2) + '\n')
                print(f'SEND THIS: CENTER_US={current}, OFFSET_US={current - 1500:+d}')
                print('Saved:', path)
                print('Sorter firmware is unchanged. Send the values before re-uploading it.')
                return 0
            try:
                target = requested_pulse(text, current)
                if not LOW_US <= target <= HIGH_US:
                    raise ValueError(f'Keep calibration between {LOW_US} and {HIGH_US} us')
            except ValueError as exc:
                print(exc)
                continue
            set_pulse(connection, target)
            current = target  # Update only after matching firmware acknowledgment.
    except (KeyboardInterrupt, EOFError):
        print('\nExited without saving.')
    except Exception as exc:
        print('Calibration stopped:', exc)
        return 1
    finally:
        if connection is not None:
            connection.close()
            print('Servo holds its last position while powered; reset/re-upload returns to firmware startup position.')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
