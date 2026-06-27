"""
YouTube -> MP3 downloader backend.

IMPORTANT: Only use this on content you have the rights to download
(your own videos, Creative Commons-licensed content, public domain
media, or anything else you have permission for). Downloading
copyrighted content without permission can violate YouTube's Terms
of Service and copyright law.

Requires ffmpeg installed and on PATH:
  - macOS:   brew install ffmpeg
  - Ubuntu:  sudo apt install ffmpeg
  - Windows: https://ffmpeg.org/download.html
"""

import os
import uuid
import shutil
import zipfile
import threading

from flask import Flask, request, jsonify, send_file

import yt_dlp

app = Flask(__name__, static_folder="static", static_url_path="")

DOWNLOAD_DIR = os.path.join(os.path.dirname(__file__), "downloads")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# In-memory job tracker. For production, swap this for Redis/DB.
# jobs[job_id] = {"status": "queued|downloading|done|error", "file": path, "is_zip": bool, "error": str, "title": str}
jobs = {}


def run_download(url: str, job_id: str):
    job_folder = os.path.join(DOWNLOAD_DIR, job_id)
    os.makedirs(job_folder, exist_ok=True)

    def progress_hook(d):
        if d.get("status") == "downloading" and job_id in jobs:
            jobs[job_id]["status"] = "downloading"
            pct = d.get("_percent_str", "").strip()
            if pct:
                jobs[job_id]["progress"] = pct

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": os.path.join(job_folder, "%(playlist_index)s - %(title)s.%(ext)s"),
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }],
        "quiet": True,
        "no_warnings": True,
        "progress_hooks": [progress_hook],
        "ignoreerrors": True,  # skip unavailable videos in a playlist instead of aborting
    }

    try:
        jobs[job_id]["status"] = "downloading"
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            jobs[job_id]["title"] = info.get("title", "download")

        mp3_files = [f for f in os.listdir(job_folder) if f.lower().endswith(".mp3")]

        if not mp3_files:
            raise RuntimeError("No audio was downloaded. The link may be invalid, private, or region-locked.")

        if len(mp3_files) == 1:
            jobs[job_id]["file"] = os.path.join(job_folder, mp3_files[0])
            jobs[job_id]["is_zip"] = False
        else:
            zip_path = os.path.join(DOWNLOAD_DIR, f"{job_id}.zip")
            with zipfile.ZipFile(zip_path, "w") as zf:
                for f in mp3_files:
                    zf.write(os.path.join(job_folder, f), arcname=f)
            jobs[job_id]["file"] = zip_path
            jobs[job_id]["is_zip"] = True

        jobs[job_id]["status"] = "done"

    except Exception as e:
        jobs[job_id]["status"] = "error"
        jobs[job_id]["error"] = str(e)


@app.route("/")
def index():
    return app.send_static_file("index.html")


@app.route("/api/download", methods=["POST"])
def start_download():
    data = request.get_json(silent=True) or {}
    url = (data.get("url") or "").strip()

    if not url:
        return jsonify({"error": "Please provide a URL."}), 400
    if "youtube.com" not in url and "youtu.be" not in url:
        return jsonify({"error": "That doesn't look like a YouTube URL."}), 400

    job_id = uuid.uuid4().hex
    jobs[job_id] = {"status": "queued"}

    thread = threading.Thread(target=run_download, args=(url, job_id), daemon=True)
    thread.start()

    return jsonify({"job_id": job_id})


@app.route("/api/status/<job_id>")
def status(job_id):
    job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "Job not found."}), 404
    # Don't leak internal file paths to the client
    safe = {k: v for k, v in job.items() if k != "file"}
    return jsonify(safe)


@app.route("/api/file/<job_id>")
def get_file(job_id):
    job = jobs.get(job_id)
    if not job or job.get("status") != "done":
        return jsonify({"error": "File isn't ready yet."}), 400

    if job.get("is_zip"):
        download_name = f"{job.get('title', 'playlist')}.zip"
    else:
        download_name = os.path.basename(job["file"])

    return send_file(job["file"], as_attachment=True, download_name=download_name)


@app.route("/api/cleanup/<job_id>", methods=["POST"])
def cleanup(job_id):
    """Optional: call after the user has downloaded their file to free disk space."""
    job = jobs.pop(job_id, None)
    if job:
        job_folder = os.path.join(DOWNLOAD_DIR, job_id)
        if os.path.isdir(job_folder):
            shutil.rmtree(job_folder, ignore_errors=True)
        zip_path = os.path.join(DOWNLOAD_DIR, f"{job_id}.zip")
        if os.path.isfile(zip_path):
            os.remove(zip_path)
    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(debug=True, port=5000)
