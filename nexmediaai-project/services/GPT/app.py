from flask import Flask, request, jsonify
import os
from functools import wraps

app = Flask(__name__)

# Configuration
class Config:
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    API_KEY = "G7OaZvkf906gDS6skW9mCnxvOLOnWnc8"

# Initialize OpenAI client - defer initialization to avoid startup errors
from openai import OpenAI
client = None

def get_openai_client():
    global client
    if client is None:
        client = OpenAI(api_key=Config.OPENAI_API_KEY)
    return client

# API Key Authentication
def require_api_key(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get('X-API-Key')
        if api_key and api_key == Config.API_KEY:
            return f(*args, **kwargs)
        return jsonify({"error": "Unauthorized access. Invalid or missing API Key"}), 401
    return decorated_function

@app.route('/api/chat', methods=['POST'])
@require_api_key
def chat():
    """
    Handle chat requests from Django application
    """
    client = get_openai_client()
    
    data = request.json
    user_input = data.get('message', '')
    model = data.get('model', 'gpt-4o')
    image_data = data.get('image', None)
    
    messages = [{"role": "user", "content": user_input}]
    
    if image_data:
        import re
        match = re.match(r"data:image/([a-zA-Z]+);base64,(.+)", image_data)
        if match:
            image_format = match.group(1)  # Extract format (jpeg, png, etc.)
            image_data = match.group(2)  # Extract base64 content
            
            messages[0]["content"] = [
                {"type": "text", "text": user_input},
                {"type": "image_url", "image_url": {"url": f"data:image/{image_format};base64,{image_data}"}}
            ]
    
    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=2000
        )
        assistant_response = response.choices[0].message.content
        return jsonify({"response": assistant_response})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    """
    Simple health check endpoint
    """
    return jsonify({"status": "healthy"})

if __name__ == '__main__':
    # Test the OpenAI client when starting in development
    try:
        test_client = get_openai_client()
        print("OpenAI client initialized successfully")
    except Exception as e:
        print(f"Warning: OpenAI client initialization error: {str(e)}")
        
    app.run(host='0.0.0.0', port=5007, debug=False)