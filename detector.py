import logging
import time
import math
import cv2
import numpy as np
import mediapipe as mp
from collections import deque

logger = logging.getLogger(__name__)

LEFT_EYE  = [362, 385, 387, 263, 373, 380]
RIGHT_EYE = [33,  160, 158, 133, 153, 144]
FACE_OVAL = [10,338,297,332,284,251,389,356,454,323,361,288,397,365,379,378,400,377,
             152,148,176,149,150,136,172,58,132,93,234,127,162,21,54,103,67,109]

EAR_BLINK_THRESHOLD  = 0.21
EAR_CONSEC_FRAMES    = 2
MOUTH_OPEN_THRESHOLD = 0.06
HEAD_TURN_THRESHOLD  = 20
SMILE_THRESHOLD      = 0.05
TEXTURE_VARIANCE_THRESHOLD = 100


class LivenessDetector:

    def __init__(self):
        self.mp_face_mesh = mp.solutions.face_mesh
        self.face_mesh = self.mp_face_mesh.FaceMesh(
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )
        self.reset()
        logger.info("LivenessDetector initialized.")

    def reset(self):
        self.blink_count = 0
        self.blink_counter = 0
        self.ear_history = deque(maxlen=30)
        self.prev_gray = None
        self.motion_history = deque(maxlen=20)
        self.texture_history = deque(maxlen=20)
        self.last_blink_time = time.time()
        self.blink_intervals = deque(maxlen=10)
        self.face_detected_frames = 0
        self.no_face_frames = 0
        self.spoof_score = 0
        self.liveness_score = 0
        self.head_pose_history = deque(maxlen=15)
        self.mouth_history = deque(maxlen=15)
        self.smile_baseline = None

    def _euclidean(self, p1, p2):
        return math.sqrt((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2)

    def compute_ear(self, landmarks, eye_indices, w, h):
        pts = [(int(landmarks[i].x * w), int(landmarks[i].y * h)) for i in eye_indices]
        A = self._euclidean(pts[1], pts[5])
        B = self._euclidean(pts[2], pts[4])
        C = self._euclidean(pts[0], pts[3])
        ear = (A + B) / (2.0 * C) if C > 0 else 0.0
        return round(ear, 4)

    def compute_mouth_open_ratio(self, landmarks, w, h):
        top    = np.array([landmarks[0].x * w,  landmarks[0].y * h])
        bottom = np.array([landmarks[17].x * w, landmarks[17].y * h])
        left   = np.array([landmarks[61].x * w, landmarks[61].y * h])
        right  = np.array([landmarks[291].x * w, landmarks[291].y * h])
        vert   = np.linalg.norm(bottom - top)
        horiz  = np.linalg.norm(right - left)
        return round(vert / horiz, 4) if horiz > 0 else 0.0

    def compute_smile_ratio(self, landmarks, w, h):
        left  = np.array([landmarks[61].x * w,  landmarks[61].y * h])
        right = np.array([landmarks[291].x * w, landmarks[291].y * h])
        fl    = np.array([landmarks[234].x * w, landmarks[234].y * h])
        fr    = np.array([landmarks[454].x * w, landmarks[454].y * h])
        mouth_w = np.linalg.norm(right - left)
        face_w  = np.linalg.norm(fr - fl)
        return round(mouth_w / face_w, 4) if face_w > 0 else 0.0

    def estimate_head_pose(self, landmarks, w, h):
        nose   = np.array([landmarks[4].x * w, landmarks[4].y * h])
        left   = np.array([landmarks[234].x * w, landmarks[234].y * h])
        right  = np.array([landmarks[454].x * w, landmarks[454].y * h])
        chin   = np.array([landmarks[152].x * w, landmarks[152].y * h])
        forehead = np.array([landmarks[10].x * w, landmarks[10].y * h])

        face_cx = (left[0] + right[0]) / 2
        face_cy = (forehead[1] + chin[1]) / 2
        face_w  = np.linalg.norm(right - left)
        face_h  = np.linalg.norm(chin - forehead)

        yaw   = ((nose[0] - face_cx) / face_w * 90) if face_w > 0 else 0
        pitch = ((nose[1] - face_cy) / face_h * 90) if face_h > 0 else 0

        if   yaw < -HEAD_TURN_THRESHOLD:  direction = "left"
        elif yaw >  HEAD_TURN_THRESHOLD:  direction = "right"
        elif pitch < -15: direction = "up"
        elif pitch >  15: direction = "down"
        else:                             direction = "center"

        return round(yaw, 2), round(pitch, 2), direction

    def analyze_texture(self, gray_roi):
        lap = cv2.Laplacian(gray_roi, cv2.CV_64F)
        return round(lap.var(), 2)

    def analyze_motion(self, gray):
        if self.prev_gray is None or self.prev_gray.shape != gray.shape:
            self.prev_gray = gray
            return 1.0
        diff = cv2.absdiff(self.prev_gray, gray)
        self.prev_gray = gray
        return round(float(np.mean(diff)), 4)

    def _compute_spoof_score(self, ear, motion, texture, blink_count, face_frames):
        score = 0
        if face_frames > 60 and blink_count == 0:
            score += 40
        avg_motion = np.mean(self.motion_history) if self.motion_history else 1.0
        if avg_motion < 0.3:
            score += 30
        avg_texture = np.mean(self.texture_history) if self.texture_history else 500
        if avg_texture < TEXTURE_VARIANCE_THRESHOLD:
            score += 20
        if len(self.ear_history) >= 20:
            ear_std = np.std(list(self.ear_history))
            if ear_std < 0.005:
                score += 10
        return min(score, 100)

    def process_frame(self, frame):
        h, w = frame.shape[:2]
        gray  = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        rgb   = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        motion = self.analyze_motion(gray)
        self.motion_history.append(motion)

        result = {
            "face_detected": False,
            "ear_left": 0.0, "ear_right": 0.0, "ear_avg": 0.0,
            "blink_count": self.blink_count,
            "eyes_closed": False,
            "mouth_open": False, "mouth_open_ratio": 0.0,
            "smile_detected": False, "smile_ratio": 0.0,
            "head_direction": "none", "yaw": 0.0, "pitch": 0.0,
            "motion": motion, "texture": 0.0,
            "spoof_score": 100, "liveness_score": 0,
            "liveness_label": "Unknown",
            "spoof_reason": "No face detected",
            "bbox": None,
        }

        mesh_results = self.face_mesh.process(rgb)
        if not mesh_results.multi_face_landmarks:
            self.no_face_frames += 1
            self.face_detected_frames = 0
            return result

        self.no_face_frames = 0
        self.face_detected_frames += 1
        face_lm = mesh_results.multi_face_landmarks[0].landmark

        ear_l = self.compute_ear(face_lm, LEFT_EYE,  w, h)
        ear_r = self.compute_ear(face_lm, RIGHT_EYE, w, h)
        ear   = round((ear_l + ear_r) / 2.0, 4)
        self.ear_history.append(ear)

        eyes_closed = ear < EAR_BLINK_THRESHOLD
        if eyes_closed:
            self.blink_counter += 1
        else:
            if self.blink_counter >= EAR_CONSEC_FRAMES:
                self.blink_count += 1
                now = time.time()
                self.blink_intervals.append(now - self.last_blink_time)
                self.last_blink_time = now
            self.blink_counter = 0

        mouth_ratio  = self.compute_mouth_open_ratio(face_lm, w, h)
        smile_ratio  = self.compute_smile_ratio(face_lm, w, h)
        mouth_open   = mouth_ratio > MOUTH_OPEN_THRESHOLD
        self.mouth_history.append(mouth_ratio)

        if self.smile_baseline is None and self.face_detected_frames > 15:
            self.smile_baseline = smile_ratio
        smile_detected = False
        if self.smile_baseline is not None:
            smile_detected = (smile_ratio - self.smile_baseline) > SMILE_THRESHOLD

        yaw, pitch, head_dir = self.estimate_head_pose(face_lm, w, h)

        pts = [(int(face_lm[i].x * w), int(face_lm[i].y * h)) for i in FACE_OVAL]
        xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
        x1, y1 = max(min(xs)-10, 0), max(min(ys)-10, 0)
        x2, y2 = min(max(xs)+10, w), min(max(ys)+10, h)
        roi_gray = gray[y1:y2, x1:x2]
        texture = self.analyze_texture(roi_gray) if roi_gray.size > 0 else 0.0
        self.texture_history.append(texture)

        spoof_score = self._compute_spoof_score(ear, motion, texture, self.blink_count, self.face_detected_frames)
        liveness_score = max(0, 100 - spoof_score)

        spoof_reason = ""
        if self.face_detected_frames > 60 and self.blink_count == 0:
            spoof_reason = "No blink detected"
        elif np.mean(self.motion_history) < 0.3:
            spoof_reason = "Static face / frozen frame"
        elif np.mean(self.texture_history) < TEXTURE_VARIANCE_THRESHOLD:
            spoof_reason = "Low texture — possible printed photo or screen replay"

        liveness_label = "Live" if liveness_score >= 60 else "Spoof"

        result.update({
            "face_detected": True,
            "ear_left": ear_l, "ear_right": ear_r, "ear_avg": ear,
            "blink_count": self.blink_count,
            "eyes_closed": bool(eyes_closed),
            "mouth_open": bool(mouth_open), "mouth_open_ratio": mouth_ratio,
            "smile_detected": bool(smile_detected), "smile_ratio": smile_ratio,
            "head_direction": head_dir, "yaw": yaw, "pitch": pitch,
            "motion": motion, "texture": texture,
            "spoof_score": spoof_score, "liveness_score": liveness_score,
            "liveness_label": liveness_label, "spoof_reason": spoof_reason,
            "bbox": [x1, y1, x2, y2],
        })
        return result

    def annotate_frame(self, frame, result):
        annotated = frame.copy()
        is_live = result.get("liveness_label") == "Live"
        color = (0, 220, 0) if is_live else (0, 0, 220)

        bbox = result.get("bbox")
        if bbox:
            x1, y1, x2, y2 = bbox
            cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
            label = f"{'LIVE' if is_live else 'SPOOF'}  {result['liveness_score']}%"
            cv2.putText(annotated, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
            ear_txt = f"EAR: {result['ear_avg']:.3f}  Blinks: {result['blink_count']}"
            cv2.putText(annotated, ear_txt, (x1, y2 + 22), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 200), 1)

        return annotated