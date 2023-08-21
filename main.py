from processing import process_audio_file, process_transcripts
import os
import asyncio
import openai
import warnings

warnings.simplefilter('ignore')

def transcribe_files(input_directory, output_directory, openai_api_key):
    supported_formats = (".mp3", ".mp4", ".mpeg", ".mpga", ".m4a", ".wav", ".webm")

    if os.path.isdir(input_directory):
        files = [f for f in os.listdir(input_directory) if f.endswith(supported_formats)]
    else:
        files = [input_directory] if input_directory.endswith(supported_formats) else []

    if not files:
        raise ValueError("No supported audio files found.")

    openai.api_key = openai_api_key

    async def transcribe_async():
        loop = asyncio.get_running_loop()
        tasks = [loop.run_in_executor(None, process_audio_file, filename, input_directory, openai_api_key) for filename in files]
        results = await asyncio.gather(*tasks)

        for transcripts, filename in zip(results, files):
            basename, _ = os.path.splitext(filename)
            txt_filename = f"{basename}.txt"
            txt_file_path = os.path.join(output_directory, txt_filename)

            with open(txt_file_path, "w") as txt_file:
                txt_file.write(transcripts)

            new_txt_filename = f"{basename}.txt"
            new_txt_file_path = os.path.join(output_directory, new_txt_filename)

            process_transcripts(transcripts, new_txt_file_path)

    asyncio.run(transcribe_async())