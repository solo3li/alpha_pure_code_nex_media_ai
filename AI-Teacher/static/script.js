let mediaRecorder;
let audioChunks = [];
let selectedLevel = "A1";

const statusCircle = document.getElementById("status-circle");
const chatBox = document.getElementById("chat-box");
const levelSelection = document.getElementById("level-selection");
const mainInterface = document.getElementById("main-interface");
const currentLevelSpan = document.getElementById("current-level");
const changeLevelBtn = document.getElementById("change-level-btn");
const textInput = document.getElementById("text-input");
const sendBtn = document.getElementById("send-btn");
const micBtn = document.getElementById("mic-btn");

// Level selection event listeners
document.querySelectorAll('.level-btn').forEach(btn => {
  btn.addEventListener('click', () => selectLevel(btn.dataset.level));
});

changeLevelBtn.addEventListener("click", showLevelSelection);
sendBtn.addEventListener("click", () => {
  const text = (textInput.value || "").trim();
  if (!text) return;
  handleTextMessage(text);
});
textInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    const text = (textInput.value || "").trim();
    if (!text) return;
    handleTextMessage(text);
  }
});
micBtn.addEventListener("click", toggleMicRecording);

function selectLevel(level) {
  selectedLevel = level;
  currentLevelSpan.textContent = level;
  
  // Update selected button
  document.querySelectorAll('.level-btn').forEach(btn => {
    btn.classList.remove('selected');
  });
  document.querySelector(`[data-level="${level}"]`).classList.add('selected');
  
  // Show main interface
  levelSelection.classList.add('hidden');
  mainInterface.classList.remove('hidden');
  
  console.log(`📚 Spanish Level selected: ${level}`);
}

function showLevelSelection() {
  levelSelection.classList.remove('hidden');
  mainInterface.classList.add('hidden');
}

function setCircleColor(color) {
  // Remove all color classes
  statusCircle.classList.remove("white", "red", "blue");
  // Add the new color class
  statusCircle.classList.add(color);
}

async function handleTextMessage(userText) {
  // UI: add user message
  addMessage(userText, "user");
  textInput.value = "";
  // Query AI
  try {
    setCircleColor("blue");
    const aiRes = await fetch("/api/send_text", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ 
        message: userText,
        level: selectedLevel,
        max_length: 50
      }),
    });
    if (!aiRes.ok) throw new Error(`AI Error: ${aiRes.status}`);
    const aiData = await aiRes.json();
    const reply = aiData.reply;
    const arabic = aiData.arabic;
    addMessage(reply, "ai", arabic);
    // TTS Spanish
    await playSpanishTTS(reply);
  } catch (err) {
    console.error(err);
    addMessage("Sorry, something went wrong.", "ai");
  } finally {
    setCircleColor("white");
  }
}

async function playSpanishTTS(text) {
  try {
    const ttsRes = await fetch("/api/tts", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text })
    });
    if (!ttsRes.ok) return;
    const ttsData = await ttsRes.json();
    const audio = new Audio(ttsData.audio_url);
    await new Promise((resolve) => {
      audio.onended = resolve;
      audio.onerror = resolve;
      audio.play();
    });
  } catch (_) {
    // ignore tts errors
  }
}

async function toggleMicRecording() {
  if (mediaRecorder && mediaRecorder.state === "recording") {
    mediaRecorder.stop();
    micBtn.classList.remove("recording");
    setCircleColor("blue");
    return;
  }
  await startOneShotRecording();
}

async function startOneShotRecording() {
  try {
    setCircleColor("red");
    micBtn.classList.add("recording");
    const stream = await navigator.mediaDevices.getUserMedia({ 
      audio: {
        echoCancellation: true,
        noiseSuppression: true,
        sampleRate: 44100
      } 
    });
    
    mediaRecorder = new MediaRecorder(stream, {
      mimeType: 'audio/webm;codecs=opus'
    });

    mediaRecorder.ondataavailable = (e) => {
      if (e.data.size > 0) {
        audioChunks.push(e.data);
      }
    };

    mediaRecorder.onstop = async () => {
      try {
      const blob = new Blob(audioChunks, { type: "audio/webm" });
      audioChunks = [];
      await processAudio(blob);
      } finally {
        setCircleColor("white");
        micBtn.classList.remove("recording");
        // stop tracks
        stream.getTracks().forEach(t => t.stop());
      }
    };
    mediaRecorder.start();
  } catch (error) {
    console.error("❌ Error starting recording:", error);
    setCircleColor("white");
    micBtn.classList.remove("recording");
  }
}

async function processAudio(blob) {
  try {
    console.log("🔄 Processing audio...", blob.size, "bytes");
    
    const formData = new FormData();
    formData.append("audio", blob, "recording.webm");

    // 1) STT
    console.log("🎯 Sending to STT...");
    const sttRes = await fetch("/api/stt", { method: "POST", body: formData });
    
    if (!sttRes.ok) {
      throw new Error(`STT Error: ${sttRes.status}`);
    }
    
    const sttData = await sttRes.json();
    const userText = sttData.text;
    console.log("👤 User said:", userText);
    addMessage(userText, "user");

    // 2) AI Response (Text + Spanish Audio)
    console.log("🤖 Getting AI response...");
    setCircleColor("blue"); // AI is thinking/responding
    
    const aiRes = await fetch("/api/send_text", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ 
        message: userText,
        level: selectedLevel,
        max_length: 50
      }),
    });
    
    if (!aiRes.ok) {
      throw new Error(`AI Error: ${aiRes.status}`);
    }
    
    const aiData = await aiRes.json();
    const reply = aiData.reply;
    const arabic = aiData.arabic;
    console.log("🤖 AI replied (Spanish):", reply);
    console.log("🤖 AI replied (Arabic):", arabic);
    addMessage(reply, "ai", arabic);
    // 3) TTS for Spanish text
    await playSpanishTTS(reply);
  } catch (error) {
    console.error("❌ Error processing audio:", error);
    addMessage("Sorry, there was an error processing your request.", "ai");
    setCircleColor("white");
  }
}

function addMessage(text, sender, arabicText = null) {
  const div = document.createElement("div");
  div.className = "message " + sender;
  
  if (arabicText && sender === "ai") {
    // For AI messages, show both Spanish and Arabic
    div.innerHTML = `
      <div class="message-content">
        <div class="spanish-text">🇪🇸 ${text}</div>
        <div class="arabic-text">🇸🇦 ${arabicText}</div>
      </div>
    `;
  } else {
    // For user messages, show as is
    div.innerText = text;
  }
  
  document.getElementById("chat-box").appendChild(div);
  
  // Scroll to bottom
  const chatBox = document.getElementById("chat-box");
  chatBox.scrollTop = chatBox.scrollHeight;
}
