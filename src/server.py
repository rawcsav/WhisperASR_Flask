import atexit
import threading

from flask import Flask, render_template_string, request, get_flashed_messages, \
    send_from_directory, redirect, url_for, flash
from werkzeug.exceptions import RequestEntityTooLarge
from main import transcribe_files
import os
import shutil
import tempfile
import time

# Initiate Flask app
app = Flask(__name__)
app.secret_key = 'supersecretkey'  # Secret key for Flask's flash mechanism
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB
SUPPORTED_FORMATS = [".mp3", ".mp4", ".mpeg", ".mpga", ".m4a", ".wav", ".webm"]  # List of supported audio formats

# Global set to track temporary directories
temp_dirs = set()

index_html = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Transcription Service</title>
    <!-- The rest of the styles remain the same -->
</head>
<body>
    <div class="navbar">
        <h1>Transcription Service</h1>
    </div>

    <div class="container">
        <form action="/transcribe" method="post" enctype="multipart/form-data">
            <label for="audio_files">Select individual audio files:</label>
            <div class="file-input-wrapper">
                <label for="audio_files" class="file-input-button">Choose Files</label>
                <input type="file" name="audio_files" id="audio_files" multiple>
            </div>
            <label for="api_key">OpenAI API Key:</label>
            <input type="password" name="api_key" id="api_key" required>
            <br><br>
            <button type="submit">Transcribe</button>
        </form>
    </div>
</body>
</html>
'''

@app.route('/', methods=['GET'])
def index():
    messages = get_flashed_messages()
    return render_template_string(index_html, messages=messages)


@app.route('/transcribe', methods=['POST'])
def transcribe():
    # Get the uploaded files and API key from the request
    audio_files = request.files.getlist('audio_files')
    audio_directory = request.files.getlist('audio_directory')
    api_key = request.form.get('api_key')

    # Flash a message about receiving the files
    flash("Received files. Checking for supported formats...", "info")

    # Create temporary directory for output and input
    output_directory = tempfile.mkdtemp()
    input_directory = tempfile.mkdtemp()

    # Store directory creation timestamp
    temp_dirs.add((output_directory, time.time()))
    temp_dirs.add((input_directory, time.time()))

    # Merge the content of the audio files and the audio_directory based on user's choice
    all_uploads = audio_files if audio_files else audio_directory

    # Filter out files that are not in supported formats
    valid_files = [uploaded_file for uploaded_file in all_uploads if
                   os.path.splitext(uploaded_file.filename)[1] in SUPPORTED_FORMATS]

    if not valid_files:
        flash("No supported audio files selected!", "error")
        return redirect(url_for('index'))

    # Flash a message about saving the valid files
    flash("Saving valid audio files for transcription...", "info")

    for uploaded_file in valid_files:
        file_path = os.path.join(input_directory, uploaded_file.filename)
        uploaded_file.save(file_path)

    # Provide a status update to the user
    flash("Transcription started. Please wait...", "info")

    # Call the transcribe_files function
    transcribe_files(input_directory, output_directory, api_key)
    shutil.rmtree(input_directory)
    # Provide a status update to the user
    flash("Transcription completed!", "success")

    # Redirect to the results page
    return redirect(url_for('results', output_dir=output_directory))

@app.route('/results', methods=['GET'])
def results():
    output_directory = request.args.get('output_dir')
    files = os.listdir(output_directory)
    return render_template_string('''
    <h2>Transcription Results</h2>
    <ul>
    {% for file in files %}
        <li><a href="{{ url_for('download', filename=file, output_dir=output_directory) }}">{{ file }}</a></li>
    {% endfor %}
    </ul>
    <p><a href="{{ url_for('index') }}">Go Back</a></p>
    ''', files=files, output_directory=output_directory)


@app.route('/download/<filename>', methods=['GET'])
def download(filename):
    output_directory = request.args.get('output_dir')
    response = send_from_directory(output_directory, filename, as_attachment=True)
    os.remove(os.path.join(output_directory, filename))

    # Check if directory is empty and remove it if it is
    if not os.listdir(output_directory):
        os.rmdir(output_directory)

    return response

@app.errorhandler(RequestEntityTooLarge)
def file_too_large(e):
    flash("File is too large! Please upload files less than 100MB.", "error")
    return redirect(url_for('index'))

def cleanup():
    current_time = time.time()
    # Define a threshold in seconds for how old a directory should be before it's deleted
    # For example, 1 hour = 3600 seconds
    threshold = 3600
    dirs_to_remove = []
    for directory, timestamp in temp_dirs:
        if current_time - timestamp > threshold:
            shutil.rmtree(directory, ignore_errors=True)
            dirs_to_remove.append((directory, timestamp))
    # Remove deleted directories from the temp_dirs set
    for directory in dirs_to_remove:
        temp_dirs.remove(directory)

def periodic_cleanup(interval=3600):  # Default to 1 hour
    while True:
        time.sleep(interval)
        cleanup()

cleanup_thread = threading.Thread(target=periodic_cleanup)
cleanup_thread.daemon = True  # Daemonize thread to close when main process exits
cleanup_thread.start()
