"""Interactive servo test. Does not import Gemini, OpenCV, or API configuration."""
import argparse
import logging
from arduino import Arduino

def main():
    from dotenv import load_dotenv
    from pathlib import Path
    load_dotenv(Path(__file__).resolve().parent / '.env')
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', help='Override automatic port detection')
    parser.add_argument('--list', action='store_true', help='List ports without opening or moving anything')
    args = parser.parse_args()
    if args.list:
        from serial.tools import list_ports
        for port in list_ports.comports():
            print(port.device, '-', port.description)
        return
    logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')
    link = Arduino(port=args.port)
    print('Unloaded test: L=LEFT, R=RIGHT, C=CENTER, Q=quit (press Enter).')
    try:
        while True:
            key = input('Servo> ').strip().upper()
            if key == 'Q':
                break
            command = {'L': 'LEFT', 'R': 'RIGHT', 'C': 'CENTER'}.get(key)
            if command and not link.move(command):
                print('Stopped after communication failure. Check hardware before restarting.')
                break
    except (EOFError, KeyboardInterrupt):
        print('\nStopped. Firmware finishes any in-flight move and centers locally.')
    finally:
        link.close()

if __name__ == '__main__':
    main()
