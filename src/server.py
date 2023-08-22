from flask import Flask, render_template, request, get_flashed_messages, \
    send_from_directory, redirect, url_for, flash
from processing import TranscriptionFailedException
from werkzeug.exceptions import RequestEntityTooLarge
from main import transcribe_files, check_api_key
from apscheduler.schedulers.background import BackgroundScheduler
import os
import time
import shutil
import tempfile
from werkzeug.utils import secure_filename
import contextlib

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)
#app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB

CLEANUP_THRESHOLD_SECONDS = 3600
SUPPORTED_FORMATS = (".mp3", ".mp4", ".mpeg", ".mpga", ".m4a", ".wav", ".webm")

temp_dirs = set()

class FileNotFoundError(Exception):
    pass


@app.route('/', methods=['GET'])
def index():
    messages = get_flashed_messages()
    return render_template("index.html", messages=messages)


@app.route('/transcribe', methods=['POST'])
def transcribe():
    audio_files = request.files.getlist('audio_files')
    api_key = request.form.get('api_key')
    use_timestamps = request.form.get('use_timestamps') == 'yes'
    language = request.form.get('language')
    translate = request.form.get('translate') == 'yes'

    # Validate API key
    if not check_api_key(api_key):
        flash("Invalid API key! Please check your API key and try again.", "error")
        return redirect(url_for('index'))

    if not audio_files or not api_key:
        flash("Please upload audio files and provide an API key.", "error")
        return redirect(url_for('index'))

    valid_files = [file for file in audio_files if file.filename.endswith(SUPPORTED_FORMATS)]

    if not valid_files:
        flash("No supported audio files selected!", "error")
        return redirect(url_for('index'))

    # Corrected indentation starts here
    output_directory = tempfile.mkdtemp(prefix="output_")  # Add prefix to output directory
    input_directory = tempfile.mkdtemp(prefix="input_")  # Add prefix to input directory

    temp_dirs.add((output_directory, time.time()))
    temp_dirs.add((input_directory, time.time()))

    for uploaded_file in valid_files:
        filename = secure_filename(uploaded_file.filename)
        file_path = os.path.join(input_directory, filename)
        uploaded_file.save(file_path)

    try:
        transcribe_files(input_directory, output_directory, api_key, use_timestamps, language, translate)
        print(
            f"Transcription completed! Input directory: {input_directory}, Output directory: {output_directory}")  # Add this line
    except TranscriptionFailedException as e:
        flash(str(e), "error")
        return redirect(url_for('index'))

    return redirect(url_for('results', output_dir=output_directory))


@app.route('/results', methods=['GET'])
def results():
    output_directory = request.args.get('output_dir')
    print(f"Output directory: {output_directory}")

    if not output_directory:
        flash("Missing output directory.", "error")
        return redirect(url_for('index'))

    try:
        files = os.listdir(output_directory)
        print(f"Files: {files}")
    except FileNotFoundError:
        flash("Output directory not found.", "error")
        return redirect(url_for('index'))

    return render_template("results.html", files=files, output_directory=output_directory)

@app.route('/download/<filename>', methods=['GET'])
def download(filename):
    output_directory = request.args.get('output_dir')  # Correctly retrieving from query parameters

    if not output_directory:
        flash("Missing output directory.", "error")
        return redirect(url_for('index'))

    file_path = os.path.join(output_directory, filename)

    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {filename}")

    response = send_from_directory(output_directory, filename, as_attachment=True)
    os.remove(file_path)

    if not os.listdir(output_directory):
        os.rmdir(output_directory)
        temp_dirs.discard((output_directory, time.time()))

    return response


#@app.errorhandler(RequestEntityTooLarge)
#def file_too_large(e):
    #flash("File is too large! Please upload files less than 50MB.", "error")
    #return redirect(url_for('index'))


@app.errorhandler(TranscriptionFailedException)
def handle_transcription_failed(e):
    flash("Transcription failed! Please check your API key and try again.", "error")
    return redirect(url_for('index'))


@app.errorhandler(FileNotFoundError)
def handle_file_not_found(e):
    flash("File not found! Please check your uploaded files and try again.", "error")
    return redirect(url_for('index'))


def cleanup():
    current_time = time.time()
    dirs_to_remove = {(directory, timestamp) for directory, timestamp in temp_dirs if
                      current_time - timestamp > CLEANUP_THRESHOLD_SECONDS and (directory.startswith('input_') or directory.startswith('output_'))}

    for directory, _ in dirs_to_remove:
        shutil.rmtree(directory, ignore_errors=True)

    temp_dirs.difference_update(dirs_to_remove)

def start_cleanup_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(cleanup, 'interval', seconds=CLEANUP_THRESHOLD_SECONDS)
    scheduler.start()

if __name__ == '__main__':
    start_cleanup_scheduler()
    app.run(debug=True)
