import re
from playwright.sync_api import sync_playwright
from dataclasses import dataclass
import re
import subprocess
import time
import requests

@dataclass
class m3u8_link:
    url: str
    referer: str

def match_m3u8(request) -> str:
    #print(request.url)
    pattern = r"\.m3u8(\?.*)?$"
    if re.search(pattern, request.url):
        print(f"FOUND M3U8 URL!!!: {request.url}")
    

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
            with page.expect_request(lambda req: ".m3u8" in req.url, timeout=timeout) as request_info:
                page.goto(url=url, wait_until="domcontentloaded")
                page.wait_for_timeout(4000)

            request = request_info.value
            referer = request.headers.get("referer", url)
            user_agent = request.headers.get("user-agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0")

            cookies = context.cookies()
            cookie_str = "; ".join([f"{c['name']}={c['value']}" for c in cookies])

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


def save_stream_to_file(m3u8: m3u8_link, output_file: str = "output.mp4"):
    if not m3u8 or not m3u8.url:
        print("[!] No valid m3u8 link provided.")
        return

    ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

    ffmpeg_cmd = [
        "ffmpeg",
        "-y",
        "-user_agent",
        ua,
        "-referer",
        m3u8.referer,
        "-allowed_segment_extensions",
        "ALL",
        "-allowed_extensions",
        "ALL",
        "-reconnect",
        "1",
        "-reconnect_at_eof",
        "1",
        "-reconnect_streamed",
        "1",
        "-reconnect_delay_max",
        "5",
        "-i",
        m3u8.url,
        "-c",
        "copy",
        "-bsf:a",
        "aac_adtstoasc",
        output_file,
    ]

    print(
        f"\n[+] Recording stream via FFmpeg into '{output_file}'... Press"
        " Ctrl+C to stop.\n"
    )
    try:
        process = subprocess.Popen(ffmpeg_cmd)
        process.wait()
    except KeyboardInterrupt:
        print("\n[+] Finalizing video file...")
    finally:
        print(f"[+] Recording stopped. Saved to {output_file}")


url = "https://tvsportslive.fr/62470-2/"
m3u8 = get_m3u8_url(url)
print(m3u8.referer)
print(m3u8.url)
save_stream_to_file(m3u8=m3u8)