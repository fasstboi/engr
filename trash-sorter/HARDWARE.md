# Arduino servo setup and testing

The existing Gemini prompt, classification, camera capture, five-second result display, and feedback controls are unchanged. Servo control runs in a separate worker. Feedback never triggers a second movement.

## Wiring and power

Keep your present wiring: WHITE signal → D9, RED → external regulated +5 V, BLACK → external supply ground, Arduino GND → that same ground. Arduino remains powered from MacBook USB. Do not power this servo through the Arduino 5 V pin or connect external +5 V to the board's 5 V pin. Your 5 V 2 A adapter is for unloaded initial tests only: it cannot be assumed to support the supplied 2.1 A stall rating. Remove mechanical load for the first tests. Stop if the servo stalls, chatters, or the supply/board resets.

## Upload firmware

1. Quit the Python application and servo test; close Serial Monitor.
2. Open `arduino/trash_sorter/trash_sorter.ino` in Arduino IDE.
3. Select your actual Uno/Nano board and USB port under Tools. For some Nano clones the Processor setting needs ATmega328P (Old Bootloader).
4. Install the Arduino Servo library through Library Manager if missing.
5. Upload, replacing the old servo test firmware. Startup commands center, so keep the mechanism clear.
6. Optional connection check: open Serial Monitor at **115200 baud**, with **Newline** selected. Reset the board: expect READY. Send PING: expect PONG. Close Serial Monitor before Python uses the port.

Configurable constants at the top of the sketch: CENTER_US=1500, LEFT_US=944, RIGHT_US=2056, HOLD_MS=1500, STEP_US=5, STEP_MS=10, CENTER_SETTLE_MS=300. It uses `servo.attach(9, 500, 2500)` and `writeMicroseconds()`. Incremental pulses soften commanded motion; they cannot limit motor current. Adjust tilt gradually only after unloaded tests. If left/right are physically reversed, swap LEFT_US and RIGHT_US, then upload again. Increase ARDUINO_TIMEOUT_SECONDS if future movement settings take longer.

## Install dependency and test without Gemini

From your project folder (activate the same environment that already runs main.py):

```sh
cd /Users/yaz/Documents/trash/trash-sorter
# If your venv is in the parent folder:
source ../.venv/bin/activate
python -m pip install -r requirements.txt
python servo_test.py --list
python servo_test.py
```

Type **L**, **R**, or **C**, then Enter. Q + Enter exits. Opening the port may reset and center the Arduino. Python waits for startup and checks PING/PONG before sending your chosen movement. Expect ACK LEFT/RIGHT/CENTER followed by DONE. L/R gently tilt, hold 1.5 seconds after reaching the commanded pulse, return to center, settle, then report DONE. CENTER only centers and settles; it does not tilt. DONE confirms the firmware completed its timing sequence, not physical position sensing.

If auto detection reports zero/multiple candidates:

```sh
python servo_test.py --port /dev/cu.usbmodemXXXX
```

Replace that example with a real path from `--list`. USB-to-serial clones are detected by common USB vendor IDs or descriptions. Ambiguous detection deliberately does not open candidate ports. Manually selecting the correct device is required in that case.

## Run the integrated sorter

Set in `.env` (or export environment variables):

```text
ARDUINO_ENABLED=true
ARDUINO_PORT=
ARDUINO_BAUD=115200
ARDUINO_TIMEOUT_SECONDS=7
```

A blank port enables automatic detection. Set ARDUINO_PORT to your actual `/dev/cu.*` path for manual override. ARDUINO_ENABLED defaults to true. Set it to false for camera/Gemini testing without serial control. Existing environment variables override `.env`.

```sh
python main.py
```

A successful RECYCLING result sends LEFT; a successful TRASH sends RIGHT. UNSURE, UNSURE-TRASH, any unknown label, and API errors send CENTER only. Camera capture/save failures send no movement. Connection opens on the first classification that needs a command. No extra Gemini call is added. Results and five-second feedback remain available while the Arduino works. Captures are blocked until both the result display and serial operation finish. If serial takes longer than the display, live video shows an Arduino-busy message.

A physical LEFT/RIGHT movement is not repeated after a timeout, disconnect, BUSY, unexpected reset, or invalid response. That session's serial control is disabled, while camera/Gemini and feedback continue. Check the device/power/cabling, then restart the application or test to reconnect. Do not restart blindly: opening USB may reset the board and center it. The firmware completes its return-to-center autonomously if the host disconnects, as long as the Arduino/servo remain powered and working. No software command can guarantee centering after power loss or a mechanical stall.

Commands are newline-terminated uppercase LEFT, RIGHT, CENTER, PING. READY is emitted after startup centering; PING returns PONG only while idle. Movement requires matching ACK followed by DONE. BUSY rejects overlapping commands without queueing; invalid/overlong lines return INVALID with no movement.

## Verification

```sh
python -m unittest discover -s tests -v
```

Automated serial tests use mocks and never move hardware. Actual board upload and unloaded physical tests must be performed on your rig. Servo/USB errors appear in Terminal and `logs/app.log`; classification/feedback CSV schemas are preserved. No firmware upload or physical movement was performed during implementation.

References: [Arduino Servo API](https://github.com/arduino-libraries/Servo/blob/master/docs/api.md), [pySerial API](https://pyserial.readthedocs.io/en/latest/pyserial_api.html).

## Near-vertical tilt update

Both `servo_test.py` and `main.py` use the same LEFT/RIGHT commands, so re-uploading the updated firmware changes both. LEFT=944 us and RIGHT=2056 us target approximately 75 degrees either side of a level 1500 us center, based on the supplied nominal 270-degree/2000-us range. This is about 15 degrees short of vertical with direct linkage; actual angle requires checking on your mechanism. Each outward/return leg is about 1.12 seconds, plus 1.5 seconds at tilt and 0.3 seconds settling (about 4.04 seconds total); the existing 7-second movement timeout remains sufficient. Keep the tray unloaded for the first test and check clearance across the full sweep. Your 5 V 2 A supply remains limited to unloaded testing; the larger travel does not increase its current capacity.

## Find the tray's center offset

1. Quit main.py, servo_test.py, and Serial Monitor. Keep the tray unloaded.
2. Upload `arduino/center_calibration/center_calibration.ino` using Arduino IDE. This temporarily replaces the sorting firmware. It starts at 1500 us on D9 and permits only 1300–1700 us adjustments, moving 1 us per 10 ms.
3. With your Python environment active, run `python calibrate_center.py`. Port override: `python calibrate_center.py --port /dev/cu.usbmodemXXXX`. `--list` only lists ports.
4. Use a bubble level while entering `+` or `-` then Enter for 5 us nudges. `++`/`--` changes 20 us; `+1`/`-1` changes 1 us. An exact number sets that pulse; `reset` returns to 1500 us. Positive pulse changes may tilt either way depending on mounting.
5. Once level, enter `save`. Send the printed `CENTER_US=..., OFFSET_US=...` values. They are also saved to `logs/center_calibration.json`. This calibrates commanded pulse, not a measured servo angle; there is no automatic level sensing.

The tool waits for each adjustment to complete and never repeats a command on timeout. It holds the selected position after exit while powered. Opening USB, resetting, or uploading can recenter it. Main sorting constants are deliberately unchanged until you provide the measurement. Before running main.py/servo_test.py again, re-upload the sorting sketch (it still uses the old center until updated). The calibration sketch intentionally rejects the normal sort protocol.
