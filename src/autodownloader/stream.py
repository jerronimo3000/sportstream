from playwright.sync_api import sync_playwright,Page,Browser,Request
import time
import subprocess
import requests


def new_webpage():
    p = sync_playwright().start()
    browser = p.chromium.launch(
        headless=False,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--autoplay-policy=no-user-gesture-required"
        ]
    )
    context = browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        viewport={"width": 3840, "height": 2160}
    )    

    page = context.new_page()
    return page


START_JS = """
() => {
  const video = document.querySelector('video');
  const stream = video.captureStream();
  const recorder = new MediaRecorder(stream, {mimeType: 'video/webm'});
  window.__chunks = [];
  recorder.ondataavailable = e => window.__chunks.push(e.data);
  recorder.start(1000);
  window.__recorder = recorder;
}
"""

STOP_JS = """
async () => {
  const recorder = window.__recorder;
  const done = new Promise(r => recorder.onstop = r);
  recorder.stop();
  await done;
  const blob = new Blob(window.__chunks, {type: 'video/webm'});
  const buf = new Uint8Array(await blob.arrayBuffer());
  let bin = '';
  for (let i = 0; i < buf.length; i += 0x8000) {
    bin += String.fromCharCode(...buf.subarray(i, i + 0x8000));
  }
  return btoa(bin);
}
"""


import base64

def start_recording(page):
    page.evaluate(START_JS)

def stop_recording(page, path):
    data = page.evaluate(STOP_JS)
    with open(path, "wb") as f:
        f.write(base64.b64decode(data))

def record(page, seconds, path):
    print("starting recording")
    start_recording(page)
    page.wait_for_timeout(seconds * 1000)
    stop_recording(page, path)

def find_video_frame(page):
    for frame in page.frames:
        if frame.query_selector("video"):
            return frame
    return None

def wait_for_video_frame(page, seconds=30):
    for _ in range(seconds):
        frame = find_video_frame(page)
        if frame:
            return frame
        page.wait_for_timeout(1000)
    return None

def build_headers(headers: dict[str,str]) -> str:
    clean_headers = {
        k: v for k, v in headers.items()
        if not k.startswith(":") and k not in ("host", "content-length")
    }

    return clean_headers


def build_headers_str(headers: dict[str,str]) -> str:
    return "".join(f"{k}: {v}\r\n" for k,v in headers.items())

def change_txt(playlist: str) -> str:
    lines = playlist.splitlines()
    new_lines = []
    for line_raw in lines:
        line = line_raw.strip()
        if ".txt" in line:
            new_line = line.replace(".txt",".ts")
            new_lines.append(new_line)
        else:
            new_lines.append(line_raw)
    return "\n".join(new_lines)

def write_playlist(playlist: str):
    with open("index.m3u8","w") as f:
        f.write(playlist)

page = new_webpage()
with page.expect_request(lambda r: "application" in r.url) as req_info:
    page.goto("https://crackstreams.mx/stream/charlotte-hornets-vs-phoenix-suns")
request = req_info.value
headers_clean = build_headers(request.all_headers())
playlist = requests.get(request.url,headers=headers_clean,timeout=15).text
playlist_fixed = change_txt(playlist).rstrip() + "\n#EXT-X-ENDLIST\n"
write_playlist(playlist)
print(request.url)
headers_str = build_headers_str(headers_clean)
cmd = [
    "ffmpeg", "-y", "-nostdin",
    "-protocol_whitelist", "file,http,https,tcp,tls,crypto",
    "-allowed_extensions", "ALL",
    "-extension_picky", "0",
    "-headers", build_headers_str(headers_clean),
    "-i", request.url,
    "-c", "copy",
    "test.ts",
]
result = subprocess.run(cmd, capture_output=True, text=True)
print("return code:", result.returncode)
print(result.stderr[-3000:])   # the useful part is at the end