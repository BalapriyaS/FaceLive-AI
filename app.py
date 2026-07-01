import base64
import logging
import time
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import numpy as np
import cv2
from detector import LivenessDetector
from challenge import ChallengeManager
from utils import decode_base64_image, encode_image_to_base64, setup_logging

app = Flask(__name__)
CORS(app)
setup_logging()
logger = logging.getLogger(__name__)
detector = LivenessDetector()
challenge_manager = ChallengeManager()
session_active = False
session_start_time = None
frame_count = 0
fps_timer = time.time()
current_fps = 0.0

@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")

@app.route("/start", methods=["POST"])
def start_detection():
    global session_active, session_start_time, frame_count, fps_timer, current_fps
    try:
        detector.reset()
        challenge_manager.reset()
        session_active = True
        session_start_time = time.time()
        frame_count = 0
        fps_timer = time.time()
        current_fps = 0.0
        return jsonify({"status": "success", "message": "Session started.", "challenge": challenge_manager.get_current_challenge()})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/detect", methods=["POST"])
def detect():
    global session_active, frame_count, fps_timer, current_fps
    if not session_active:
        return jsonify({"status": "error", "message": "Session not active."}), 400
    try:
        data = request.get_json(force=True)
        if not data or "frame" not in data:
            return jsonify({"status": "error", "message": "No frame."}), 400
        frame = decode_base64_image(data["frame"])
        if frame is None:
            return jsonify({"status": "error", "message": "Invalid frame."}), 400
        frame_count += 1
        elapsed = time.time() - fps_timer
        if elapsed >= 1.0:
            current_fps = round(frame_count / elapsed, 1)
            frame_count = 0
            fps_timer = time.time()
        result = detector.process_frame(frame)
        challenge_result = challenge_manager.evaluate(result)
        result.update(challenge_result)
        annotated = detector.annotate_frame(frame, result)
        result["annotated_frame"] = encode_image_to_base64(annotated)
        result["fps"] = current_fps
        result["session_time"] = round(time.time() - session_start_time, 1)
        return jsonify({"status": "success", "data": result})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/challenge", methods=["POST"])
def next_challenge():
    try:
        return jsonify({"status": "success", "challenge": challenge_manager.next_challenge()})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/status", methods=["GET"])
def status():
    return jsonify({"status": "success", "session_active": session_active, "fps": current_fps, "liveness_verified": challenge_manager.is_verified()})

@app.route("/stop", methods=["POST"])
def stop_detection():
    global session_active
    session_active = False
    detector.reset()
    challenge_manager.reset()
    return jsonify({"status": "success", "message": "Session stopped."})

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000, threaded=True)