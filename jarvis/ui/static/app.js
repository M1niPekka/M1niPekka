const messagesEl = document.getElementById("messages");
const composer = document.getElementById("composer");
const input = document.getElementById("input");
const voiceBtn = document.getElementById("voiceBtn");
const statusDot = document.getElementById("statusDot");
const statusText = document.getElementById("statusText");
const logsBody = document.getElementById("logsBody");

let renderedCount = 1; // the static greeting bubble already in the DOM
let listening = false;

function renderMessage(role, text) {
  const row = document.createElement("div");
  row.className = `msg ${role}`;
  const bubble = document.createElement("div");
  bubble.className = "bubble";
  bubble.textContent = text;
  row.appendChild(bubble);
  messagesEl.appendChild(row);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

async function refreshStatus() {
  try {
    const res = await fetch("/api/status");
    const data = await res.json();
    listening = data.listening;
    statusDot.className = "dot " + (listening ? "on" : "off");
    statusText.textContent = `${data.brain} · wake word "${data.wake_word}"` +
      (data.voice_available ? "" : " · mic unavailable in this session");
    voiceBtn.textContent = listening ? "Stop listening" : "Start listening";
    voiceBtn.classList.toggle("active", listening);
    voiceBtn.disabled = !data.voice_available;
  } catch (e) {
    statusText.textContent = "disconnected from Jarvis";
  }
}

async function refreshMessages() {
  try {
    const res = await fetch("/api/messages");
    const data = await res.json();
    for (let i = renderedCount; i < data.length; i++) {
      renderMessage(data[i].role, data[i].text);
    }
    renderedCount = data.length;
  } catch (e) {
    /* ignore transient polling errors */
  }
}

async function refreshLogs() {
  try {
    const res = await fetch("/api/logs");
    const data = await res.json();
    logsBody.textContent = data.log || "(no shell commands run yet)";
  } catch (e) {
    /* ignore */
  }
}

composer.addEventListener("submit", async (e) => {
  e.preventDefault();
  const text = input.value.trim();
  if (!text) return;
  input.value = "";
  renderMessage("user", text);
  renderedCount++;
  const res = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });
  const data = await res.json();
  renderMessage("assistant", data.reply || data.error || "(no response)");
  renderedCount++;
});

voiceBtn.addEventListener("click", async () => {
  const endpoint = listening ? "/api/voice/stop" : "/api/voice/start";
  await fetch(endpoint, { method: "POST" });
  refreshStatus();
});

refreshStatus();
refreshMessages();
refreshLogs();
setInterval(refreshStatus, 3000);
setInterval(refreshMessages, 2000);
setInterval(refreshLogs, 4000);
