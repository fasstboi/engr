"""OpenCV key-repeat suppression and busy-input rejection."""
import time

class KeyboardTrigger:
    def __init__(self, clock=time.monotonic, release_gap=0.35, cooldown=0.8):
        self.clock, self.release_gap, self.cooldown = clock, release_gap, cooldown
        self.last_space = self.last_accept = float('-inf')

    def capture_requested(self, key, busy=False):
        if key != 32:
            return False
        now = self.clock()
        released = now - self.last_space > self.release_gap
        self.last_space = now
        if busy or not released or now - self.last_accept < self.cooldown:
            return False
        self.last_accept = now
        return True
