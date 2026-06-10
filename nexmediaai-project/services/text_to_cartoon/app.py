# text_to_cartoon_api.py
from flask import Flask, request, jsonify, send_file
from PIL import Image
import io, os, uuid
import requests
from deep_translator import GoogleTranslator # type: ignore
from huggingface_hub import InferenceClient # type: ignore

app = Flask(__name__)

class Config:
    HUGGINGFACE_API_URL = "https://api-inference.huggingface.co/models/goofyai/3d_render_style_xl"
    HUGGINGFACE_API_KEY = os.getenv("HUGGINGFACE_API_KEY", "")
    
    PROCESSED_FOLDER = os.getenv("PROCESSED_FOLDER", "/app/uploads")
    os.makedirs(PROCESSED_FOLDER, exist_ok=True)



def generate_image_from_prompt(prompt, api_key, model="goofyai/3d_render_style_xl", provider="fal-ai"):
    client = InferenceClient(provider=provider, api_key=api_key)
    try:
        return client.text_to_image(prompt, model=model)
    except Exception as e:
        print(f"Error generating image: {e}")
        return None


@app.route("/generate", methods=["POST"])
def generate():
    data = request.get_json()
    prompt = data.get("prompt")
 

 

    try:
        if any('\u0600' <= c <= '\u06ff' for c in prompt):
            prompt = GoogleTranslator(source="auto", target="en").translate(prompt)
    except Exception as e:
        return jsonify({"error": f"Translation error: {str(e)}"}), 500

    image = generate_image_from_prompt(prompt=prompt, api_key=Config.HUGGINGFACE_API_KEY)
    if image:
        filename = f"{uuid.uuid4().hex[:8]}.png"
        file_path = os.path.join(Config.PROCESSED_FOLDER, filename)
        image.save(file_path, "PNG")
        return send_file(file_path, mimetype="image/png")

    return jsonify({"error": "Image generation failed"}), 500

if __name__ == "__main__":
    app.run(port=5006, host="0.0.0.0", debug=True)
