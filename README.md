# WhisperAPI Flask Server

This transcription service uses OpenAI's Whisper API to transcribe audio files to text. It supports several audio formats, splits large files into smaller parts, and generates a webpage where users can upload their audio files and download transcribed, formatted text files with subtitles. 

## Features

- Transcription of audio files using OpenAI's Whisper API
- Support for multiple audio formats: .mp3, .mp4, .mpeg, .mpga, .m4a, .wav, .webm
- Handles large files by splitting them into smaller parts
- Formatted SRT subtitling
- Flask-based web interface for uploading and downloading files
- Memory conscious through automatic cleanup of temporary directories

## Requirements

- Flask
- Pydub
- OpenAI Python package
- Flask
- 
## Overview

The transcription service consists of three main parts:

1. `processing.py`: Core functionality for transcribing audio files, splitting large files, and parsing/formatting transcripts.
2. `main.py`: A script that uses the functions from `processing.py` to transcribe files in a directory and save the transcripts.
3. `app.py`: A Flask web application that provides a user interface for uploading and downloading files, and calls the transcription functions from `processing.py`.
   
## Usage

1. Clone this repository and navigate to its directory.

```bash
git clone https://github.com/your_username/transcription-service.git
cd WhisperASR_Flask
```
2. Use the following command to install the required packages:

```bash
pip install -r requirements.txt
```

3. Run the Flask application:

```bash
python server.py
```

4. Open your web browser and go to http://127.0.0.1:5000

5. Enter your API key, upload your audio files using the web interface, then wait for the transcription to finish. The transcribed text files will be available for download.
