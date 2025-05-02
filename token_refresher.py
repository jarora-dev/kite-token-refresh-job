"""
token_refresher.py  – Cloud-Run Job that:
  1) uses Playwright to log in to Kite Web with credentials + TOTP
  2) grabs ?request_token=… from the redirect URL
  3) calls kite.generate_session() to get ACCESS_TOKEN
  4) saves it as a *new version* of Secret Manager secret
Runs in < 90 s, then exits.
"""
import os, sys, time, datetime as dt, urllib.parse, asyncio, base64
from kiteconnect import KiteConnect
from google.cloud import secretmanager
from playwright.async_api import async_playwright

API_KEY      = os.environ["KITE_API_KEY"]
API_SECRET   = os.environ["KITE_API_SECRET"]
USER_ID      = os.environ["KITE_USER_ID"]
PASSWORD     = os.environ["KITE_PASSWORD"]
TOTP_SECRET  = os.environ["KITE_TOTP_SECRET"]    # 32-char base32 from “Can’t scan?” link
SECRET_NAME  = os.environ.get("ACCESS_SECRET_NAME", "kite_access_token")
PROJECT_ID   = os.environ["GOOGLE_CLOUD_PROJECT"]

def hotp(secret: str, for_time: int) -> str:                        # RFC 6238 TOTP
    import hmac, hashlib, struct
    key = base64.b32decode(secret, True)
    msg = struct.pack(">Q", int(for_time / 30))
    h = hmac.new(key, msg, hashlib.sha1).digest()
    o = h[19] & 15
    code = (struct.unpack(">I", h[o:o+4])[0] & 0x7fffffff) % 1_000_000
    return f"{code:06d}"

async def fetch_request_token() -> str:
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto("https://kite.zerodha.com/")
        await page.fill('input[id="userid"]', USER_ID)
        await page.fill('input[id="password"]', PASSWORD)
        await page.click('button[type="submit"]')
        await page.fill('input[placeholder="••••••"]', hotp(TOTP_SECRET, time.time()))
        await page.click('button[type="submit"]')
        # Wait until redirect with request_token happens
        await page.wait_for_url("**/authenticate*", timeout=10000)
        parsed = urllib.parse.urlparse(page.url)
        token = urllib.parse.parse_qs(parsed.query)["request_token"][0]
        await browser.close()
        return token

async def main():
    print("🔐  Logging in headlessly …")
    token = await fetch_request_token()
    kite = KiteConnect(api_key=API_KEY)
    sess = kite.generate_session(request_token=token, api_secret=API_SECRET)
    access = sess["access_token"]
    print("✅  Got ACCESS_TOKEN, pushing to Secret Manager …")
    client = secretmanager.SecretManagerServiceClient()
    parent = f"projects/{PROJECT_ID}/secrets/{SECRET_NAME}"
    client.add_secret_version(parent=parent, payload={"data": access.encode()})
    print("🎉  New version added, job complete")

if __name__ == "__main__":
    asyncio.run(main())
