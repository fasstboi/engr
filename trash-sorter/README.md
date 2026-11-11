# AI Trash and Recycling Sorter — Phase 1

Python 3 camera prototype for macOS, with portable modules for later Linux deployment. No Arduino, servo, serial library, web app, or continuous image submission is required. The official Google Gen AI SDK sends one JPEG per accepted Space trigger. Preview stays responsive during the request. Busy triggers are dropped, never queued; automatic API retries are disabled.

## macOS setup

Use Python 3.11 or newer (3.12 recommended). If needed, install Python from https://www.python.org/downloads/macos/ . Extract this project somewhere writable, then open Terminal in its folder:

```sh
cd ~/Downloads/trash-sorter
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
cp .env.example .env
open -e .env
```

Set `GEMINI_API_KEY` to a key obtained through https://aistudio.google.com/apikey and save the file. Never commit or share `.env`. Existing environment variables override `.env`. Optionally set `RECYCLING_RULES` to the materials actually accepted at your school; without local rules the prompt uses a typical two-bin prototype policy. Images are sent to Google only on a capture trigger.

```sh
python main.py
```

Allow camera access for Terminal/your IDE under **System Settings → Privacy & Security → Camera**. Restart the terminal if permissions change. Click the preview window so it has keyboard focus.

1. Place one item on the tray with good lighting.
2. Tap and release **Space**. The latest frame is compressed to JPEG, saved under `captures/`, and sent to Gemini once.
3. Read TRASH, RECYCLING, or UNSURE-TRASH and actual API/total time in Terminal.
4. Wait for the preview to show SPACE again, then test another item.
5. Press **Q**, close the preview, or use Ctrl+C to exit. The camera closes immediately; an in-flight API request is allowed to finish and log before the process exits.

OpenCV exposes key events rather than reliable key-up events. A 350 ms repeat-gap filter plus 800 ms cooldown suppresses typical held-key repeats; **tap Space once per object**. Exact physical key-down/key-up guarantees across all OS repeat settings would require a native keyboard listener. Busy requests are always rejected.

## Configuration

All settings are in `.env.example`. Camera index defaults to 0; try 1 or 2 for a USB camera. Requested dimensions may be adjusted by the camera driver. Images are resized to at most 1280 pixels on the longest side and encoded at JPEG quality 85. `SAVE_IMAGES=false` skips disk images (CSV filename is empty); default is true.

`API_TIMEOUT_SECONDS=15` configures the SDK HTTP timeout in milliseconds internally. This is a network timeout, not a strict wall-clock deadline. No automatic retry is made after timeouts, quota errors, or failures; the next deliberate Space press can try again. A response validation or API error produces UNSURE-TRASH with error status; valid UNSURE-TRASH is a successful uncertain classification. The five-second goal is measured, not guaranteed.

Only `TRIGGER_MODE=keyboard` and `PREVIEW_ENABLED=true` are implemented in Phase 1. Serial fields are reserved and unused. No headless support is claimed yet. `GEMINI_MODEL` defaults to the specified `gemini-3.5-flash`; model availability, free-tier eligibility, and quotas depend on your account and can change. Choose another image/structured-output capable model if necessary.

## Logs and troubleshooting

`logs/classifications.csv` records capture timestamp with timezone, image path, classification, API latency, total processing time, success/error, and error message. Total time ends at classification (does not include later CSV writing). `logs/app.log` records runtime events. Captures, logs, credentials, and virtual environments are gitignored. No automatic retention cleanup is implemented.

- Missing key: edit `.env` or export GEMINI_API_KEY.
- Camera unavailable: close FaceTime/Zoom, check permissions and CAMERA_INDEX. A disconnected camera exits with an error and releases resources; reconnect and restart. Automatic reconnection belongs to Phase 4.
- HTTP 429: wait and check API quota. Authentication/model errors: check key, model and account availability. Requests are not silently retried.
- Invalid/blocked/missing JSON: logged as UNSURE-TRASH/error; no action is taken.
- Log/disk failures stop operation rather than silently lose engineering data.

## Automated checks

Run from the project directory:

```sh
python -m unittest discover -s tests -v
python -m compileall -q . -x '/.venv/'
```

Tests use fake time and mocked API calls; they do not access your camera or spend API quota. They cover strict validation, API failure behavior, repeat suppression, cooldown, and dropping busy triggers.

## Manual Phase 1 acceptance check

Start on macOS, confirm live preview, tap Space, confirm exactly one new JPEG and one CSV row, and inspect the terminal category and timing. Repeat with several objects without restarting. Test an empty tray (expect UNSURE-TRASH), try holding Space to check repeat suppression on your OS, and verify busy presses do not queue requests. Verify Q releases the camera. Test a bad API key to confirm UNSURE-TRASH/error logging and continued operation, then restore your key and restart. These camera/API checks require real hardware and credentials and have not been performed automatically.

## Architecture and next phases

- `main.py`: coordinates preview, capture, single background request, logging, shutdown.
- `camera.py`: persistent OpenCV access, capture, JPEG compression, saving.
- `classifier.py`: official Gemini SDK, structured output, strict validation, timing and failure handling.
- `triggers.py`: keyboard debounce/repeat suppression; accepts a busy flag.
- `config.py`: environment configuration and validation.
- `arduino.py`: documented extension point; no hardware implementation in Phase 1.

**Phase 2:** add pyserial, a reconnecting serial reader, and an Arduino sketch with INPUT_PULLUP and nonblocking debouncing that emits one newline-terminated CAPTURE per button press. Factor the current capture submission block into a shared function for Space and serial events. Feed both through the same busy guard; discard events received while processing rather than queueing them. Enable serial/both trigger modes while keeping keyboard mode independent of hardware.

**Phase 3:** implement acknowledged T/R/C protocol with timeouts. Arduino owns configurable servo positions and local tilt/return timing. Keep the coordinator busy through the entire movement and center acknowledgment. UNSURE-TRASH/errors keep the tray centered. Add local Arduino watchdog/recovery before enabling motion.

**Phase 4:** add serial-only headless execution, camera/serial reconnection with backoff, Linux device configuration and permissions, rotating logs, and a systemd service with environment credentials. Keep the same classification module. Do not run the current GUI application as a headless boot service.

SDK reference: https://googleapis.github.io/python-genai/

## Model availability troubleshooting

The original gemini-2.5-flash setting returned HTTP 404 in this project. The configuration now uses gemini-3.5-flash, verified with a saved capture. Run `python list_models.py` to list account-visible generation models. Listing alone does not guarantee a model will accept generation requests. HTTP 503 indicates temporary provider unavailability; try a new deliberate capture later. No automatic retry or overlapping request is made. An exported GEMINI_MODEL overrides .env; run `unset GEMINI_MODEL` if the terminal still shows an old model.

## Updated classification and preview

The prompt uses an explicit default policy for common recyclables and trash rather than requiring proof of local acceptance. RECYCLING_RULES can override that policy for your school. It is a prototype assumption, not verified municipal guidance. UNSURE-TRASH is reserved for genuine visual ambiguity, empty trays, conflicting foreground items, or special-handling waste. Retest with labeled objects to measure actual accuracy; fewer UNSURE-TRASH responses alone does not prove better accuracy.

The preview keeps the latest category, API seconds, and total seconds visible until another result arrives. While processing it shows elapsed time and labels the previous answer as Last result. API failures show UNSURE-TRASH (ERROR) rather than appearing to be a successful uncertain prediction.

After each capture, the preview holds the captured frame during processing, then displays its result and timing for five seconds after completion before returning to live video. Space presses during processing or the five-second display are ignored; Q still exits. The camera continues reading in the background, so the next capture uses a fresh frame. The previous result is cleared when a new capture starts.

## Feedback during the result display

While the captured image and prediction are shown during the five-second result countdown, press **Y** to confirm the prediction, or **T**, **R**, **U** to supply the actual category (TRASH, RECYCLING, UNSURE-TRASH). Uppercase works too. The screen confirms the saved feedback. You may change your answer until the countdown ends; the last answer wins. Feedback does not extend the five-second countdown. Inputs before a prediction exists or after live video resumes are ignored.

`logs/capture_feedback.csv` has one row per completed capture attempt, including a unique capture ID, image path, original prediction, API and total seconds, success/error, error details, feedback (`correct`, `incorrect`, or `unanswered`), corrected category, and feedback timestamp. The record is saved as unanswered immediately when the result arrives, including API errors; feedback updates that same row immediately. Exiting without feedback leaves it unanswered. Original predictions are preserved. Existing `logs/classifications.csv` continues to record results as before. Failed image saves are recorded with an empty image path; SAVE_IMAGES=false also produces an empty path. Feedback is evaluation data and does not automatically retrain Gemini.

## Trash fallback policy update

The current categories are TRASH, RECYCLING, and UNSURE-TRASH. Recognizable crumpled printer/notebook paper is explicitly RECYCLING. Ordinary waste with unclear recyclability defaults to TRASH. UNSURE-TRASH is reserved for images without an assessable target, severe ambiguity, and special-handling items needing manual review. API/capture failures also produce UNSURE-TRASH with error status. U feedback now selects UNSURE-TRASH. This replaces the earlier uncertainty policy above. Existing CSV rows retain their original historical labels; new results use the new labels.

## Serial servo integration (implemented)

See [HARDWARE.md](HARDWARE.md) for firmware upload, wiring, exact install/run commands, port selection, and unloaded L/R/C testing. This supersedes the earlier future-phase servo notes. `ARDUINO_ENABLED=true` is the default; false preserves camera-only operation. Classifier prompts, image handling, timing and feedback logs are unchanged.

## Gemini HTTP 429 / 503

429 means a rate/quota limit, not object uncertainty. Check your API project's active model limits and usage in Google AI Studio; daily exhaustion or a zero free-tier allocation cannot be resolved by a short retry delay. 503 means the service is temporarily overloaded/unavailable. The application now reports these separately and pauses new captures for at least 60 seconds (429) or 15 seconds (503), honoring a longer structured RetryInfo delay when present. A live countdown appears after the result display. There is no automatic API retry, no automatic model switch, and no repeat servo movement. A new deliberate Space press is required after cooldown. API errors still center the tray and are recorded with error status. Changing the prompt does not resolve these service errors.
