const startBtn = document.getElementById("start-btn");
const stopBtn = document.getElementById("stop-btn");
const transcriptDiv = document.getElementById("transcript");
const statusDiv = document.getElementById("status");

let websocket;
let mediaRecorder;
let audioContext;
let audioQueue = [];
let isPlaying = false;
// Assuming 16kHz mono, which is common for voice.
// This must match the sample rate of the TTS output.
const sampleRate = 16000;

startBtn.addEventListener("click", () => {
  startBtn.disabled = true;
  stopBtn.disabled = false;
  statusDiv.textContent = "Connecting...";

  navigator.mediaDevices
    .getUserMedia({ audio: true, video: false })
    .then((stream) => {
      const wsUrl = `ws://${window.location.host}/voice`;
      websocket = new WebSocket(wsUrl);

      websocket.onopen = () => {
        statusDiv.textContent = "Connected. Speak now.";
        mediaRecorder = new MediaRecorder(stream);
        mediaRecorder.ondataavailable = (event) => {
          if (event.data.size > 0 && websocket.readyState === WebSocket.OPEN) {
            websocket.send(event.data);
          }
        };
        mediaRecorder.start(250); // Send audio data every 250ms
        audioContext = new (window.AudioContext || window.webkitAudioContext)({
          sampleRate,
        });
      };

      websocket.onmessage = (event) => {
        const frame = JSON.parse(event.data);
        if (frame.type === "transcript") {
          transcriptDiv.textContent = frame.text;
        } else if (frame.type === "audio") {
          const audioData = atob(frame.audio); // base64 decode
          const pcmData = new Int16Array(audioData.length / 2);
          for (let i = 0; i < pcmData.length; i++) {
            pcmData[i] =
              (audioData.charCodeAt(i * 2 + 1) << 8) |
              audioData.charCodeAt(i * 2);
          }

          const float32Data = new Float32Array(pcmData.length);
          for (let i = 0; i < pcmData.length; i++) {
            float32Data[i] = pcmData[i] / 32768.0;
          }

          const audioBuffer = audioContext.createBuffer(
            1,
            float32Data.length,
            audioContext.sampleRate
          );
          audioBuffer.getChannelData(0).set(float32Data);

          audioQueue.push(audioBuffer);
          if (!isPlaying) {
            playAudioQueue();
          }
        }
      };

      websocket.onclose = () => {
        statusDiv.textContent = "Disconnected.";
        startBtn.disabled = false;
        stopBtn.disabled = true;
        if (mediaRecorder && mediaRecorder.state === "recording") {
          mediaRecorder.stop();
        }
        if (audioContext && audioContext.state !== "closed") {
          audioContext.close();
        }
      };

      websocket.onerror = (error) => {
        console.error("WebSocket Error:", error);
        statusDiv.textContent = "Connection error.";
      };
    });
});

stopBtn.addEventListener("click", () => {
  if (websocket && websocket.readyState === WebSocket.OPEN) {
    websocket.close();
  }
  if (mediaRecorder && mediaRecorder.state === "recording") {
    mediaRecorder.stop();
  }
});

function playAudioQueue() {
  if (audioQueue.length === 0) {
    isPlaying = false;
    return;
  }

  isPlaying = true;
  const buffer = audioQueue.shift();
  const source = audioContext.createBufferSource();
  source.buffer = buffer;
  source.connect(audioContext.destination);
  source.onended = playAudioQueue;
  source.start();
}
