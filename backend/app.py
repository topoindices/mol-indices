from flask import Flask, request, jsonify, session, redirect, url_for
import os, re, logging, tempfile
from flask_cors import CORS
from authlib.integrations.flask_client import OAuth
import processor
import json
from functools import wraps
import shutil
import time

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', '48176aa6387c857025fc16c0807cbbdbdbabd88547e1fca8bef17603d86cef29')
ADMIN_EMAILS = [e.strip().lower() for e in os.environ.get('ADMIN_EMAILS', 'anthuvanjoseph21@gmail.com').split(',')]
CONTACT_EMAIL = os.environ.get('CONTACT_EMAIL', 'anthuvanjoseph21@gmail.com')

# Add session cookie configuration
app.config.update(
    SESSION_COOKIE_SAMESITE='None',
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True
)

# CORS Configuration
CORS(app, resources={
    r"/*": {
        "origins": os.environ.get('FRONTEND_URL', 'http://localhost:3000'),
        "supports_credentials": True
    }
})

# OAuth setup
oauth = OAuth(app)
google = oauth.register(
    name='google',
    client_id=os.environ.get('GOOGLE_CLIENT_ID'),
    client_secret=os.environ.get('GOOGLE_CLIENT_SECRET'),
    access_token_url='https://accounts.google.com/o/oauth2/token',
    authorize_url='https://accounts.google.com/o/oauth2/auth',
    api_base_url='https://www.googleapis.com/oauth2/v1/',
    client_kwargs={
        'scope': 'email profile',
        'redirect_uri': os.environ.get('REDIRECT_URI', 'http://localhost:5000/auth/google/callback')
    },
)

# Persistent storage
PERSISTENT_STORAGE = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'usage_data')
os.makedirs(PERSISTENT_STORAGE, exist_ok=True)
USAGE_FILE = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'usage.json')
usage_data = {}
FRONTEND_URL = os.environ.get('FRONTEND_URL', 'http://localhost:3000')

# Load used emails
if os.path.exists(USAGE_FILE):
    with open(USAGE_FILE, 'r') as f:
        usage_data = json.load(f)

def get_usage_file(email):
    return os.path.join(PERSISTENT_STORAGE, f"{email}.json")

def update_usage(email, mode, file_count):
    usage_file = get_usage_file(email)
    
    if os.path.exists(usage_file):
        with open(usage_file, 'r') as f:
            usage = json.load(f)
    else:
        usage = {'degree': False, 'degreesum': False, 'reverse_degree': False, 
                'scaled_face_degree': False, 'scaled_face_degree_sum': False}
    
    if usage[mode]:
        return False
    
    usage[mode] = True
    with open(usage_file, 'w') as f:
        json.dump(usage, f)
    return True

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        email = session.get('email', '').lower()
        if email not in ADMIN_EMAILS:
            app.logger.warning(f"Admin access denied for {email}")
            return jsonify({'error': 'Admin access required'}), 403
        return f(*args, **kwargs)
    return decorated_function

@app.route('/auth/google')
def google_login():
    redirect_uri = url_for('google_callback', _external=True)
    return google.authorize_redirect(redirect_uri)

@app.route('/auth/google/callback')
def google_callback():
    try:
        token = google.authorize_access_token()
        user_info = google.get('userinfo').json()
        email = user_info['email'].lower()
            
        session['email'] = email
        session.permanent = True
        return redirect(f"{FRONTEND_URL}/?auth=success")
        
    except Exception as e:
        app.logger.error(f"Google auth failed: {str(e)}")
        return redirect(f"{FRONTEND_URL}/?error=auth_failed")

@app.route('/auth/check')
def check_auth():
    email = session.get('email')
    if email:
        is_admin = email.lower() in ADMIN_EMAILS
        return jsonify({'email': email, 'is_admin': is_admin}), 200
    return jsonify({'error': 'Unauthorized'}), 401

@app.route('/health')
def health_check():
    return jsonify({'status': 'healthy'}), 200

@app.route('/upload', methods=['POST'])
def upload():
    try:
        email = session.get('email')
        if not email:
            return jsonify({'error': 'Unauthorized'}), 401

        is_admin = email.lower() in ADMIN_EMAILS  # Updated admin check

        mode = request.form.get('mode', 'degree')
        if mode not in ['degree', 'degreesum', 'reverse_degree', 
                       'scaled_face_degree', 'scaled_face_degree_sum']:
            return jsonify({'error': 'Invalid mode'}), 400
        k = int(request.form.get('k', 1)) if mode == 'reverse_degree' else 1
        files = request.files.getlist('files')
        valid_files = [f for f in files if f.filename.lower().endswith('.mol')]

        # Permanent storage per user
        usage_file = get_usage_file(email)
        if os.path.exists(usage_file):
            with open(usage_file, 'r') as f:
                usage = json.load(f)
        else:
            usage = {'degree': False, 'degreesum': False, 'reverse_degree': False, 
                    'scaled_face_degree': False, 'scaled_face_degree_sum': False}

        # Check if mode already used
        if not is_admin and usage.get(mode, False):
            return jsonify({
                'error': 'limit_exceeded',
                'message': f'Mail to {CONTACT_EMAIL} for further analysis'
            }), 403

        # Process files
        with tempfile.TemporaryDirectory() as temp_dir:
            file_paths = [os.path.join(temp_dir, f.filename) for f in valid_files]
            for file, path in zip(valid_files, file_paths):
                file.save(path)
            
            results = processor.process_uploaded_files(file_paths, mode, k)
            
            if not results:
                return jsonify({'error': 'invalid_file'}), 400

        # Permanent lock for this mode
        if not is_admin:
            usage[mode] = True
            with open(usage_file, 'w') as f:
                json.dump(usage, f)

        return jsonify(results), 200
        
    except Exception as e:
        app.logger.error(f"Upload error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/usage-status')
def usage_status():
    email = session.get('email')
    if not email:
        return jsonify({'error': 'Unauthorized'}), 401
    
    usage_file = get_usage_file(email)
    if os.path.exists(usage_file):
        with open(usage_file, 'r') as f:
            return jsonify(json.load(f))
    return jsonify({'degree': False, 'degreesum': False, 'reverse_degree': False,
           'scaled_face_degree': False, 'scaled_face_degree_sum': False})

@app.route('/admin/reset-usage', methods=['POST'])
@admin_required
def admin_reset_usage():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
            
        user_email = data.get('email', '').strip().lower()
        
        # Validate email format
        if not re.fullmatch(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b', user_email):
            return jsonify({'error': 'Invalid email format'}), 400
            
        # Get user file path
        user_file = get_usage_file(user_email)
        app.logger.info(f"Resetting usage for: {user_email} at {user_file}")
        
        if not os.path.exists(user_file):
            return jsonify({'error': 'User not found or never analyzed files'}), 404
            
        # Reset usage and preserve file
        try:
            with open(user_file, 'w') as f:
                json.dump({'degree': False, 'degreesum': False, 'reverse_degree': False,
                            'scaled_face_degree': False, 'scaled_face_degree_sum': False}, f)
            app.logger.info(f"Successfully reset usage for {user_email}")
            return jsonify({'message': f'Reset successful for {user_email}'}), 200
            
        except Exception as e:
            app.logger.error(f"File write error: {str(e)}")
            return jsonify({'error': 'Failed to update user record'}), 500
            
    except Exception as e:
        app.logger.error(f"Admin reset error: {str(e)}")
        return jsonify({'error': 'Server error'}), 500

@app.route('/clear-cookie')
def clear_cookie():
    response = jsonify({'message': 'Cookie cleared'})
    response.headers['Cache-Control'] = 'no-store, max-age=0'
    response.set_cookie(
        'mol_cookie_test',
        '',
        expires=0,
        samesite='None',
        secure=True
    )
    return response

@app.route('/check-cookies')
def check_cookies():
    response = jsonify({'cookie_enabled': 'mol_cookie_test' in request.cookies})
    response.headers['Cache-Control'] = 'no-store, max-age=0'
    response.headers.extend({
        'Access-Control-Allow-Origin': os.environ.get('FRONTEND_URL', 'http://localhost:3000'),
        'Access-Control-Allow-Credentials': 'true',
        'Vary': 'Origin',
        'Access-Control-Expose-Headers': 'Set-Cookie'
    })
    
    if 'mol_cookie_test' not in request.cookies:
        response.set_cookie(
            'mol_cookie_test',
            f'test_{time.time()}',
            samesite='None',
            secure=True,
            max_age=60,
            httponly=True
        )
    return response
    
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)