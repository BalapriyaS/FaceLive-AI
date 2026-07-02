# 🧬 FaceLive AI — Face Liveness Detection System

> A real-time browser- based **Challenge-Response Anti-Spoofing System** that verifies whether a person in front of a webcam is a genuine live human or a spoof attempt using a photo, video, or screen replay.

![Python](https://img.shields.io/badge/Python-3.9%2B-blue)
![Flask](https://img.shields.io/badge/Flask-3.0-black)
![OpenCV](https://img.shields.io/badge/OpenCV-4.10-green)
![MediaPipe](https://img.shields.io/badge/MediaPipe-FaceMesh-orange)
![License](https://img.shields.io/badge/License-MIT-yellow)

---

## 📖 Overview

**FaceLive AI** is designed to improve biometric authentication by ensuring that only a live person can be verified. The system combines multiple liveness detection techniques to prevent spoofing attacks.

It combines three layers of defense:

1. 👁️ **Eye Aspect Ratio (EAR)** — detects natural blinking using 468-point facial landmarks
2. 🎯 **Challenge-Response** — random tasks (blink, turn head, smile, open mouth) that a static photo cannot perform
3. 🔍 **Anti-Spoof Heuristics** — motion, texture, and EAR-variance analysis to flag photos/screen replays in real time

A "Live Person Verified" result only appears once **3 challenges are completed AND** the session shows **sustained, genuine liveness evidence** — closing the loophole where a tilted photo could trick a single task.

---

## ✨ Features

- 📷 Real-time webcam-based detection (no special hardware needed)
- 🎯 6+ randomized liveness challenges
- 📊 Live metrics — EAR, blink count, head pose, mouth state, motion, texture
- 🛡️ Multi-layer anti-spoof scoring engine
- 🎨 Clean, responsive Black & Gold dashboard UI
- ⚡ ~8 FPS real-time processing on standard CPU
- 🔌 REST API backend (Flask) — easy to extend or integrate

---

## 🏗️ Tech Stack

| Layer | Technology |
|---|---|
| **Backend** | Python 3.9+, Flask 3.0 |
| **Computer Vision** | OpenCV 4.10 |
| **Facial Landmarks** | MediaPipe Face Mesh (468 points) |
| **Algorithm** | Eye Aspect Ratio (EAR), Head Pose Estimation |
| **Frontend** | HTML5, CSS3, Vanilla JavaScript |
| **Communication** | REST API (JSON over HTTP) |

---

## 📁 Project Structure

```
facelive-ai/
├── app.py                 # Flask server & REST API routes
├── detector.py             # Core CV — EAR, head pose, spoof scoring
├── challenge.py             # Challenge-Response state machine
├── utils.py                 # Image encode/decode, logging helpers
├── requirements.txt          # Python dependencies
├── templates/
│   └── index.html            # Main dashboard UI
├── static/
│   ├── style.css              # Black & Gold theme styling
│   └── script.js               # Webcam capture & live UI logic
└── README.md
```

---

## ⚙️ Installation

### Prerequisites
- Python 3.9 – 3.11
- A working webcam
- Google Chrome or Firefox

### Steps

```bash
# 1. Clone the repository
git clone https://github.com/<balapriya>/facelive-ai.git
cd facelive-ai

# 2. Create a virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
source venv/bin/activate     # macOS/Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run the application
python app.py
```

Open your browser at **http://127.0.0.1:5000**

---

## 🎮 How to Use

1. Click **▶ Start Detection** and allow camera access
2. Center your face in the frame with good lighting
3. Follow the on-screen challenge (e.g. *"Blink both eyes TWICE"*)
4. Complete 3 challenges successfully
5. Get verified: **✅ Live Person Verified!**

If a spoof (photo/screen) is detected, the system displays **❌ Spoof Detected** along with the reason (e.g. *"No blink detected"*, *"Static image — insufficient motion"*).

---

## 🔌 API Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Serves the dashboard UI |
| `POST` | `/start` | Starts a new detection session |
| `POST` | `/detect` | Processes a frame, returns metrics |
| `POST` | `/challenge` | Skips to next challenge |
| `GET` | `/status` | Returns current session status |
| `POST` | `/stop` | Stops the session |

**Example `/detect` request:**
```json
POST /detect
{ "frame": "data:image/jpeg;base64,..." }
```

**Example response:**
```json
{
  "status": "success",
  "data": {
    "face_detected": true,
    "ear_avg": 0.241,
    "blink_count": 3,
    "liveness_score": 92,
    "liveness_label": "Live",
    "challenge": { "instruction": "Smile please", "completed": 2, "required": 3 }
  }
}
```

---

## 🧠 How It Works

### Eye Aspect Ratio (EAR)
```
EAR = (‖p2-p6‖ + ‖p3-p5‖) / (2 × ‖p1-p4‖)
```
EAR drops sharply when eyes close. A blink is registered when EAR stays below ~0.21 for 2+ consecutive frames.

### Anti-Spoof Scoring
| Signal | Spoof Indicator |
|---|---|
| No blink in observation window | Printed photo |
| Low frame motion | Frozen/held image |
| Low texture variance | Blurry print or screen replay |
| Flat EAR variance | Static image |

### Session-Wide Verification
Final "Live" status requires **both**:
- ✅ 3 challenges completed
- ✅ ≥70% of session frames independently scored "Live"

---

## 🐞 Troubleshooting

| Issue | Fix |
|---|---|
| `ModuleNotFoundError: mediapipe` | Run `pip install -r requirements.txt` inside your venv |
| Camera permission denied | Click the camera icon in your browser's address bar → Allow |
| Port 5000 already in use | Change `port=5000` in `app.py` to another port |
| Black/blank video | Ensure no other app is using the webcam |
| Low FPS | Reduce canvas resolution in `script.js` |

---

## 🚀 Future Improvements

- [ ] Deep learning-based anti-spoofing (CNN trained on CASIA-FASD / Replay-Attack)
- [ ] Face recognition integration after liveness verification
- [ ] Attendance system / eKYC integration
- [ ] Cloud deployment (Docker + AWS/GCP)
- [ ] Mobile app version

---

## 🙋 Author

S. Bala Priya

BE CSE (AIML)

VSB Engineering College,Karur

---

⭐ If you found this project useful, consider giving it a star on GitHub!
