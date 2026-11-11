"""Phase 1 coordinator. Camera/GUI on main thread; one background API request."""
import csv
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import cv2
from config import Config, ROOT
from camera import Camera
from classifier import Classifier
from triggers import KeyboardTrigger
from feedback import CaptureLog, correction_for_key
from arduino import Arduino, command_for_result

FIELDS = ['timestamp', 'image_filename', 'classification', 'api_latency_seconds',
          'total_processing_seconds', 'status', 'error_message']

def process(classifier, jpeg, timestamp, filename, started):
    result = classifier.classify(jpeg)
    return [timestamp, filename, result.classification, f'{result.latency:.3f}',
            f'{time.perf_counter()-started:.3f}', 'error' if result.error else 'success', result.error]

def record(row, capture_log):
    path = ROOT / 'logs' / 'classifications.csv'
    new = not path.exists() or path.stat().st_size == 0
    with path.open('a', newline='', encoding='utf-8') as handle:
        writer = csv.writer(handle)
        if new:
            writer.writerow(FIELDS)
        writer.writerow(row)
    capture_id = capture_log.add(row)
    logging.info('Result: %s | API: %ss | total: %ss | %s | %s', row[2], row[3], row[4], row[5], row[6])
    return capture_id

def draw_status(frame, busy, latest, started=None):
    """Draw a persistent result panel; raw camera frames remain unmodified."""
    height, width = frame.shape[:2]
    scale = min(1.0, width / 800)
    panel_height = min(height, int(150 * scale))
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (width, panel_height), (20, 20, 20), -1)
    cv2.addWeighted(overlay, 0.85, frame, 0.15, 0, frame)
    lines = [('SPACE: capture | Q: quit', (240, 240, 240))]
    if busy:
        elapsed = time.perf_counter() - started if started is not None else 0
        lines.append((f'Processing new capture... {elapsed:.1f}s', (0, 220, 255)))
    elif latest is None:
        lines.append(('Ready - place one item on the tray', (240, 240, 240)))
    if latest is not None:
        category, api, total, status = latest[2:6]
        color = (80, 230, 80) if category == 'RECYCLING' else ((80, 140, 255) if category == 'TRASH' else (0, 220, 255))
        prefix = 'Last result' if busy else 'Result'
        label = f'{prefix}: {category}' + (' (ERROR)' if status == 'error' else '')
        lines.append((label, color))
        lines.append((f'API: {float(api):.2f}s | Total: {float(total):.2f}s', (240, 240, 240)))
    for i, (text, color) in enumerate(lines):
        cv2.putText(frame, text, (int(16 * scale), int((28 + i * 34) * scale)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.65 * scale, color, max(1, round(2 * scale)), cv2.LINE_AA)
    return frame

def main():
    (ROOT / 'logs').mkdir(exist_ok=True)
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s',
        handlers=[logging.StreamHandler(), logging.FileHandler(ROOT / 'logs' / 'app.log')])
    camera = classifier = executor = pending = None
    servo = servo_executor = movement = None
    latest = request_started = None
    captured_frame = None
    reset_at = None
    latest_id = None
    feedback_label = 'No feedback yet'
    capture_log = CaptureLog(ROOT / 'logs' / 'capture_feedback.csv')
    try:
        config = Config()
        if config.arduino_enabled:
            servo = Arduino()
            servo_executor = ThreadPoolExecutor(max_workers=1)
        classifier = Classifier(config)
        camera = Camera(config)
        executor = ThreadPoolExecutor(max_workers=1)
        trigger = KeyboardTrigger()
        logging.info('Ready. Focus preview: SPACE captures; Q exits. Arduino control: %s', config.arduino_enabled)
        while True:
            frame = camera.read()
            if movement is not None and movement.done():
                movement.result()
                movement = None
            cooldown = max(0.0, classifier.retry_after - time.monotonic())
            busy = pending is not None or reset_at is not None or movement is not None or cooldown > 0
            if pending is not None and pending.done():
                latest = pending.result()
                latest_id = record(latest, capture_log)
                if servo is not None:
                    movement = servo_executor.submit(servo.move, command_for_result(latest[2], latest[5]))
                pending = None
                feedback_label = 'No feedback yet'
                reset_at = time.monotonic() + 5.0
            if reset_at is not None and time.monotonic() >= reset_at:
                captured_frame = latest = request_started = reset_at = latest_id = None
            shown_frame = captured_frame if captured_frame is not None else frame
            display = draw_status(shown_frame.copy(), pending is not None, latest, request_started)
            if reset_at is not None:
                remaining = max(0.0, reset_at - time.monotonic())
                cv2.rectangle(display, (0, 0), (display.shape[1], 40), (20, 20, 20), -1)
                cv2.putText(display, f'Live preview in {remaining:.1f}s | Q: quit',
                            (12, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (240, 240, 240), 1, cv2.LINE_AA)
                # Bottom panel stays separate from classification/timing at the top.
                width, height = display.shape[1], display.shape[0]
                font_scale = min(0.60, width / 1100)
                cv2.rectangle(display, (0, max(0, height - 66)), (width, height), (20, 20, 20), -1)
                for offset, text in ((42, 'Feedback: Y=correct | T=trash | R=recycling | U=unsure-trash'),
                                     (16, feedback_label)):
                    cv2.putText(display, text, (10, height - offset), cv2.FONT_HERSHEY_SIMPLEX,
                                font_scale, (240, 240, 240), 1, cv2.LINE_AA)
            if movement is not None and reset_at is None:
                cv2.putText(display, 'Arduino busy - wait for DONE', (16, 70),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 220, 255), 2, cv2.LINE_AA)
            if cooldown > 0 and reset_at is None:
                cv2.rectangle(display, (0, 0), (display.shape[1], 40), (20, 20, 20), -1)
                cv2.putText(display, f'Gemini cooldown: {cooldown:.0f}s | Q: quit', (12, 28),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 220, 255), 1, cv2.LINE_AA)
            cv2.imshow('Trash Sorter - Phase 1', display)
            key = cv2.waitKey(1)
            if key >= 0:
                key &= 0xFF
            if key in (ord('q'), ord('Q')) or cv2.getWindowProperty('Trash Sorter - Phase 1', cv2.WND_PROP_VISIBLE) < 1:
                break
            if reset_at is not None and time.monotonic() < reset_at and latest_id is not None:
                corrected = correction_for_key(key, latest[2])
                if corrected is not None:
                    verdict = capture_log.update(latest_id, corrected)
                    feedback_label = f'Saved: {verdict.upper()} | Actual: {corrected}'
                    logging.info('Feedback for %s: %s; corrected category: %s', latest_id, verdict, corrected)
            if trigger.capture_requested(key, busy):
                started = time.perf_counter()
                request_started = started
                timestamp = datetime.now().astimezone().isoformat(timespec='milliseconds')
                try:
                    jpeg, filename = camera.capture(frame, ROOT / 'captures', config.save)
                    captured_frame = frame.copy()
                    latest = latest_id = None
                    logging.info('Captured %s; requesting Gemini...', filename or 'JPEG (saving disabled)')
                    pending = executor.submit(process, classifier, jpeg, timestamp, filename, started)
                except (OSError, RuntimeError) as exc:
                    latest = [timestamp, '', 'UNSURE-TRASH', '0.000', f'{time.perf_counter()-started:.3f}', 'error', str(exc)]
                    latest_id = record(latest, capture_log)
                    feedback_label = 'No feedback yet'
                    captured_frame = frame.copy()
                    reset_at = time.monotonic() + 5.0
    except KeyboardInterrupt:
        logging.info('Interrupted.')
    except Exception as exc:
        logging.error('%s', exc)
        return 1
    finally:
        if camera:
            camera.close()
        if pending is not None:
            logging.info('Finishing in-flight request before exit...')
            try:
                record(pending.result(), capture_log)
            except Exception as exc:
                logging.error('Pending result could not be logged: %s', type(exc).__name__)
        if executor:
            executor.shutdown(wait=True)
        if servo_executor:
            servo_executor.shutdown(wait=True)
        if servo:
            servo.close()
        if classifier:
            classifier.close()
        logging.info('Stopped; camera released.')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
