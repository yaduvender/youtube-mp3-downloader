# YouTube → MP3 Downloader

A small Flask tool that converts a YouTube video or playlist link into MP3 file(s).

⚠️ **Use responsibly.** Only download content you have the rights to —
your own uploads, Creative Commons–licensed videos, public domain media,
or anything else you have permission for. Downloading copyrighted content
without permission can violate YouTube's Terms of Service and copyright law.

## Setup

1. **Install ffmpeg** (required for audio conversion):

   * macOS: `brew install ffmpeg`
   * Ubuntu/Debian: `sudo apt install ffmpeg`
   * Windows: download from https://ffmpeg.org/download.html and add it to your PATH
2. **Install Python dependencies:**

```bash
   pip install -r requirements.txt
   ```

3. **Run the server:**

```bash
   python app.py
   ```

4. Open **http://localhost:5000** in your browser.

## How it works

* Paste a YouTube video or playlist URL and click Convert.
* The backend downloads it in the background using `yt-dlp` and converts it
to MP3 with `ffmpeg`.
* Single videos return an `.mp3`; playlists return a `.zip` of all tracks.
* The frontend polls `/api/status/<job\_id>` every 1.5s and shows a download
link once it's ready.

## API endpoints

|Method|Endpoint|Description|
|-|-|-|
|POST|`/api/download`|Body: `{"url": "..."}` → returns `job\_id`|
|GET|`/api/status/<job\_id>`|Returns job status/progress|
|GET|`/api/file/<job\_id>`|Downloads the finished file|
|POST|`/api/cleanup/<job\_id>`|Deletes the job's files from disk|

## Notes \& next steps

* `yt-dlp` is updated frequently to keep up with YouTube changes — if
downloads suddenly start failing, try `pip install -U yt-dlp` first.
* Jobs and files are currently stored in memory/on local disk — fine for
personal/local use, but swap in a real job queue (e.g. Celery + Redis)
and object storage (e.g. S3) before deploying this publicly or at scale.
* Consider adding a cap on playlist size or video length if you deploy
this somewhere others can use it, to avoid runaway disk usage.

