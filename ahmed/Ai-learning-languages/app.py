import os
import uuid
from flask import Flask, render_template, request, jsonify, send_file
from dotenv import load_dotenv
from gtts import gTTS
import whisper
import requests

load_dotenv()
app = Flask(__name__)

# مفاتيح
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# تحميل Whisper محلي
whisper_model = whisper.load_model("base")

# الصفحة الرئيسية
@app.route("/")
def index():
    return render_template("index.html")

# إرسال نص للـ AI (OpenRouter)
@app.route("/api/send_text", methods=["POST"])
def send_text():
    data = request.get_json()
    user_message = data.get("message", "")
    level = data.get("level", "A1")
    max_length = data.get("max_length", 50)

    # Level-specific system prompts
    level_prompts = {
        "A1": "You are a Spanish teacher for A1 (Beginner) level. Use very simple Spanish with basic vocabulary. Keep responses under 30 words. Use present tense only. Be encouraging and clear.",
        "A2": "You are a Spanish teacher for A2 (Elementary) level. Use simple Spanish with common vocabulary. Keep responses under 40 words. Use present and past tense. Be helpful and patient.",
        "B1": "You are a Spanish teacher for B1 (Intermediate) level. Use intermediate Spanish with varied vocabulary. Keep responses under 50 words. Use different tenses. Be engaging and supportive.",
        "B2": "You are a Spanish teacher for B2 (Upper Intermediate) level. Use advanced Spanish with complex vocabulary. Keep responses under 50 words. Use all tenses. Be challenging and motivating.",
        "C1": "You are a Spanish teacher for C1 (Advanced) level. Use sophisticated Spanish with nuanced vocabulary. Keep responses under 50 words. Use complex structures. Be intellectually stimulating.",
        "C2": "You are a Spanish teacher for C2 (Proficient) level. Use native-level Spanish with advanced vocabulary. Keep responses under 50 words. Use all linguistic features. Be challenging and sophisticated."
    }

    system_prompt = level_prompts.get(level, level_prompts["A1"])

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "deepseek/deepseek-chat-v3.1:free",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ],
        "max_tokens": 100  # Limit response length
    }

    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload
        )
        response.raise_for_status()
        reply_text = response.json()["choices"][0]["message"]["content"]
        
        # Ensure response is short
        words = reply_text.split()
        if len(words) > max_length:
            reply_text = " ".join(words[:max_length]) + "..."
        
        # Translate Spanish to Arabic
        arabic_translation = translate_to_arabic(reply_text)
            
        print(f"📚 Level {level} - User: {user_message[:50]}... - Spanish: {reply_text[:50]}... - Arabic: {arabic_translation[:50]}...")
        return jsonify({
            "reply": reply_text,
            "arabic": arabic_translation
        })
    except Exception as e:
        print(f"❌ AI API Error: {str(e)}")
        return jsonify({"error": "AI response failed", "details": str(e)}), 500

def translate_to_arabic(spanish_text):
    """Translate Spanish text to Arabic using OpenRouter"""
    try:
        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": "deepseek/deepseek-chat-v3.1:free",
            "messages": [
                {"role": "system", "content": "You are a professional translator. Translate the Spanish text to Arabic. Return only the Arabic translation, no explanations."},
                {"role": "user", "content": f"Translate this Spanish text to Arabic: {spanish_text}"}
            ],
            "max_tokens": 100
        }
        
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload
        )
        response.raise_for_status()
        arabic_text = response.json()["choices"][0]["message"]["content"]
        
        return arabic_text.strip()
    except Exception as e:
        print(f"❌ Translation Error: {str(e)}")
        return "ترجمة غير متاحة"  # Translation not available

# Speech-to-Text (Whisper محلي)
@app.route("/api/stt", methods=["POST"])
def stt():
    if "audio" not in request.files:
        return jsonify({"error": "No audio file provided"}), 400

    audio_file = request.files["audio"]
    filename = f"{uuid.uuid4()}.wav"
    filepath = os.path.join("temp", filename)
    os.makedirs("temp", exist_ok=True)
    audio_file.save(filepath)

    try:
        result = whisper_model.transcribe(filepath, language="es")  # الإسباني
        text = result["text"]
    except Exception as e:
        print("❌ Whisper Error:", str(e))
        return jsonify({"error": "STT failed", "details": str(e)}), 500
    finally:
        # نمسح الملف بعد المعالجة
        if os.path.exists(filepath):
            os.remove(filepath)

    return jsonify({"text": text})

# تحويل النص الإسباني إلى صوت باستخدام gTTS
@app.route("/api/tts", methods=["POST"])
def tts():
    data = request.get_json()
    text = data.get("text", "")

    if not text.strip():
        return jsonify({"error": "No text provided"}), 400

    try:
        # إنشاء ملف صوتي مؤقت
        filename = f"{uuid.uuid4()}.mp3"
        filepath = os.path.join("temp", filename)
        os.makedirs("temp", exist_ok=True)
        
        # تحويل النص الإسباني إلى صوت
        tts = gTTS(text=text, lang="es")  # الإسباني
        tts.save(filepath)
        
        # إرجاع رابط الملف
        audio_url = f"/temp/{filename}"
        print(f"🔊 TTS Generated: {text[:50]}...")
        return jsonify({"audio_url": audio_url})
        
    except Exception as e:
        print("❌ gTTS Error:", str(e))
        return jsonify({"error": "TTS generation failed", "details": str(e)}), 500

# خدمة الملفات الصوتية
@app.route("/temp/<filename>")
def serve_audio(filename):
    filepath = os.path.join("temp", filename)
    if os.path.exists(filepath):
        return send_file(filepath, mimetype="audio/mpeg")
    else:
        return jsonify({"error": "Audio file not found"}), 404
    

if __name__ == "__main__":
    app.run(debug=True)
