from processing import process_audio_file, process_transcripts, TranscriptionFailedException
from pathlib import Path
import os
import asyncio
import openai
from typing import List
import requests


# Add check_api_key function to validate the api_key
def check_api_key(api_key: str) -> bool:
    openai.api_key = api_key

    try:
        headers = {
            'Authorization': f'Bearer {api_key}',
        }
        response = requests.get('https://api.openai.com/v1/models', headers=headers)
        if response.status_code == 200:
            return True
    except requests.exceptions.RequestException:
        return False
    # (uncomment the above lines if using OpenAI library)


def transcribe_files(input_directory: str,
                     output_directory: str,
                     openai_api_key: str,
                     use_timestamps: bool = True,
                     language: str = 'en',
                     translate: bool = False) -> List[str]:
    supported_formats = (".mp3", ".mp4", ".mpeg", ".mpga", ".m4a", ".wav", ".webm")
    input_path = Path(input_directory)

    if input_path.is_dir():
        files = [f for f in os.listdir(input_directory) if f.endswith(supported_formats)]
    else:
        files = [input_directory] if input_directory.endswith(supported_formats) else []

    if not files:
        raise ValueError("No supported audio files found.")

    openai.api_key = openai_api_key

    async def transcribe_async():
        loop = asyncio.get_running_loop()
        tasks = [loop.run_in_executor(None, process_audio_file, filename, input_directory, openai_api_key, use_timestamps, language, translate) for filename in files]
        try:
            results = await asyncio.gather(*tasks)
        except Exception as e:
            # raise TranscriptionFailedException if there's an error in the asynchronous transcription process
            raise TranscriptionFailedException(str(e))

        for transcripts, filename in zip(results, files):
            basename = os.path.splitext(filename)[0]
            txt_filename = f"{basename}.txt"
            txt_file_path = os.path.join(output_directory, txt_filename)

            with open(txt_file_path, "w") as txt_file:
                txt_file.write(transcripts)

            if use_timestamps:
                process_transcripts(transcripts, txt_file_path)

    asyncio.run(transcribe_async())
