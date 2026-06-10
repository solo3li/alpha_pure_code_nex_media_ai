from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import os
import tempfile
import traceback
import logging
import requests
from werkzeug.utils import secure_filename
from openai import OpenAI

app = Flask(__name__)
CORS(app)


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# API Key for authentication
API_KEY = "G7OaZvkf906gDS6skW9mCnxvOLOnWnc8"

# Initialize OpenAI client
# Make sure to set your OpenAI API key as an environment variable
openai_client = None

# Darijat API Configuration
DARIJAT_API_KEY = "1|UhPDOocWKIW8Q767wWD17Z0cK15cmHNQ"
DARIJAT_API_URL = "https://tts.darijat.com/api/v1/external/generate-audio"

def initialize_openai_client():
    """Initialize OpenAI client with API key"""
    global openai_client
    try:
        # Get OpenAI API key from environment variable
        openai_api_key = os.getenv("OPENAI_API_KEY", "")
        if not openai_api_key:
            raise ValueError("OPENAI_API_KEY environment variable is not set")
        
        openai_client = OpenAI(api_key=openai_api_key)
        logger.info("OpenAI client initialized successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to initialize OpenAI client: {e}")
        return False

if not initialize_openai_client():
    logger.warning("OpenAI client initialization failed on startup")

def authenticate_request():
    """Check if the request has valid API key"""
    api_key = request.headers.get('X-API-Key')
    if api_key != API_KEY:
        return False
    return True

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    try:
        if openai_client is None:
            if not initialize_openai_client():
                return jsonify({
                    "status": "error", 
                    "message": "OpenAI client initialization failed"
                }), 500
        
        return jsonify({"status": "healthy", "openai_client": "initialized"}), 200
    except Exception as e:
        return jsonify({
            "status": "error", 
            "message": f"Health check failed: {str(e)}"
        }), 500

@app.route('/api/generate_openai_audio', methods=['POST'])
def generate_openai_audio():
    """Generate audio from text using OpenAI TTS API"""
    
    # Authenticate request
    if not authenticate_request():
        return jsonify({"error": "Invalid API key"}), 401
    
    try:
        # Initialize OpenAI client if not already done
        global openai_client
        if openai_client is None:
            if not initialize_openai_client():
                return jsonify({"error": "OpenAI TTS service is not available"}), 503
        
        # Get request data
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400
        
        text = data.get('text', '')
        voice = data.get('voice', 'alloy')
        model = data.get('model', 'tts-1')
        speed = data.get('speed', 1.0)
        format = data.get('format', 'mp3')
        instructions = data.get('instructions', '')
        user_id = data.get('user_id', 'unknown')
        
        logger.info("=== OpenAI TTS generation request started ===")
        logger.info(f"Parameters - text: '{text[:50]}...', voice: '{voice}', model: '{model}', speed: {speed}, format: '{format}', user_id: '{user_id}'")
        
        # Validate required parameters
        if not text:
            return jsonify({"error": "Text parameter is required"}), 400
        
        if len(text) > 4096:
            return jsonify({"error": "Text exceeds OpenAI's 4096 character limit"}), 400
        
        # Validate voice
        valid_voices = ['alloy', 'ash', 'ballad', 'coral', 'echo', 'fable', 
                       'nova', 'onyx', 'sage', 'shimmer', 'verse']
        if voice not in valid_voices:
            return jsonify({"error": f"Invalid voice. Must be one of: {', '.join(valid_voices)}"}), 400
        
        # Validate model
        valid_models = ['tts-1', 'tts-1-hd', 'gpt-4o-mini-tts']
        if model not in valid_models:
            return jsonify({"error": f"Invalid model. Must be one of: {', '.join(valid_models)}"}), 400
        
        # Validate speed
        if not (0.25 <= speed <= 4.0):
            return jsonify({"error": "Speed must be between 0.25 and 4.0"}), 400
        
        # Validate format
        valid_formats = ['mp3', 'opus', 'aac', 'flac', 'wav', 'pcm']
        if format not in valid_formats:
            return jsonify({"error": f"Invalid format. Must be one of: {', '.join(valid_formats)}"}), 400
        
        logger.info(f"Generating audio for user: {user_id}, voice: {voice}, model: {model}")
        
        try:
            # Prepare OpenAI TTS request parameters
            tts_params = {
                "model": model,
                "input": text,
                "voice": voice,
                "response_format": format,
                "speed": speed
            }
            
            # Add instructions only for gpt-4o-mini-tts model
            if model == 'gpt-4o-mini-tts' and instructions.strip():
                tts_params["instructions"] = instructions.strip()
                logger.info(f"Added instructions: {instructions}")
            
            logger.info(f"Calling OpenAI TTS API with params: {tts_params}")
            
            # Call OpenAI TTS API
            response = openai_client.audio.speech.create(**tts_params)
            
            logger.info("OpenAI TTS API call successful")
            
            # Create temporary file to store the audio
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=f'.{format}')
            
            # Write the audio content to temporary file
            temp_file.write(response.content)
            temp_file.close()
            
            temp_audio_path = temp_file.name
            
            logger.info(f"Audio file created at: {temp_audio_path}")
            
            # Check if the file exists and has content
            if not os.path.exists(temp_audio_path):
                logger.error(f"Generated audio file not found at: {temp_audio_path}")
                return jsonify({"error": "Generated audio file not found"}), 500
            
            # Get file size for logging
            file_size = os.path.getsize(temp_audio_path)
            logger.info(f"Audio file size: {file_size} bytes")
            
            if file_size == 0:
                logger.error("Generated audio file is empty")
                return jsonify({"error": "Generated audio file is empty"}), 500
            
            # Return the file as response
            try:
                return send_file(
                    temp_audio_path,
                    as_attachment=True,
                    download_name=f"{user_id}_output_audio.{format}",
                    mimetype=f'audio/{format}' if format != 'mp3' else 'audio/mpeg'
                )
            except Exception as send_error:
                logger.error(f"Error sending file: {send_error}")
                return jsonify({"error": "Error sending audio file"}), 500
                
        except Exception as openai_error:
            logger.error(f"OpenAI TTS API error: {openai_error}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            
            # Handle specific OpenAI API errors
            error_message = str(openai_error)
            if "rate limit" in error_message.lower():
                return jsonify({"error": "OpenAI API rate limit exceeded. Please try again later."}), 429
            elif "quota" in error_message.lower():
                return jsonify({"error": "OpenAI API quota exceeded. Please check your billing."}), 402
            elif "authentication" in error_message.lower() or "unauthorized" in error_message.lower():
                return jsonify({"error": "OpenAI API authentication failed. Please check your API key."}), 401
            elif "invalid" in error_message.lower():
                return jsonify({"error": f"Invalid request to OpenAI API: {error_message}"}), 400
            else:
                return jsonify({"error": f"OpenAI TTS generation failed: {error_message}"}), 500
            
    except Exception as e:
        logger.error(f"Unexpected error in generate_openai_audio: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({"error": "An unexpected error occurred"}), 500

@app.route('/api/generate_darijat_audio', methods=['POST'])
def generate_darijat_audio():
    """Generate Arabic audio from text using Darijat TTS API"""
    
    # Authenticate request
    if not authenticate_request():
        return jsonify({"error": "Invalid API key"}), 401
    
    try:
        # Get request data
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400
        
        text = data.get('text', '')
        voice_name = data.get('voice_name')
        human_simulation = data.get('human_simulation', True)
        style_instruction = data.get('style_instruction', '')
        user_id = data.get('user_id', 'unknown')
        
        logger.info("=== Darijat Arabic TTS generation request started ===")
        logger.info(f"Parameters - text: '{text[:50]}...', voice_name: '{voice_name}', style_instruction: '{style_instruction}', user_id: '{user_id}'")
        
        # Validate required parameters
        if not text:
            return jsonify({"error": "Text parameter is required"}), 400
        
        if not voice_name:
            return jsonify({"error": "voice_name parameter is required"}), 400
        
        logger.info(f"Generating Darijat audio for user: {user_id}, voice: {voice_name}")
        
        try:
            # Prepare Darijat API request
            darijat_payload = {
                "text": text,
                "voice_name": voice_name,
                "human_simulation": human_simulation,
            }

            if style_instruction.strip():
                darijat_payload["style_instruction"] = style_instruction.strip()

            logger.info(f"Calling Darijat API with payload: {darijat_payload}")

            # Use a session with retries
            session = requests.Session()
            from requests.adapters import HTTPAdapter
            from urllib3.util.retry import Retry

            retries = Retry(
                total=3,
                backoff_factor=1,
                status_forcelist=[429, 502, 503, 504],
                allowed_methods=["POST"],
            )
            adapter = HTTPAdapter(max_retries=retries)
            session.mount("https://", adapter)

            try:
                resp = session.post(
                    DARIJAT_API_URL,
                    json=darijat_payload,
                    headers={
                        "Authorization": f"Bearer {DARIJAT_API_KEY}",
                        "Content-Type": "application/json",
                        "Accept": "application/json",
                    },
                    timeout=(30, 240),
                    stream=True,
                )
            except requests.exceptions.ConnectTimeout:
                logger.error("Connection to Darijat timed out")
                return jsonify({"error": "Connection timeout to Arabic TTS service"}), 504
            except requests.exceptions.ReadTimeout:
                logger.error("Read timeout waiting for Darijat response")
                return jsonify({"error": "Arabic TTS service is taking too long"}), 504
            except requests.exceptions.RequestException as e:
                logger.error(f"Request to Darijat failed: {e}")
                return jsonify({"error": "Failed to call Arabic TTS service"}), 503

            logger.info(f"Darijat API response status: {resp.status_code}")

            if resp.status_code != 200:
                try:
                    error_data = resp.json()
                    error_message = error_data.get('error', error_data.get('message', str(error_data)))
                except Exception:
                    error_message = f"Darijat API returned status {resp.status_code}"
                logger.error(f"Darijat API error: {error_message}")
                return jsonify({"error": error_message}), resp.status_code

            # Handle response — could be JSON with audio_url or direct audio
            content_type = resp.headers.get('content-type', '')

            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3')

            if 'application/json' in content_type:
                resp_data = resp.json()
                audio_url = resp_data.get('audio_url') or resp_data.get('url') or resp_data.get('data', {}).get('audio_url')
                
                if audio_url:
                    logger.info(f"Got audio URL from Darijat: {audio_url}")
                    audio_resp = session.get(audio_url, stream=True, timeout=(30, 240))
                    audio_resp.raise_for_status()
                    
                    for chunk in audio_resp.iter_content(chunk_size=4096):
                        if chunk:
                            temp_file.write(chunk)
                else:
                    temp_file.close()
                    os.unlink(temp_file.name)
                    return jsonify({"error": f"Darijat returned JSON without audio: {resp_data}"}), 500
            else:
                for chunk in resp.iter_content(chunk_size=4096):
                    if chunk:
                        temp_file.write(chunk)

            temp_file.close()
            temp_audio_path = temp_file.name

            file_size = os.path.getsize(temp_audio_path)
            logger.info(f"Darijat audio file size: {file_size} bytes")

            if file_size == 0:
                logger.error("Generated audio file is empty")
                return jsonify({"error": "Generated audio file is empty"}), 500

            return send_file(
                temp_audio_path,
                as_attachment=True,
                download_name=f"{user_id}_arabic_audio.mp3",
                mimetype='audio/mpeg',
            )

        except requests.exceptions.Timeout:
            logger.error("Darijat API request timeout")
            return jsonify({"error": "Request timeout from Arabic TTS service"}), 504
        except requests.exceptions.ConnectionError as conn_error:
            logger.error(f"Darijat API connection error: {conn_error}")
            return jsonify({"error": "Cannot connect to Arabic TTS service"}), 503
        except Exception as darijat_error:
            logger.error(f"Darijat API error: {darijat_error}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return jsonify({"error": f"Arabic TTS generation failed: {str(darijat_error)}"}), 500
            
    except Exception as e:
        logger.error(f"Unexpected error in generate_darijat_audio: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({"error": "An unexpected error occurred"}), 500

@app.route('/api/test_openai', methods=['POST'])
def test_openai_endpoint():
    """Test endpoint for OpenAI TTS"""
    if not authenticate_request():
        return jsonify({"error": "Invalid API key"}), 401
    
    try:
        # Initialize OpenAI client if not already done
        global openai_client
        if openai_client is None:
            if not initialize_openai_client():
                return jsonify({"error": "OpenAI client initialization failed"}), 500
        
        data = request.get_json()
        text = data.get('text', 'Hello world, this is a test of OpenAI text to speech.')
        
        logger.info("Testing OpenAI TTS API...")
        
        # Test the OpenAI TTS API call
        response = openai_client.audio.speech.create(
            model="tts-1",
            voice="alloy",
            input=text,
            response_format="mp3"
        )
        
        # Create temporary file
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3')
        temp_file.write(response.content)
        temp_file.close()
        
        file_size = os.path.getsize(temp_file.name)
        
        # Clean up
        os.unlink(temp_file.name)
        
        return jsonify({
            "status": "success",
            "message": "OpenAI TTS test completed successfully",
            "file_size": file_size,
            "text_length": len(text)
        })
        
    except Exception as e:
        logger.error(f"OpenAI TTS test failed: {e}")
        return jsonify({
            "status": "error",
            "error": str(e),
            "traceback": traceback.format_exc()
        })

@app.route('/api/debug', methods=['GET'])
def debug_environment():
    """Debug endpoint to check environment"""
    import sys
    import platform
    
    try:
        # Check OpenAI client
        openai_status = "Available" if openai_client else "Not initialized"
        
        # Check environment variables
        openai_key_set = "Yes" if os.getenv('OPENAI_API_KEY') else "No"
        
    except Exception as e:
        openai_status = f"Error: {e}"
        openai_key_set = "Error checking"
    
    return jsonify({
        "python_version": sys.version,
        "platform": platform.platform(),
        "openai_client_status": openai_status,
        "openai_api_key_set": openai_key_set,
        "working_directory": os.getcwd(),
        "temp_directory": tempfile.gettempdir()
    })

# Initialize OpenAI client on startup



if __name__ == '__main__':
    # Initialize OpenAI client
    initialize_openai_client()
    app.run(host='0.0.0.0', port=5008, debug=True)