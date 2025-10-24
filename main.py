import os
import time
import re
import threading
import json
from typing import Dict, Set
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from playwright.sync_api import sync_playwright
import phonenumbers
import firebase_admin
from firebase_admin import credentials, auth as firebase_auth, firestore

# ============================================================
# 🔥 Firebase Initialization (Render Safe)
# ============================================================

firebase_json = os.getenv("FIREBASE_CREDENTIALS")

if not firebase_json:
    raise RuntimeError("❌ FIREBASE_CREDENTIALS environment variable not set on Render")

try:
    firebase_dict = json.loads(firebase_json)
    cred = credentials.Certificate(firebase_dict)
    if not firebase_admin._apps:
        firebase_admin.initialize_app(cred)
    db = firestore.client()
    print("✅ Firebase initialized successfully")
except Exception as e:
    raise RuntimeError(f"❌ Failed to initialize Firebase: {e}")

# ============================================================
# ⚙️ FastAPI Configuration
# ============================================================

app = FastAPI(title="Numify Backend", version="1.3")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "*",  # 🔥 Allow all during testing; restrict later
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================
# 🌍 Globals
# ============================================================

sessions: Dict[str, Dict] = {}
HEADLESS = os.environ.get("HEADLESS", "true").lower() == "true"
BROWSER_PATH = os.environ.get("BROWSER_PATH")

# ============================================================
# 📞 Helpers
# ============================================================

def extract_numbers(text: str) -> Set[str]:
    """Extract valid 8-digit Tunisian numbers from text."""
    found = set()

    try:
        for match in phonenumbers.PhoneNumberMatcher(text, "TN"):
            number = phonenumbers.format_number(match.number, phonenumbers.PhoneNumberFormat.E164)
            digits_only = re.sub(r"\D", "", number)
            if len(digits_only) == 8:
                found.add(digits_only)
    except Exception:
        pass

    regex = re.compile(r"\b\d{8}\b")
    for m in regex.findall(text):
        found.add(m)

    return found


def verify_token_get_uid_from_header(authorization_header: str) -> str:
    """Verify Firebase ID token from Authorization header."""
    if not authorization_header:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    if not authorization_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid Authorization header")
    id_token = authorization_header.split("Bearer ")[1]
    return verify_firebase_token(id_token)


def verify_firebase_token(id_token: str) -> str:
    """Verify Firebase token and return UID."""
    try:
        decoded = firebase_auth.verify_id_token(id_token)
        return decoded.get("uid")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired ID token")

# ============================================================
# 🤖 Scraper Logic
# ============================================================

def scraper_thread(uid: str, live_url: str):
    """Run TikTok live scraping for one user."""
    seen_comments = set()
    seen_numbers = set()

    print(f"🟢 Scraper thread starting for {uid} -> {live_url} (headless={HEADLESS})")

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=HEADLESS,
                args=["--disable-blink-features=AutomationControlled"],
            )

            context = browser.new_context()
            page = context.new_page()
            page.goto(live_url, timeout=60000)
            time.sleep(8)

            print("⚠️ Waiting for TikTok chat messages to load...")

            sessions[uid]["running"] = True
            sessions[uid].setdefault("numbers", [])

            while sessions[uid]["running"]:
                elements = page.query_selector_all("div[data-e2e='chat-message']")
                if not elements:
                    elements = page.query_selector_all("div[class*='chat']")

                for e in elements:
                    try:
                        text = e.inner_text().strip()
                    except Exception:
                        continue

                    if not text or text in seen_comments:
                        continue
                    seen_comments.add(text)

                    numbers_found = extract_numbers(text)
                    for num in numbers_found:
                        if num not in seen_numbers:
                            seen_numbers.add(num)
                            print(f"📞 Found: {num} → {text[:60]}")

                            data = {"timestamp": firestore.SERVER_TIMESTAMP, "number": num, "message": text}
                            sessions[uid]["numbers"].append(data)

                            # Save to Firestore
                            try:
                                doc_ref = db.collection("extractions").document(uid)
                                db.collection("extractions").document(uid).collection("numbers").add({
                                    "number": num,
                                    "message": text,
                                    "createdAt": firestore.SERVER_TIMESTAMP,
                                })
                                doc_ref.set(
                                    {"liveUrl": live_url, "lastUpdated": firestore.SERVER_TIMESTAMP},
                                    merge=True,
                                )
                            except Exception as e:
                                print("⚠️ Firestore write failed:", e)

                time.sleep(2)

            print(f"🔴 Scraper thread exiting for {uid}")
            browser.close()

    except Exception as e:
        sessions[uid]["running"] = False
        sessions[uid].setdefault("error", str(e))
        print(f"❌ Scraper error for {uid}: {e}")

# ============================================================
# 🧩 API Endpoints
# ============================================================

@app.post("/start")
async def start_scraping(request: Request):
    """Start TikTok live scraping session."""
    uid = verify_token_get_uid_from_header(request.headers.get("authorization"))
    payload = await request.json()
    live_url = payload.get("live_url")

    if not live_url:
        raise HTTPException(status_code=400, detail="Missing live_url")

    user_doc = db.collection("users").document(uid).get()
    if not user_doc.exists:
        raise HTTPException(status_code=403, detail="User record not found")

    user_data = user_doc.to_dict()
    if not user_data.get("approved", False):
        raise HTTPException(status_code=403, detail="User not approved")

    if uid in sessions and sessions[uid].get("running"):
        return JSONResponse({"message": "Already running"}, status_code=400)

    sessions[uid] = {"running": False, "numbers": []}
    t = threading.Thread(target=scraper_thread, args=(uid, live_url), daemon=True)
    t.start()

    print(f"✅ Scraper started for user: {uid}")
    return {"message": "Scraper started"}


@app.post("/stop")
async def stop_scraping(request: Request):
    """Stop user's scraping session."""
    uid = verify_token_get_uid_from_header(request.headers.get("authorization"))
    if uid in sessions:
        sessions[uid]["running"] = False
        print(f"🛑 Scraper stopped for user: {uid}")
        return {"message": "Scraper stopped"}
    return JSONResponse({"message": "No active session"}, status_code=404)


@app.get("/stream")
async def stream_numbers(request: Request):
    """Stream extracted numbers in real-time (SSE)."""
    token = request.query_params.get("token")
    if not token:
        raise HTTPException(status_code=401, detail="Missing ?token param")

    uid = verify_firebase_token(token)

    def event_generator():
        last_index = 0
        while True:
            if uid in sessions:
                numbers = sessions[uid].get("numbers", [])
                if len(numbers) > last_index:
                    for num in numbers[last_index:]:
                        payload = json.dumps({
                            "number": num["number"],
                            "message": num["message"],
                        })
                        yield f"data: {payload}\n\n"
                    last_index = len(numbers)
            time.sleep(1)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/")
def root():
    """Health check endpoint."""
    return {"message": "✅ Numify backend is running on Render"}
