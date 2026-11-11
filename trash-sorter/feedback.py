"""Persistent capture records and user corrections; independent of camera/API."""
import csv
import os
import tempfile
from datetime import datetime
from pathlib import Path
from uuid import uuid4

BASE_FIELDS = ['timestamp', 'image_filename', 'classification', 'api_latency_seconds',
               'total_processing_seconds', 'status', 'error_message']
FIELDS = ['capture_id'] + BASE_FIELDS + ['feedback', 'corrected_category', 'feedback_timestamp']

def correction_for_key(key, prediction):
    if key < 0 or key > 255:
        return None
    letter = chr(key).lower()
    if letter == 'y':
        return prediction
    return {'t': 'TRASH', 'r': 'RECYCLING', 'u': 'UNSURE-TRASH'}.get(letter)

class CaptureLog:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def add(self, result):
        capture_id = uuid4().hex
        row = dict(zip(BASE_FIELDS, result))
        row.update(capture_id=capture_id, feedback='unanswered', corrected_category='', feedback_timestamp='')
        new = not self.path.exists() or self.path.stat().st_size == 0
        with self.path.open('a', newline='', encoding='utf-8') as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDS)
            if new:
                writer.writeheader()
            writer.writerow(row)
            handle.flush()
            os.fsync(handle.fileno())
        return capture_id

    def update(self, capture_id, category):
        if category not in ('TRASH', 'RECYCLING', 'UNSURE-TRASH'):
            raise ValueError('Invalid corrected category')
        with self.path.open(newline='', encoding='utf-8') as handle:
            rows = list(csv.DictReader(handle))
        row = next((row for row in rows if row['capture_id'] == capture_id), None)
        if row is None:
            raise ValueError('Unknown capture ID')
        row['feedback'] = 'correct' if row['classification'] == category else 'incorrect'
        row['corrected_category'] = category
        row['feedback_timestamp'] = datetime.now().astimezone().isoformat(timespec='milliseconds')
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', dir=self.path.parent, newline='', encoding='utf-8', delete=False) as handle:
                temporary = Path(handle.name)
                writer = csv.DictWriter(handle, fieldnames=FIELDS)
                writer.writeheader()
                writer.writerows(rows)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        return row['feedback']
