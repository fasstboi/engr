import os
from pathlib import Path
from dotenv import load_dotenv
ROOT = Path(__file__).resolve().parent

def boolean(name, default):
    value = os.getenv(name, default).lower()
    if value not in ('true', 'false'):
        raise ValueError(f'{name} must be true or false')
    return value == 'true'

class Config:
    def __init__(self):
        load_dotenv(ROOT / '.env')
        self.api_key = os.getenv('GEMINI_API_KEY', '').strip()
        if not self.api_key:
            raise ValueError('Set GEMINI_API_KEY in .env or your environment')
        if os.getenv('TRIGGER_MODE', 'keyboard') != 'keyboard' or not boolean('PREVIEW_ENABLED', 'true'):
            raise ValueError('Phase 1 requires TRIGGER_MODE=keyboard and PREVIEW_ENABLED=true')
        self.arduino_enabled = boolean('ARDUINO_ENABLED', 'true')
        self.model = os.getenv('GEMINI_MODEL', 'gemini-3.5-flash')
        self.camera = int(os.getenv('CAMERA_INDEX', '0'))
        self.width = int(os.getenv('CAMERA_WIDTH', '1280'))
        self.height = int(os.getenv('CAMERA_HEIGHT', '720'))
        self.save = boolean('SAVE_IMAGES', 'true')
        self.timeout = float(os.getenv('API_TIMEOUT_SECONDS', '15'))
        self.rules = os.getenv('RECYCLING_RULES', 'Use the default two-bin prototype policy in the prompt.')
        if self.width <= 0 or self.height <= 0 or not 0 < self.timeout <= 120:
            raise ValueError('Dimensions must be positive; timeout must be in (0, 120] seconds')
