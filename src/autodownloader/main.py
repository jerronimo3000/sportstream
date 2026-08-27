import re
from playwright.sync_api import sync_playwright,Page,Browser,Request
from dataclasses import dataclass
import re
import subprocess
import time
import requests
import streamlink
from flask import Flask, Response
from streamlink.stream.stream import Stream
from plugins import Sportsurge, Dudestream

@dataclass
class m3u8_link:
    url: str
    referer: str
    user_agent: str
    cookies_header: str

def match_m3u8(request) -> str:
    #print(request.url)
    pattern = r"\.m3u8(\?.*)?$"
    if re.search(pattern, request.url):
        print(f"FOUND M3U8 URL!!!: {request.url}")

def print_request_url(request: Request):
    print(f"URL: {request.url}")

def get_network_requests(url: str):
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,  # Must be False so the player initializes
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

        page = browser.new_page()
        page.on("request",match_m3u8)
        page.goto(url=url,wait_until="domcontentloaded")
        page.wait_for_timeout(timeout=60000)



def get_m3u8_url(
    url: str, timeout: int = 15000, raise_on_missing: bool = False
) -> m3u8_link:
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,  # Must be False so the player initializes
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox"
            ]
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 3840, "height": 2160}
        )    

        page = browser.new_page()

        try:
            print("opening url and waiting for m3u8 request")
            with page.expect_request(lambda req: ".m3u8" in req.url, timeout=timeout) as request_info:
                page.goto(url=url, wait_until="domcontentloaded")
                page.wait_for_timeout(4000)

            request = request_info.value
            referer = request.headers.get("referer", url)
            user_agent = request.headers.get("user-agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0")

            cookies = context.cookies()
            cookie_str = "; ".join([f"{c['name']}={c['value']}" for c in cookies])

            print(f"FOUND M3U8 ULR: {request.url}")
            return m3u8_link(
                url=request.url,
                referer=referer,
                user_agent=user_agent,
                cookies_header=cookie_str
            )
        except Exception as e:
            print(f"[!] Error intercepting M3U8: {e}")
            return None
        finally:
            browser.close()

def get_stream(m3u8: m3u8_link) -> Stream:
    if not m3u8 or not m3u8.url:
        print("[!] Invalid stream object.")
        return

    # Initialize a Streamlink session
    session = streamlink.Streamlink()

    # Configure session options/headers to pass CDN checks
    session.set_option("http-headers", {
        "Referer": m3u8.referer,
        "User-Agent": m3u8.user_agent,
        "Cookie": m3u8.cookies_header
    })
    session.set_option("hls-live-restart", True)

    print(f"[+] Fetching stream tracks from manifest...")
    # Wrap with hlsvariant:// to force HLS parsing
    streams = session.streams(f"hlsvariant://{m3u8.url}")
    
    if "best" not in streams:
        print("[!] No valid stream variant found.")
        return

    stream = streams["best"]
    return stream

def save_stream_to_file(stream: Stream, output_file: str = "output.mp4"):
    print(f"[+] Recording stream into '{output_file}'... Press Ctrl+C to stop.")

    try:
        with stream.open() as stream_fd, open(output_file, "wb") as out_file:
            while True:
                # Read chunks from the stream and write to disk
                data = stream_fd.read(1024 * 64)
                if not data:
                    break
                out_file.write(data)
    except KeyboardInterrupt:
        print("\n[+] Recording stopped by user.")
    finally:
        print(f"[+] File saved: {output_file}")


app = Flask(__name__)

def generate(url: str):

    while True:
        stream_fd = None

        try:
            print("Finding a new M3U8 stream...")
            m3u8 = get_m3u8_url(url)

            if m3u8 is None:
                raise RuntimeError("Could not find M3U8 URL")

            stream = get_stream(m3u8)

            if stream is None:
                raise RuntimeError("Could not find playable stream")

            print("Opening Streamlink stream...")
            stream_fd = stream.open()

            while True:
                data = stream_fd.read(64 * 1024)

                if not data:
                    raise ConnectionError("Stream ended")

                yield data

        except Exception as e:
            print(f"Stream failed: {e!r}")
            print("Retrying in 5 seconds...")
            time.sleep(5)

        finally:
            if stream_fd is not None:
                try:
                    stream_fd.close()
                except Exception:
                    pass

            print("Stream connection closed")

def find_m3u8_link(urls: str, num_retries: int = 5):
    print("Finding a new M3U8 stream...")
    for url in urls:
        for i in range(3):
            m3u8 = get_m3u8_url(url,timeout=5000)
            if m3u8 is not None:
                break
        if m3u8 is not None:
            break

    if m3u8 is None:
        raise RuntimeError("Could not find M3U8 URL")

    return m3u8

@app.get("/restream")
def restream():
    site = Sportsurge()
    url = site.get_current_game_url("buffalo", "tvsportslive")
    # site = Dudestream()
    # url = site.get_current_game_url("ararat")
    print(url)
    return Response(generate(url = url), mimetype="video/mp2t")


#url = "https://v2.streameast.ga/mlb/philadelphia-phillies-vs-seattle-mariners-2/"
#m3u8 = get_m3u8_url(url)
#print(m3u8.referer)
#print(m3u8.url)
#stream = get_stream(m3u8=m3u8)
#save_stream_to_file(stream=stream)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8900)
