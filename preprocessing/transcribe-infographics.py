from pdf2image import convert_from_path
from PIL import Image
import pytesseract
import os

input_folder = 'infographics'
output_folder = 'transcribed-infographics'

if not os.path.exists(output_folder):
    os.makedirs(output_folder)

def transcribe_image(image):
    try:
        text = pytesseract.image_to_string(image)
        return text
    except Exception as e:
        print(f"Error during transcription: {e}")
        return ""

def process_pdf(pdf_path):
    images = convert_from_path(pdf_path)
    full_transcription = ""

    for i, image in enumerate(images):
        print(f"Transcribing {os.path.basename(pdf_path)} page {i+1}...")
        transcription = transcribe_image(image)
        full_transcription += transcription + "\n"

    # save transcription to corresponding txt
    output_file_path = os.path.join(output_folder, f"{os.path.basename(pdf_path)}.txt")
    with open(output_file_path, "w") as text_file:
        text_file.write(full_transcription)
    # print(f"Saved full transcription for {os.path.basename(pdf_path)}.\n")

for filename in os.listdir(input_folder):
    file_path = os.path.join(input_folder, filename)

    if filename.endswith(".pdf"):
        print(f"Processing PDF: {filename}")
        process_pdf(file_path)

    elif filename.endswith(".jpg") or filename.endswith(".jpeg") or filename.endswith(".png"):
        # print(f"Processing image: {filename}")
        with Image.open(file_path) as img:
            transcription = transcribe_image(img)

        output_file_path = os.path.join(output_folder, f"{filename}.txt")
        with open(output_file_path, "w") as text_file:
            text_file.write(transcription)
        print(f"Saved transcription for {filename}.\n")

print("All files processed and cleaned up.")
