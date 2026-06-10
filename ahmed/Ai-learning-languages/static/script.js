let mediaRecorder;
let audioChunks = [];
let silenceTimer;
let isCalling = false;
let selectedLevel = "A1";

const callBtn = document.getElementById("call-btn");
const statusCircle = document.getElementById("status-circle");
const chatBox = document.getElementById("chat-box");
const levelSelection = document.getElementById("level-selection");
const mainInterface = document.getElementById("main-interface");
const currentLevelSpan = document.getElementById("current-level");
const changeLevelBtn = document.getElementById("change-level-btn");

// Level selection event listeners
document.querySelectorAll('.level-btn').forEach(btn => {
  btn.addEventListener('click', () => selectLevel(btn.dataset.level));
});

callBtn.addEventListener("click", toggleCall);
changeLevelBtn.addEventListener("click", showLevelSelection);

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
  if (isCalling) {
    toggleCall(); // End call if active
  }
}

async function toggleCall() {
  if (!isCalling) {
    // Start Call
    isCalling = true;
    callBtn.innerText = "End Call";
    setCircleColor("red"); // تسجيل شغال
    showChatBox();
    startRecording();
  } else {
    // End Call
    isCalling = false;
    callBtn.innerText = "Start Call";
    setCircleColor("white"); // وقف
    hideChatBox();
    if (mediaRecorder && mediaRecorder.state !== "inactive") {
      mediaRecorder.stop();
    }
    clearTimeout(silenceTimer);
  }
}

function setCircleColor(color) {
  // Remove all color classes
  statusCircle.classList.remove("white", "red", "blue");
  // Add the new color class
  statusCircle.classList.add(color);
}

function showChatBox() {
  chatBox.classList.remove("hidden");
}

function hideChatBox() {
  chatBox.classList.add("hidden");
}

async function startRecording() {
  try {
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
        console.log("📊 Audio chunk received:", e.data.size, "bytes");
      }
    };

    mediaRecorder.onstop = async () => {
      console.log("🛑 Recording stopped");
      const blob = new Blob(audioChunks, { type: "audio/webm" });
      audioChunks = [];

      if (!isCalling) return;

      await processAudio(blob);

      // لو لسه المكالمة شغالة نرجع نسجل تاني
      if (isCalling) {
        setCircleColor("red"); // نرجع وضع التسجيل
        startRecording();
      }
    };

    mediaRecorder.start(1000); // Collect data every second
    console.log("🎤 Recording started");

    // مراقبة الصمت
    const audioContext = new AudioContext();
    const source = audioContext.createMediaStreamSource(stream);
    const analyser = audioContext.createAnalyser();
    analyser.fftSize = 2048;
    analyser.smoothingTimeConstant = 0.8;
    source.connect(analyser);
    const dataArray = new Uint8Array(analyser.frequencyBinCount);

    let silenceStartTime = null;
    const SILENCE_THRESHOLD = 20; // Lower threshold for better detection
    const SILENCE_DURATION = 3000; // Exactly 3 seconds

    function checkSilence() {
      analyser.getByteFrequencyData(dataArray);
      
      // Calculate average volume
      let sum = 0;
      for (let i = 0; i < dataArray.length; i++) {
        sum += dataArray[i];
      }
      const average = sum / dataArray.length;
      
      const isSilent = average < SILENCE_THRESHOLD;
      const currentTime = Date.now();
      
      if (isSilent) {
        if (silenceStartTime === null) {
          silenceStartTime = currentTime;
          console.log("🔇 Silence detected, starting timer...");
        } else {
          const silenceDuration = currentTime - silenceStartTime;
          console.log(`🔇 Silence: ${(silenceDuration/1000).toFixed(1)}s / 3.0s`);
          
          if (silenceDuration >= SILENCE_DURATION) {
            console.log("⏰ 3 seconds of silence reached, stopping recording");
            if (mediaRecorder.state !== "inactive") {
              mediaRecorder.stop();
            }
            silenceStartTime = null;
            return;
          }
        }
      } else {
        if (silenceStartTime !== null) {
          console.log("🔊 Sound detected, resetting silence timer");
          silenceStartTime = null;
        }
        console.log(`🔊 Sound level: ${average.toFixed(1)}`);
      }

      if (isCalling) {
        requestAnimationFrame(checkSilence);
      }
    }

    checkSilence();
  } catch (error) {
    console.error("❌ Error starting recording:", error);
    setCircleColor("white");
    isCalling = false;
    callBtn.innerText = "Start Call";
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
    console.log("🔊 Converting Spanish text to speech...");
    const ttsRes = await fetch("/api/tts", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: reply }),
    });
    
    if (!ttsRes.ok) {
      throw new Error(`TTS Error: ${ttsRes.status}`);
    }
    
    const ttsData = await ttsRes.json();
    console.log("🔊 Playing Spanish audio...");

    const audio = new Audio(ttsData.audio_url);
    audio.onerror = (e) => {
      console.error("❌ Audio playback error:", e);
    };
    
    audio.play();

    await new Promise((resolve, reject) => {
      audio.onended = resolve;
      audio.onerror = reject;
    });
    
    console.log("✅ Spanish audio playback completed");
    
    // بعد ما الصوت يخلص نرجع للتسجيل
    if (isCalling) {
      setCircleColor("red"); // نرجع وضع التسجيل
    }
  } catch (error) {
    console.error("❌ Error processing audio:", error);
    addMessage("Sorry, there was an error processing your request.", "ai");
    if (isCalling) {
      setCircleColor("red"); // نرجع وضع التسجيل
    }
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
