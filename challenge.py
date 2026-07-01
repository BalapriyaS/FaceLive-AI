import random
import time
import logging

logger = logging.getLogger(__name__)

REQUIRED_CHALLENGES = 3

# Easy + medium challenges
CHALLENGES = [
    {"id": "blink_twice", "instruction": "Blink both eyes TWICE", "type": "blink", "target": 2, "timeout": 10},
    {"id": "blink_once",  "instruction": "Blink once",            "type": "blink", "target": 1, "timeout": 8},
    {"id": "turn_left",   "instruction": "Turn your head LEFT",   "type": "head_direction", "target": "left",  "timeout": 8},
    {"id": "turn_right",  "instruction": "Turn your head RIGHT",  "type": "head_direction", "target": "right", "timeout": 8},
    {"id": "look_up",     "instruction": "Look UP slightly",      "type": "head_direction", "target": "up",    "timeout": 8},
    {"id": "look_down",   "instruction": "Look DOWN slightly",    "type": "head_direction", "target": "down",  "timeout": 8},
    {"id": "open_mouth",  "instruction": "Open your MOUTH wide",  "type": "mouth_open", "timeout": 8},
    {"id": "smile",       "instruction": "SMILE please",          "type": "smile",      "timeout": 8},
]


class ChallengeManager:

    def __init__(self):
        self.required_count = REQUIRED_CHALLENGES
        self.reset()

    def reset(self):
        self.completed_count = 0
        self.failed_count = 0
        self.history = []
        self.current = dict(random.choice(CHALLENGES))
        self.challenge_start_time = time.time()
        self._blinks_at_start = None
        self._live_frame_count = 0
        self._total_frame_count = 0

    def is_verified(self):
        if self.completed_count < self.required_count:
            return False
        # Require that at least 70% of frames seen during the whole session
        # were independently scored as "Live" by the detector — this stops
        # a static photo from passing just because it tricked one task.
        if self._total_frame_count < 15:
            return False
        live_ratio = self._live_frame_count / max(1, self._total_frame_count)
        return live_ratio >= 0.70

    def get_current_challenge(self):
        elapsed = round(time.time() - self.challenge_start_time, 1)
        timeout = self.current.get("timeout", 8)
        return {
            "id":          self.current["id"],
            "instruction": self.current["instruction"],
            "type":        self.current["type"],
            "timeout":     timeout,
            "elapsed":     elapsed,
            "time_left":   max(0, round(timeout - elapsed, 1)),
            "completed":   self.completed_count,
            "required":    self.required_count,
            "remaining":   max(0, self.required_count - self.completed_count),
            "failed":      self.failed_count,
            "history":     self.history[-5:],
        }

    def next_challenge(self):
        candidates = [c for c in CHALLENGES if c["id"] != self.current["id"]]
        self.current = dict(random.choice(candidates))
        self.challenge_start_time = time.time()
        self._blinks_at_start = None
        return self.get_current_challenge()

    def evaluate(self, detection):
        # Track overall liveness evidence across the whole session,
        # independent of whether a specific task is currently active.
        if detection.get("face_detected"):
            self._total_frame_count += 1
            if detection.get("liveness_label") == "Live":
                self._live_frame_count += 1

        if self.is_verified():
            return {"challenge": self.get_current_challenge(), "liveness_verified": True}

        timeout = self.current.get("timeout", 8)
        elapsed = time.time() - self.challenge_start_time
        ch_type = self.current["type"]
        completed = False

        if ch_type == "blink":
            if self._blinks_at_start is None:
                self._blinks_at_start = detection.get("blink_count", 0)
            completed = (detection.get("blink_count", 0) - self._blinks_at_start) >= self.current.get("target", 1)

        elif ch_type == "head_direction":
            completed = detection.get("head_direction") == self.current.get("target")

        elif ch_type == "mouth_open":
            completed = detection.get("mouth_open", False)

        elif ch_type == "smile":
            completed = detection.get("smile_detected", False)

        if completed:
            self.completed_count += 1
            self.history.append({
                "challenge": self.current["instruction"],
                "result":    "Passed",
                "time":      round(elapsed, 1)
            })
            if not self.is_verified():
                self.next_challenge()

        elif elapsed > timeout:
            self.failed_count += 1
            self.history.append({
                "challenge": self.current["instruction"],
                "result":    "Timed out",
                "time":      round(elapsed, 1)
            })
            self.next_challenge()

        return {"challenge": self.get_current_challenge(), "liveness_verified": self.is_verified()}