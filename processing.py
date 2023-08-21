import openai
import os
from pydub import AudioSegment
import re

initial_prompt="Hello, welcome to my lecture."

def convert_to_mp3(file_path):
    basename, extension = os.path.splitext(file_path)
    mp3_file_path = f"{basename}.mp3"

    if extension.lower() in ['.mp4', '.mpeg', '.mpga', '.m4a', '.wav', '.webm']:
        audio = AudioSegment.from_file(file_path, extension.lower().lstrip('.'))
        audio.export(mp3_file_path, format="mp3")
        return mp3_file_path
    else:
        return file_path


def transcribe_with_retry(audio_file, prompt):
    success = False
    transcript = None
    max_retries = 3
    retry_count = 0

    while not success and retry_count < max_retries:
        try:
            transcript = openai.Audio.transcribe("whisper-1", audio_file, response_format="srt", language="en",
                                                 prompt=prompt)
            success = True
        except Exception as e:
            print(f"Error: {e}. Retrying...")
            retry_count += 1

    if not success:
        print("Max retries reached. Failed to transcribe audio.")

    return transcript
def parse_transcript_text(transcript_srt):
    parsed_subtitles = parse_subtitles(transcript_srt)
    transcribed_text = ""
    for subtitle, text in parsed_subtitles:
        transcribed_text += text + " "
    return transcribed_text.strip()

def process_audio_file(filename, input_directory, openai_api_key):
    max_file_size = 25 * 1024 * 1024  # 25 MB
    supported_formats = (".mp3", ".mp4", ".mpeg", ".mpga", ".m4a", ".wav", ".webm")
    file_path = os.path.join(input_directory, filename)
    file_size = os.path.getsize(file_path)

    openai.api_key = openai_api_key

    # If the file is a compatible format and is smaller than 25MB
    if file_size <= max_file_size and filename.endswith(supported_formats):
        with open(file_path, "rb") as audio_file:
            return transcribe_with_retry(audio_file, prompt=initial_prompt)

    # If the file is larger than 25MB and is a compatible format but not an MP3
    elif file_size > max_file_size and filename.endswith(supported_formats) and not filename.endswith(".mp3"):
        mp3_file_path = convert_to_mp3(file_path)
        os.remove(file_path)

    # If the file is an MP3 and is larger than 25MB
    elif file_size > max_file_size and filename.endswith(".mp3"):
        mp3_file_path = file_path

    else:
        return None  # Return None or handle other file types accordingly

    # Check file size of mp3_file_path and split if necessary
    file_size = os.path.getsize(mp3_file_path)
    if file_size > max_file_size:
        file_parts = split_large_file(mp3_file_path)
        os.remove(mp3_file_path)
        transcripts_parts = []
        prompt=''

        for part_idx, part_file in enumerate(file_parts):
            with open(part_file, "rb") as audio_file:
                transcript_part = transcribe_with_retry(audio_file, prompt=prompt)
                transcripts_parts.append(transcript_part)

            # Reset the prompt to an empty string for all parts except the first one
            if part_idx == 0:
                prompt = "Hello, welcome to my lecture."
            else:
                prompt = ""

            # Update prompt with transcribed text for the next part
            if transcript_part is not None:
                prompt += parse_transcript_text(transcript_part)

            # Delete the part after transcribing
            os.remove(part_file)

        # Append transcripts and maintain timestamps
        # Append transcripts and maintain timestamps
        transcripts = ''
        timestamp_offset = 0

        for part_transcripts in transcripts_parts:
            parsed_subtitles = parse_subtitles(part_transcripts)
            last_timestamp = 0
            last_end_timestamp = 0

            for subtitle, text in parsed_subtitles:
                match = re.search(r'(\d+:\d+:\d+,\d+)\s+-->\s+(\d+:\d+:\d+,\d+)', subtitle)
                if match:
                    start_timestamp = match.group(1)
                    end_timestamp = match.group(2)
                    start_time = timestamp_to_ms(start_timestamp)
                    end_time = timestamp_to_ms(end_timestamp)
                else:
                    print(f"Failed to find timestamp in subtitle: {subtitle}")
                    continue

                new_start_time = ms_to_timestamp(start_time + timestamp_offset)
                new_end_time = ms_to_timestamp(end_time + timestamp_offset)

                new_subtitle = subtitle.replace(start_timestamp, new_start_time)
                new_subtitle = new_subtitle.replace(end_timestamp, new_end_time)

                transcripts += new_subtitle + "\n" + text + "\n\n"

                last_end_timestamp = end_time

            timestamp_offset += last_end_timestamp

        return transcripts

def parse_subtitles(content):
    parsed_subtitles = re.findall(r'(\d+\n\d+:\d+:\d+,\d+ --> \d+:\d+:\d+,\d+\n(.*?)(?:\n|\Z))', content, re.DOTALL)
    if not parsed_subtitles:
        print(f"Error: Unable to parse subtitles from content: {content}")
    return parsed_subtitles


def is_full_sentence(text):
    return text.strip() and text[-1] in '.!?'

def format_timestamp(timestamp):
    timestamp = timestamp[:-4]
    h, m, s = map(int, timestamp.split(':'))
    if h > 0:
        return f'{h:02d}:{m:02d}:{s:02d}'
    else:
        return f'{m:02d}:{s:02d}'


def process_subtitles(subtitles):
    new_subtitles = []
    subtitle_buffer = ''
    start_time = ''
    end_time = ''

    for subtitle, text in subtitles:
        if not start_time:
            start_time = re.search(r'(\d+:\d+:\d+,\d+) -->', subtitle).group(1)

        subtitle_buffer += ' ' + text.strip()

        if is_full_sentence(subtitle_buffer):
            end_time = re.search(r'--> (\d+:\d+:\d+,\d+)', subtitle).group(1)
            new_subtitles.append((start_time, end_time, subtitle_buffer.strip()))
            subtitle_buffer = ''
            start_time = ''
            end_time = ''

    return new_subtitles


def export_subtitles(subtitles, filename):
    with open(filename, 'w') as f:
        for start, end, text in subtitles:
            start = format_timestamp(start)
            end = format_timestamp(end)
            f.write(f'[{start} - {end}] {text}\n\n')


def timestamp_to_ms(timestamp):
    hours, minutes, remaining = timestamp.split(':')
    seconds, milliseconds = remaining.split(',')
    total_ms = int((int(hours) * 3600 + int(minutes) * 60 + float(seconds)) * 1000 + int(milliseconds))
    return total_ms


def ms_to_timestamp(ms):
    seconds, milliseconds = divmod(ms, 1000)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{int(hours):02d}:{int(minutes):02d}:{int(seconds):02d},{int(milliseconds):03d}"


def split_large_file(file_path):
    split_duration_ms = 24 * 60 * 1000  # 24 minutes
    audio = AudioSegment.from_file(file_path)
    file_basename, _ = os.path.splitext(file_path)
    file_parts = []

    for i in range(0, len(audio), split_duration_ms):
        part = audio[i:i + split_duration_ms]
        part_filename = f"{file_basename}_part{i // split_duration_ms}.mp3"
        part.export(part_filename, format="mp3")
        file_parts.append(part_filename)

    return file_parts


def process_transcripts(content, output_file):
    parsed_subtitles = parse_subtitles(content)
    formatted_subtitles = process_subtitles(parsed_subtitles)
    export_subtitles(formatted_subtitles, output_file)