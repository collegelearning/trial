import os
import subprocess
import platform
import webbrowser
import threading
import psutil
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
server_ip = "200.0.2.141"
port = 7000
CORS(app, resources={r"/*": {"origins": f"http://{server_ip}:{port}"}})  # Corrected CORS
WEB_APP_URL = f"http://{server_ip}:{port}/login"

# Get the current user running this instance
try:
    current_user = os.getlogin()
except Exception:
    current_user = None  # Fallback

def open_web_app():
    """Opens the web app in Google Chrome"""
    webbrowser.open(WEB_APP_URL)

def get_active_user():
    """Returns the currently active (interactive) user"""
    active_user = None
    for session in psutil.users():
        if session.terminal:  # Ensures it's an interactive session
            active_user = session.name
            break
    return active_user

def open_file_in_active_user_session(file_path):
    """Ensures the file opens in the currently active user's session"""
    active_user = get_active_user()
    
    if not active_user or active_user != current_user:
        return {"error": f"Inactive user session. Active user: {active_user}"}, 403

    try:
        system_platform = platform.system()

        if system_platform == "Windows":
            # Ensure the file opens in the current active user's session
            subprocess.Popen(
                f'start "" "{file_path}"', shell=True, close_fds=True
            )
        elif system_platform == "Darwin":
            subprocess.Popen(["open", file_path])
        elif system_platform == "Linux":
            subprocess.Popen(["xdg-open", file_path])
        else:
            return {"error": f"Unsupported OS: {system_platform}"}, 500

        return {"message": f"Opened: {file_path}"}, 200
    except Exception as e:
        return {"error": str(e)}, 500

@app.route('/open', methods=['POST'])
def open_file():
    data = request.json
    file_path = data.get('file_path')

    if not isinstance(file_path, str) or not file_path.strip():
        return jsonify({"error": "Invalid file_path format"}), 400

    if not os.path.exists(file_path):
        return jsonify({"error": "File not found"}), 404

    # Ensure only the active user opens the file
    response, status = open_file_in_active_user_session(file_path)
    return jsonify(response), status

if __name__ == '__main__':
    threading.Thread(target=open_web_app, daemon=True).start()
    app.run(host='0.0.0.0', port=7001)
