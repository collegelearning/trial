import os
import psutil
import subprocess
import platform
import webbrowser
import threading
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
server_ip = "200.0.2.141"
port = 7000
CORS(app, origins=[f"{server_ip}:{port}"])  # Enable CORS only for Server IP
WEB_APP_URL = f"http://{server_ip}:{port}/login"  # URL of the Flask web app

# Get the current logged-in user
current_user = os.getlogin()

def open_web_app():
    """Opens the web app in default browser - Google Chrome"""
    webbrowser.open(WEB_APP_URL)

def stop_previous_listener_process():
    """Terminate any existing listener64.exe process running for a different user"""
    for proc in psutil.process_iter(attrs=['pid', 'username', 'name']):
        if proc.info['name'] == 'listener64.exe' and proc.info['username'] != current_user:
            # If listener64.exe is running for a different user, terminate it
            print(f"Terminating listener64.exe process for user {proc.info['username']}")
            proc.terminate()

@app.route('/open', methods=['POST'])
def open_file():
    data = request.json
    file_path = data.get('file_path')

    # Validate file_path
    if not file_path or not os.path.exists(file_path):
        return jsonify({"error": "Valid file_path is required"}), 400

    try:
        # Determine the OS and open the file accordingly
        system_platform = platform.system()

        if system_platform == "Windows":
            os.startfile(file_path)  # Windows-specific method
        elif system_platform == "Darwin":  # macOS
            subprocess.run(["open", file_path], check=True)
        elif system_platform == "Linux":
            subprocess.run(["xdg-open", file_path], check=True)
        else:
            return jsonify({"error": f"Unsupported OS: {system_platform}"}), 500

        return jsonify({"message": f"Opened: {file_path}"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # Stop previous listener64.exe process if running under a different user
    stop_previous_listener_process()

    # Start the listener (Flask app) for the current user
    threading.Thread(target=open_web_app, daemon=True).start()
    app.run(host='0.0.0.0', port=7001)
