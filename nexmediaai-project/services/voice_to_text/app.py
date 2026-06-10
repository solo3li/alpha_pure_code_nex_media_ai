from flask import Flask, request, jsonify
from openai import OpenAI, APIError
import os
import tempfile
import requests
import logging
import subprocess
import shutil

app = Flask(__name__)

# Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

client = OpenAI(api_key=OPENAI_API_KEY)

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {'.mp3', '.wav', '.m4a', '.mp4', '.webm', '.mov', '.avi'}
MAX_FILE_SIZE = 500 * 1024 * 1024  # 500 MB for input
OPENAI_MAX_SIZE = 25 * 1024 * 1024  # 25 MB OpenAI limit


def check_ffmpeg():
    """Check if ffmpeg is available"""
    return shutil.which('ffmpeg') is not None


def compress_audio(input_path, output_path, target_size_mb=20):
    """Compress audio file to target size using ffmpeg"""
    try:
        if not check_ffmpeg():
            logger.warning("ffmpeg not found, skipping compression")
            return input_path
        
        # Get file duration first
        duration_cmd = [
            'ffprobe', '-i', input_path, '-show_entries', 
            'format=duration', '-v', 'quiet', '-of', 'csv=p=0'
        ]
        
        try:
            duration_result = subprocess.run(duration_cmd, capture_output=True, text=True)
            duration = float(duration_result.stdout.strip())
        except:
            duration = 600  # Default fallback duration (10 minutes)
        
        # Calculate target bitrate
        target_size_bits = target_size_mb * 8 * 1024 * 1024
        target_bitrate = max(16, min(128, int((target_size_bits / duration) / 1000)))  # Between 16k and 128k
        
        logger.info(f"Compressing audio: duration={duration:.1f}s, target_bitrate={target_bitrate}k")
        
        # Compression command with aggressive settings
        compress_cmd = [
            'ffmpeg', '-i', input_path, '-y',
            '-vn',  # No video
            '-acodec', 'mp3',  # Use MP3 codec
            '-ab', f'{target_bitrate}k',  # Audio bitrate
            '-ar', '16000',  # Sample rate (16kHz is sufficient for speech)
            '-ac', '1',  # Mono audio
            '-f', 'mp3',  # Output format
            output_path
        ]
        
        result = subprocess.run(compress_cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            # Check if compressed file is small enough
            compressed_size = os.path.getsize(output_path)
            logger.info(f"Compression successful: {compressed_size / (1024*1024):.1f}MB")
            
            if compressed_size <= OPENAI_MAX_SIZE:
                return output_path
            else:
                # If still too large, try even more aggressive compression
                logger.info("File still too large, applying more aggressive compression")
                return compress_audio_aggressive(input_path, output_path)
        else:
            logger.error(f"FFmpeg error: {result.stderr}")
            return input_path
            
    except Exception as e:
        logger.error(f"Compression error: {e}")
        return input_path


def compress_audio_aggressive(input_path, output_path):
    """Apply very aggressive compression for large files"""
    try:
        # Ultra-compressed settings
        compress_cmd = [
            'ffmpeg', '-i', input_path, '-y',
            '-vn',  # No video
            '-acodec', 'mp3',
            '-ab', '32k',  # Very low bitrate
            '-ar', '8000',  # Very low sample rate (still acceptable for speech)
            '-ac', '1',  # Mono
            '-f', 'mp3',
            output_path
        ]
        
        result = subprocess.run(compress_cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            compressed_size = os.path.getsize(output_path)
            logger.info(f"Aggressive compression: {compressed_size / (1024*1024):.1f}MB")
            return output_path
        else:
            logger.error(f"Aggressive compression failed: {result.stderr}")
            return input_path
            
    except Exception as e:
        logger.error(f"Aggressive compression error: {e}")
        return input_path


def process_audio_file(file_path, original_filename):
    """Process and compress audio file if needed"""
    file_size = os.path.getsize(file_path)
    
    # If file is already small enough, use as-is
    if file_size <= OPENAI_MAX_SIZE:
        logger.info(f"File size OK: {file_size / (1024*1024):.1f}MB")
        return file_path
    
    logger.info(f"File too large: {file_size / (1024*1024):.1f}MB, compressing...")
    
    # Create compressed version
    compressed_path = file_path + '_compressed.mp3'
    final_path = compress_audio(file_path, compressed_path)
    
    # Verify final size
    final_size = os.path.getsize(final_path)
    if final_size > OPENAI_MAX_SIZE:
        logger.warning(f"Compressed file still large: {final_size / (1024*1024):.1f}MB")
        # Could implement file splitting here if needed
    
    return final_path


def allowed_file(filename):
    return any(filename.lower().endswith(ext) for ext in ALLOWED_EXTENSIONS)


def translate_text(text: str, target_language: str) -> str:
    """Translate text using GPT-4o-mini"""
    try:
        # Map language codes to full names for better translation
        language_names = {
            'en': 'English', 'fr': 'French', 'es': 'Spanish', 'de': 'German',
            'it': 'Italian', 'pt': 'Portuguese', 'ru': 'Russian', 'zh': 'Chinese',
            'ja': 'Japanese', 'ko': 'Korean', 'ar': 'Arabic', 'hi': 'Hindi',
            'tr': 'Turkish', 'nl': 'Dutch', 'sv': 'Swedish', 'da': 'Danish',
            'no': 'Norwegian', 'fi': 'Finnish', 'el': 'Greek', 'pl': 'Polish',
        }
        
        target_lang_name = language_names.get(target_language, target_language)
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": f"You are a professional translator. Translate the following text to {target_lang_name}. Maintain the original meaning and tone."},
                {"role": "user", "content": text}
            ]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"Translation API error: {e}")
        return None


@app.route('/health', methods=['GET'])
def health_check():
    ffmpeg_available = check_ffmpeg()
    return jsonify({
        'status': 'healthy',
        'ffmpeg_available': ffmpeg_available,
        'max_input_size_mb': MAX_FILE_SIZE // (1024*1024),
        'openai_max_size_mb': OPENAI_MAX_SIZE // (1024*1024)
    })


@app.route('/transcribe', methods=['POST'])
def transcribe_audio():
    temp_files = []  # Track temp files for cleanup
    
    try:
        if 'audio' not in request.files:
            return jsonify({'error': 'No audio file provided'}), 400

        file = request.files['audio']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400

        if not allowed_file(file.filename):
            return jsonify({'error': 'File type not supported'}), 400

        # Get parameters from request
        should_translate = request.form.get('translate', 'false').lower() == 'true'
        target_language = request.form.get('target', 'en')
        
        logger.info(f"Processing file: {file.filename}, translate={should_translate}, target={target_language}")

        # Validate file size
        file.seek(0, os.SEEK_END)
        file_size = file.tell()
        file.seek(0)
        if file_size > MAX_FILE_SIZE:
            return jsonify({'error': f'File too large. Max {MAX_FILE_SIZE // (1024*1024)}MB'}), 400

        # Save original file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as temp_file:
            file.save(temp_file.name)
            original_temp_path = temp_file.name
            temp_files.append(original_temp_path)

        # Process and compress if needed
        processed_path = process_audio_file(original_temp_path, file.filename)
        if processed_path != original_temp_path:
            temp_files.append(processed_path)

        # Check final size
        final_size = os.path.getsize(processed_path)
        if final_size > OPENAI_MAX_SIZE:
            return jsonify({
                'error': f'File too large after compression ({final_size // (1024*1024)}MB). OpenAI limit is 25MB.'
            }), 400

        try:
            # Step 1: Transcribe
            with open(processed_path, "rb") as audio_file:
                transcript = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    response_format="text",
                    prompt="Transcribe exactly what is said without translation. Preserve the original language, dialect, and exact words spoken."
                )

            result = {
                "success": True,
                "original_text": transcript,
                "file_size_mb": final_size / (1024*1024),
                "was_compressed": processed_path != original_temp_path
            }

            # Step 2: Translate if requested
            if should_translate:
                translated = translate_text(transcript, target_language)
                if translated:
                    result["translated_text"] = translated
                    result["target_language"] = target_language
                else:
                    result["error"] = "Translation failed"

            return jsonify(result)

        finally:
            # Cleanup temp files
            for temp_path in temp_files:
                try:
                    os.unlink(temp_path)
                except:
                    pass

    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        # Cleanup temp files on error
        for temp_path in temp_files:
            try:
                os.unlink(temp_path)
            except:
                pass
        return jsonify({'error': 'Internal server error'}), 500


@app.route('/transcribe-url', methods=['POST'])
def transcribe_from_url():
    temp_files = []
    
    try:
        data = request.get_json()
        if not data or 'url' not in data:
            return jsonify({'error': 'No URL provided'}), 400

        url = data['url']
        should_translate = data.get('translate', False)
        target_language = data.get('target', 'en')
        
        logger.info(f"Processing URL: {url}, translate={should_translate}, target={target_language}")

        # Download
        response = requests.get(url, stream=True)
        response.raise_for_status()

        file_size = int(response.headers.get('content-length', 0))
        if file_size > MAX_FILE_SIZE:
            return jsonify({'error': f'File too large. Max {MAX_FILE_SIZE // (1024*1024)}MB'}), 400

        # Save downloaded file
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            for chunk in response.iter_content(chunk_size=8192):
                temp_file.write(chunk)
            original_temp_path = temp_file.name
            temp_files.append(original_temp_path)

        # Process and compress if needed
        processed_path = process_audio_file(original_temp_path, "downloaded_audio")
        if processed_path != original_temp_path:
            temp_files.append(processed_path)

        # Check final size
        final_size = os.path.getsize(processed_path)
        if final_size > OPENAI_MAX_SIZE:
            return jsonify({
                'error': f'File too large after compression ({final_size // (1024*1024)}MB). OpenAI limit is 25MB.'
            }), 400

        try:
            # Step 1: Transcribe
            with open(processed_path, "rb") as audio_file:
                transcript = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    response_format="text",
                    prompt="Transcribe exactly what is said without translation. Preserve the original language, dialect, and exact words spoken."
                )

            result = {
                "success": True,
                "original_text": transcript,
                "file_size_mb": final_size / (1024*1024),
                "was_compressed": processed_path != original_temp_path
            }

            # Step 2: Translate if requested
            if should_translate:
                translated = translate_text(transcript, target_language)
                if translated:
                    result["translated_text"] = translated
                    result["target_language"] = target_language
                else:
                    result["error"] = "Translation failed"

            return jsonify(result)

        finally:
            # Cleanup temp files
            for temp_path in temp_files:
                try:
                    os.unlink(temp_path)
                except:
                    pass

    except requests.exceptions.RequestException as e:
        logger.error(f"Download error: {e}")
        return jsonify({'error': 'Failed to download file'}), 400
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        # Cleanup temp files on error
        for temp_path in temp_files:
            try:
                os.unlink(temp_path)
            except:
                pass
        return jsonify({'error': 'Internal server error'}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5005, debug=True)