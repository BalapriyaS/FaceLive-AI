"use strict";

let mediaStream       = null;
let detectionInterval = null;
let timerInterval     = null;
let sessionActive     = false;
let verifiedShown     = false;
let challengeTimeout  = 8;
let challengeElapsed  = 0;
let detectionHistory  = [];

const DETECT_INTERVAL_MS = 120;
const MAX_HISTORY        = 50;
const CANVAS_QUALITY     = 0.6;

const videoEl           = document.getElementById("localVideo");
const canvasEl          = document.getElementById("localCanvas");
const annotatedImg      = document.getElementById("annotatedImg");
const loadingOverlay    = document.getElementById("loadingOverlay");
const faceLostOverlay   = document.getElementById("faceLostOverlay");
const verifiedStamp     = document.getElementById("verifiedStamp");
const startBtn          = document.getElementById("startBtn");
const stopBtn           = document.getElementById("stopBtn");
const sessionBadge      = document.getElementById("sessionBadge");
const fpsBadge          = document.getElementById("fpsBadge");
const timerBar          = document.getElementById("timerBar");
const timerLabel        = document.getElementById("timerLabel");
const progressFill      = document.getElementById("progressFill");
const progressText      = document.getElementById("progressText");
const challengeInstr    = document.getElementById("challengeInstruction");
const challengeHistory  = document.getElementById("challengeHistory");
const detectionHistEl   = document.getElementById("detectionHistory");
const statusBadge       = document.getElementById("statusBadge");
const spoofReason       = document.getElementById("spoofReason");
const livenessScore     = document.getElementById("livenessScore");
const gaugeFill         = document.getElementById("gaugeFill");
const earValue          = document.getElementById("earValue");
const blinkCount        = document.getElementById("blinkCount");
const headDir           = document.getElementById("headDir");
const yawPitch          = document.getElementById("yawPitch");
const mouthStatus       = document.getElementById("mouthStatus");
const mouthRatio        = document.getElementById("mouthRatio");
const motionValue       = document.getElementById("motionValue");
const textureValue      = document.getElementById("textureValue");
const verifiedModal     = document.getElementById("verifiedModal");
const themeToggle       = document.getElementById("themeToggle");

themeToggle.addEventListener("click", () => {
  const html = document.documentElement;
  const isDark = html.getAttribute("data-theme") === "dark";
  html.setAttribute("data-theme", isDark ? "light" : "dark");
  themeToggle.textContent = isDark ? "☀️" : "🌙";
});

async function startCamera() {
  try {
    mediaStream = await navigator.mediaDevices.getUserMedia({
      video: { width: { ideal: 640 }, height: { ideal: 480 }, facingMode: "user" },
      audio: false,
    });
    videoEl.srcObject = mediaStream;
    await new Promise((res) => { videoEl.onloadedmetadata = res; });
    videoEl.play();
    canvasEl.width  = videoEl.videoWidth  || 640;
    canvasEl.height = videoEl.videoHeight || 480;
    loadingOverlay.classList.add("hidden");
  } catch (err) {
    loadingOverlay.innerHTML = `<p style="color:var(--red)">❌ Camera unavailable: ${err.message}</p>`;
    throw err;
  }
}

function captureFrame() {
  const ctx = canvasEl.getContext("2d");
  ctx.drawImage(videoEl, 0, 0, canvasEl.width, canvasEl.height);
  return canvasEl.toDataURL("image/jpeg", CANVAS_QUALITY);
}

async function startDetection() {
  if (sessionActive) return;
  loadingOverlay.classList.remove("hidden");

  try {
    await startCamera();
  } catch {
    return;
  }

  try {
    const res  = await fetch("/start", { method: "POST" });
    const data = await res.json();
    if (data.status !== "success") throw new Error(data.message);

    sessionActive  = true;
    verifiedShown  = false;
    startBtn.classList.add("hidden");
    stopBtn.classList.remove("hidden");
    sessionBadge.textContent = "⬤ Active";
    sessionBadge.className   = "nav-badge active";

    if (data.challenge) updateChallenge(data.challenge);
    startFrameLoop();
    startTimerLoop();

  } catch (err) {
    loadingOverlay.classList.add("hidden");
  }
}

async function stopDetection() {
  sessionActive = false;
  clearInterval(detectionInterval);
  clearInterval(timerInterval);
  detectionInterval = null;
  timerInterval     = null;

  if (mediaStream) {
    mediaStream.getTracks().forEach((t) => t.stop());
    mediaStream = null;
  }

  try {
    await fetch("/stop", { method: "POST" });
  } catch (_) {}

  startBtn.classList.remove("hidden");
  stopBtn.classList.add("hidden");
  annotatedImg.src         = "";
  sessionBadge.textContent = "⬤ Idle";
  sessionBadge.className   = "nav-badge";
  faceLostOverlay.classList.add("hidden");
  verifiedStamp.classList.add("hidden");
  timerBar.style.width     = "100%";
  timerLabel.textContent   = "—";
  challengeInstr.innerHTML = 'Press <strong>Start Detection</strong> to begin';
  loadingOverlay.classList.remove("hidden");
  loadingOverlay.innerHTML = '<div class="spinner"></div><p>Starting camera…</p>';
}

function startFrameLoop() {
  detectionInterval = setInterval(sendFrame, DETECT_INTERVAL_MS);
}

async function sendFrame() {
  if (!sessionActive) return;
  const frameB64 = captureFrame();

  try {
    const res  = await fetch("/detect", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ frame: frameB64 }),
    });
    const json = await res.json();
    if (json.status === "success") processResult(json.data);
  } catch (err) {
    console.error("Network error:", err);
  }
}

function processResult(d) {
  if (d.annotated_frame) annotatedImg.src = d.annotated_frame;
  fpsBadge.textContent = `${d.fps ?? 0} FPS`;

  if (!d.face_detected) {
    faceLostOverlay.classList.remove("hidden");
  } else {
    faceLostOverlay.classList.add("hidden");
  }

  earValue.textContent   = d.ear_avg  ? d.ear_avg.toFixed(3) : "—";
  blinkCount.textContent = `Blinks: ${d.blink_count ?? 0}`;

  const dirEmoji = { left: "⬅️", right: "➡️", up: "⬆️", down: "⬇️", center: "😐", none: "—" };
  headDir.textContent  = dirEmoji[d.head_direction] ?? "—";
  yawPitch.textContent = d.yaw != null ? `Yaw ${d.yaw}°  Pitch ${d.pitch}°` : "";

  if (d.mouth_open)       mouthStatus.textContent = "😮 Open";
  else if (d.smile_detected) mouthStatus.textContent = "😊 Smile";
  else                       mouthStatus.textContent = "😐 Neutral";
  mouthRatio.textContent = `Ratio: ${d.mouth_open_ratio?.toFixed(3) ?? "—"}`;

  motionValue.textContent  = d.motion  != null ? d.motion.toFixed(2)   : "—";
  textureValue.textContent = d.texture != null ? `Texture: ${d.texture.toFixed(0)}` : "";

  const score  = d.liveness_score ?? 0;
  const isLive = d.liveness_label === "Live";

  livenessScore.textContent = `${score}%`;
  gaugeFill.style.width     = `${score}%`;

  statusBadge.textContent = isLive ? "✅ Live Person" : "❌ Spoof Detected";
  statusBadge.className   = "status-badge " + (isLive ? "live" : "spoof");
  spoofReason.textContent = d.spoof_reason ?? "";

  sessionBadge.textContent = isLive ? "⬤ Live" : "⬤ Spoof";
  sessionBadge.className   = "nav-badge " + (isLive ? "active" : "spoof");

  if (d.challenge) updateChallenge(d.challenge);

  if (d.liveness_verified && !verifiedShown) {
    verifiedShown = true;
    verifiedStamp.classList.remove("hidden");
    verifiedModal.classList.remove("hidden");
    pushHistory("✅ Live Person Verified", "success");
  }

  if (Math.random() < 0.04) {
    pushHistory(`${isLive ? "✅" : "❌"} ${d.liveness_label} — Score ${score}%`, isLive ? "success" : "error");
  }
}

function updateChallenge(ch) {
  if (!ch) return;
  challengeInstr.textContent = ch.instruction ?? "";
  challengeTimeout = ch.timeout ?? 8;
  challengeElapsed = ch.elapsed ?? 0;

  const pct = Math.min(100, (ch.completed / ch.required) * 100);
  progressFill.style.width = `${pct}%`;
  progressText.textContent = `${ch.completed} / ${ch.required}`;

  if (ch.history && ch.history.length) {
    const items = ch.history.slice(-5).reverse().map((h) =>
      `<li><span>${h.challenge}</span><span>${h.result} (${h.time}s)</span></li>`
    ).join("");
    challengeHistory.innerHTML = items;
  }
}

function startTimerLoop() {
  timerInterval = setInterval(() => {
    if (!sessionActive) return;
    challengeElapsed = Math.min(challengeElapsed + 0.1, challengeTimeout);
    const pct     = Math.max(0, 100 - (challengeElapsed / challengeTimeout) * 100);
    const timeLeft = Math.max(0, challengeTimeout - challengeElapsed);

    timerBar.style.width  = `${pct}%`;
    timerLabel.textContent = `${timeLeft.toFixed(1)}s remaining`;
    timerBar.classList.toggle("warn", pct < 30);
  }, 100);
}

function pushHistory(msg, level = "info") {
  const ts = new Date().toLocaleTimeString();
  detectionHistory.unshift({ ts, msg, level });
  if (detectionHistory.length > MAX_HISTORY) detectionHistory.pop();
  renderHistory();
}

function renderHistory() {
  if (!detectionHistory.length) {
    detectionHistEl.innerHTML = '<li class="history-placeholder">No events recorded yet.</li>';
    return;
  }
  detectionHistEl.innerHTML = detectionHistory.slice(0, 20).map((h) =>
    `<li><span>${h.msg}</span><span style="color:var(--text-muted);font-size:11px">${h.ts}</span></li>`
  ).join("");
}

function closeModal() {
  verifiedModal.classList.add("hidden");
}