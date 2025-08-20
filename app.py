from flask import Flask, render_template, request, redirect, url_for, send_from_directory, jsonify
import os
import uuid
import qrcode
from io import BytesIO
import base64
from werkzeug.utils import secure_filename
from datetime import datetime
from pyngrok import ngrok, conf
import threading
import time

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB limit
app.config['ALLOWED_EXTENSIONS'] = {
    'image': ['png', 'jpg', 'jpeg', 'gif'],
    'video': ['mp4', 'webm', 'ogg'],
    'document': ['pdf', 'doc', 'docx', 'txt', 'csv', 'xls', 'xlsx', 'ppt', 'pptx']
}

# Ngrok configuration
NGROK_AUTHTOKEN = "31O4mreUYd7RZxUgucG4uicpGIp_6m6cc53y1wAW48JeoNMuC"
NGROK_URL = None

def start_ngrok():
    global NGROK_URL
    try:
        # Configure ngrok authtoken
        conf.get_default().auth_token = NGROK_AUTHTOKEN
        conf.get_default().region = "us"  # You can change to "eu", "ap", etc.

        # Start ngrok tunnel
        ngrok_tunnel = ngrok.connect(5000)
        NGROK_URL = ngrok_tunnel.public_url
        print(f"\n * Ngrok tunnel running at: {NGROK_URL}")
        print(" * Use this URL to access your app from any device!")
    except Exception as e:
        print(f"\n * Ngrok error: {str(e)}")
        print(" * Continuing without ngrok - QR codes will only work locally")

def allowed_file(filename, file_type):
    if '.' not in filename:
        return False
    ext = filename.rsplit('.', 1)[1].lower()
    return ext in app.config['ALLOWED_EXTENSIONS'].get(file_type, [])

def generate_qr_code(data, fill_color='#6c5ce7', back_color='#ffffff'):
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color=fill_color, back_color=back_color)
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/generate', methods=['POST'])
def generate():
    content_type = request.form.get('content_type')
    unique_id = str(uuid.uuid4())
    color = request.form.get('color', '#6c5ce7')  # Default purple
    bg_color = request.form.get('bg_color', '#ffffff')  # Default white
    
    if content_type == 'text':
        text = request.form.get('text')
        if not text:
            return jsonify({'error': 'Text content is required'}), 400
        
        # Store text in a file
        filename = f"{unique_id}.txt"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        with open(filepath, 'w') as f:
            f.write(text)
        
        qr_data = text
    
    elif content_type == 'url':
        url = request.form.get('url')
        if not url:
            return jsonify({'error': 'URL is required'}), 400
        
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        
        qr_data = url
    
    elif content_type in ['image', 'video', 'document']:
        if 'file' not in request.files:
            return jsonify({'error': 'No file uploaded'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No selected file'}), 400
        
        if file and allowed_file(file.filename, content_type):
            ext = secure_filename(file.filename).rsplit('.', 1)[1].lower()
            filename = f"{unique_id}.{ext}"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            
            # Use ngrok URL if available, otherwise local URL
            if NGROK_URL:
                qr_data = f"{NGROK_URL}/files/{filename}"
            else:
                qr_data = url_for('get_file', filename=filename, _external=True)
        else:
            return jsonify({'error': 'Invalid file type'}), 400
    else:
        return jsonify({'error': 'Invalid content type'}), 400
    
    qr_code = generate_qr_code(qr_data, fill_color=color, back_color=bg_color)
    
    return jsonify({
        'qr_code': qr_code,
        'content_type': content_type,
        'content_id': unique_id,
        'qr_data': qr_data,
        'timestamp': datetime.now().isoformat(),
        'color_used': color,
        'bg_color_used': bg_color,
        'public_url': NGROK_URL if NGROK_URL else "Local server only"
    })

@app.route('/files/<filename>')
def get_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    # Ensure upload directory exists
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    
    # Start ngrok in a separate thread
    if os.environ.get('WERKZEUG_RUN_MAIN') != 'true':
        ngrok_thread = threading.Thread(target=start_ngrok)
        ngrok_thread.daemon = True
        ngrok_thread.start()
    
    # Run Flask app
    app.run(host='0.0.0.0', port=5000, debug=True)