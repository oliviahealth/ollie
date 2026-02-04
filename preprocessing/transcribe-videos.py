import os
import speech_recognition as sr
from moviepy.editor import VideoFileClip
import tempfile

input_folder = 'video-files'
output_folder = 'transcribed-files'

recognizer = sr.Recognizer()

for file in os.listdir(input_folder):
    
    if file.lower().endswith(('.mp4', '.mov')):
        video_path = os.path.join(input_folder, file)
        
        try:
            # extract audio only (as .wav)
            video = VideoFileClip(video_path)
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=True) as temp_audio_file:
                temp_audio_path = temp_audio_file.name
                video.audio.write_audiofile(temp_audio_path)

                # transcribe audio
                with sr.AudioFile(temp_audio_path) as source:
                    audio = recognizer.record(source)
                    try:
                        text = recognizer.recognize_google(audio)
                    except sr.UnknownValueError:
                        text = "Could not understand audio"
                        # make a list of vids that wasn't able to be transcribed
                        with open('transcribed-err.txt', 'a') as txt_err_file:
                            txt_err_file.write(file + '\n')
                    except sr.RequestError as e:
                        text = f"Error with the request: {e}"
        
            # save transcription to corresponding txt
            txt_filename = os.path.splitext(file)[0] + '.txt'
            txt_path = os.path.join(output_folder, txt_filename)
            with open(txt_path, 'w') as txt_file:
                txt_file.write(text)
        
            print(f'Transcription for {file} saved as {txt_filename}')
        
        except Exception as e:
            print(f"An error occurred while processing {file}: {e}")
