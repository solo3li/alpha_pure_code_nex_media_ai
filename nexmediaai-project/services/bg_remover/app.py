from flask import Flask, request, jsonify, send_file
import os
import uuid
import time
from rembg import remove
from PIL import Image
import io

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = '/tmp/uploads'
app.config['PROCESSED_FOLDER'] = '/tmp/processed'
API_KEY = "GPukTcc2FXcAo32U6j6y5rOK8LJW5QAf"

@app.before_request
def authenticate():
    if request.headers.get('X-Api-Key') != API_KEY:
        return jsonify({'error': 'Unauthorized'}), 401

# Route for uploading and saving image
@app.route('/upload', methods=['POST'])
def upload_image():
    start_time = time.time()

    try:
        # Validate file
        if 'image' not in request.files:
            return jsonify({'error': 'No image provided'}), 400

        file = request.files['image']
        if file.filename == '':
            return jsonify({'error': 'Empty filename'}), 400

        # Save image to temporary folder
        filename = file.filename
        upload_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(upload_path)

        return jsonify({
            'success': True,
            'filename': filename,
            'upload_path': upload_path,
            'processing_time': round(time.time() - start_time, 2)
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# Route for processing the image after upload
@app.route('/process', methods=['POST'])
def process_image():
    start_time = time.time()

    try:
        # Validate filename
        data = request.get_json()
        filename = data.get('filename')
        if not filename:
            return jsonify({'error': 'No filename provided'}), 400

        # Construct file path
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        if not os.path.exists(file_path):
            return jsonify({'error': 'File not found'}), 404

        # Process image
        img = Image.open(file_path)
        original_size = img.size

        # Remove background
        output = remove(img)

        # Save output
        user_id = request.headers['X-User-ID']
        output_filename = f"bgremoved_{user_id}_{uuid.uuid4().hex[:8]}.png"
        output_path = os.path.join(app.config['PROCESSED_FOLDER'], output_filename)
        output.save(output_path)

        return jsonify({
            'success': True,
            'output_filename': output_filename,
            'output_path': output_path,
            'original_width': original_size[0],
            'original_height': original_size[1],
            'processing_time': round(time.time() - start_time, 2)
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# Add security headers
@app.after_request
def add_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Content-Security-Policy'] = "default-src 'self'"
    return response

# Healthcheck route
@app.route('/healthcheck')
def healthcheck():
    """New endpoint for monitoring"""
    return jsonify({'status': 'healthy'})

if __name__ == '__main__':
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(app.config['PROCESSED_FOLDER'], exist_ok=True)
    app.run(host='0.0.0.0', port=5000)
