from datetime import datetime
from uuid import uuid4
import cv2

class Camera:
    def __init__(self, config):
        self.device = cv2.VideoCapture(config.camera)
        if not self.device.isOpened():
            self.device.release()
            raise RuntimeError(f'Cannot open camera {config.camera}. Check macOS camera permissions, CAMERA_INDEX, and other camera apps.')
        self.device.set(cv2.CAP_PROP_FRAME_WIDTH, config.width)
        self.device.set(cv2.CAP_PROP_FRAME_HEIGHT, config.height)

    def read(self):
        ok, frame = self.device.read()
        if not ok or frame is None:
            raise RuntimeError('Camera stopped providing frames. Reconnect camera and restart.')
        return frame

    @staticmethod
    def capture(frame, directory, save=True):
        height, width = frame.shape[:2]
        if max(height, width) > 1280:
            scale = 1280 / max(height, width)
            frame = cv2.resize(frame, (round(width * scale), round(height * scale)))
        ok, encoded = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        if not ok:
            raise RuntimeError('JPEG encoding failed')
        jpeg, path = encoded.tobytes(), ''
        if save:
            directory.mkdir(parents=True, exist_ok=True)
            target = directory / (datetime.now().strftime('%Y%m%d_%H%M%S_%f') + '_' + uuid4().hex[:8] + '.jpg')
            target.write_bytes(jpeg)
            path = str(target)
        return jpeg, path

    def close(self):
        self.device.release()
        cv2.destroyAllWindows()
