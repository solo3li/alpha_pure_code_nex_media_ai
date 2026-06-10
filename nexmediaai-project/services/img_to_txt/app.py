from flask import Flask, request, jsonify
from werkzeug.utils import secure_filename
from PIL import Image
from transformers import BlipProcessor, BlipForConditionalGeneration
import os
import time
import torch # type: ignore

app = Flask(__name__)

# Configuration
API_KEY = "GPukTcc2FXcAo32U6j6y5rOK8LJW5QAf"
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Initialize the image captioning model once at startup
processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-large")
model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-large")

# Move model to GPU if available
if torch.cuda.is_available():
    model = model.to('cuda')

@app.before_request
def authenticate():
    if request.headers.get('X-Api-Key') != API_KEY:
        return jsonify({'error': 'Unauthorized'}), 401

def generate_caption_from_image(file_path):
    """Generate a caption for the given image using the pre-loaded model."""
    try:
        print(f"Processing image: {file_path}")
        raw_image = Image.open(file_path).convert('RGB')
        
        # Process image using the pre-loaded processor and model
        if torch.cuda.is_available():
            inputs = processor(raw_image, return_tensors="pt").to('cuda')
        else:
            inputs = processor(raw_image, return_tensors="pt")
        
        out = model.generate(**inputs)
        caption = processor.decode(out[0], skip_special_tokens=True)
        
        print(f"Generated caption: {caption}")
        return caption
        
    except Exception as e:
        print(f"Error in generate_caption_from_image: {str(e)}")
        raise

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

        # Secure filename and save
        filename = secure_filename(file.filename)
        user_id = request.headers.get('X-User-ID', 'unknown')
        full_filename = f"{user_id}_{filename}"
        upload_path = os.path.join(app.config['UPLOAD_FOLDER'], full_filename)
        file.save(upload_path)

        return jsonify({
            'success': True,
            'filename': full_filename,
            'upload_path': upload_path,
            'processing_time': round(time.time() - start_time, 2)
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/generate', methods=['POST'])
def generate_caption():
    try:
        # Validate request contains JSON data
        if not request.is_json:
            return jsonify({'error': 'Request must be JSON'}), 400

        data = request.get_json()

        # Validate filename exists and is not None
        if not data or 'filename' not in data or not data['filename']:
            return jsonify({
                'success': False,
                'error': 'Filename is required and cannot be empty',
                'received_data': data
            }), 400

        # Get and validate filename
        filename = str(data['filename']).strip()
        if not filename:
            return jsonify({'error': 'Filename cannot be empty'}), 400

        # Handle path components
        filename = filename.split('/')[-1]  # Take last part if path exists
        filename = filename.split('\\')[-1]  # Handle Windows paths

        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)

        print(f"Looking for file at: {file_path}")
        if not os.path.exists(file_path):
            return jsonify({
                'success': False,
                'error': f'File not found at {file_path}',
                'searched_path': file_path,
                'received_data': data
            }), 404

        caption = generate_caption_from_image(file_path)
        return jsonify({'success': True, 'caption': caption})

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5004)