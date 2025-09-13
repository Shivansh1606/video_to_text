from flask import Flask, request, render_template, jsonify, send_file
import os
import uuid
import threading
from moviepy.editor import VideoFileClip
import speech_recognition as sr

app = Flask(__name__)

UPLOAD_FOLDER = 'uploads'
TEXT_FOLDER = 'texts'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(TEXT_FOLDER, exist_ok=True)

progress_data = {}

def convert_media_to_text(file_id, media_path, text_path):
    try:
        progress_data[file_id] = {"status": "processing", "progress": 0, "filename": os.path.basename(text_path)}

        # Extract audio if video, else just process audio file
        ext = os.path.splitext(media_path)[1].lower()
        if ext in ['.mp4', '.mov', '.avi', '.mkv', '.flv', '.wmv']:
            clip = VideoFileClip(media_path)
            audio_path = os.path.join(UPLOAD_FOLDER, f"{file_id}_audio.wav")
            clip.audio.write_audiofile(audio_path)
            clip.close()
        else:
            audio_path = media_path

        progress_data[file_id]["progress"] = 30

        recognizer = sr.Recognizer()
        with sr.AudioFile(audio_path) as source:
            audio_data = recognizer.record(source)

        progress_data[file_id]["progress"] = 70

        try:
            text = recognizer.recognize_google(audio_data)
        except sr.UnknownValueError:
            text = "Sorry, could not understand the audio."
        except sr.RequestError:
            text = "Speech recognition service error."

        with open(text_path, 'w', encoding='utf-8') as f:
            f.write(text)

        progress_data[file_id]["progress"] = 100
        progress_data[file_id]["status"] = "done"

        # Cleanup audio & media files
        if ext in ['.mp4', '.mov', '.avi', '.mkv', '.flv', '.wmv']:
            os.remove(audio_path)
        os.remove(media_path)

    except Exception as e:
        progress_data[file_id]["status"] = "error"
        progress_data[file_id]["error"] = str(e)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload():
    if 'media' not in request.files:
        return jsonify({"error": "No media part"}), 400
    file = request.files['media']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    file_id = str(uuid.uuid4())
    filename = f"{file_id}{os.path.splitext(file.filename)[1]}"
    media_path = os.path.join(UPLOAD_FOLDER, filename)
    text_filename = f"{file_id}.txt"
    text_path = os.path.join(TEXT_FOLDER, text_filename)

    file.save(media_path)

    # Start conversion in background thread
    threading.Thread(target=convert_media_to_text, args=(file_id, media_path, text_path)).start()

    return jsonify({"id": file_id})

@app.route('/status/<file_id>')
def status(file_id):
    data = progress_data.get(file_id)
    if not data:
        return jsonify({"error": "Invalid ID"}), 404
    return jsonify(data)

@app.route('/download/<filename>')
def download(filename):
    path = os.path.join(TEXT_FOLDER, filename)
    if os.path.exists(path):
        return send_file(path, as_attachment=True)
    return "File not found", 404

@app.route('/text/<filename>')
def get_text(filename):
    path = os.path.join(TEXT_FOLDER, filename)
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    return "Text file not found", 404

if __name__ == '__main__':
    app.run(debug=True)
