from fastapi import FastAPI, Request, Body, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from pymongo import MongoClient
from datetime import datetime

import os
import re
import base64
import hashlib
import hmac
import numpy as np
import requests  # <-- NEW: API call ke liye
from pathlib import Path
from bson import ObjectId

# ── App setup ──────────────────────────────────────────────────────────────────
app = FastAPI()

app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SESSION_SECRET", "change-this-to-a-long-random-secret")
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # tighten this to your frontend URL in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).resolve().parent
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

# ── MongoDB ────────────────────────────────────────────────────────────────────
MONGO_URI = os.getenv("MONGO_URI")
if not MONGO_URI:
    raise RuntimeError("MONGO_URI environment variable is not set!")

client = MongoClient(MONGO_URI)
db = client["secondbrain"]
users_col = db["users"]
mem_col   = db["memories"]

# ── Hugging Face API Setup (External AI) ───────────────────────────────────────
HF_TOKEN = os.getenv("HF_TOKEN")
# Updated to a more reliable model and correct API endpoint
API_URL = "https://api-inference.huggingface.co/models/sentence-transformers/all-MiniLM-L6-v2"

def get_embedding(text: str) -> list:
    if not HF_TOKEN:
        raise ValueError("HF_TOKEN environment variable is not set in Render!")
    
    headers = {"Authorization": f"Bearer {HF_TOKEN}"}
    response = requests.post(API_URL, headers=headers, json={"inputs": [text]})
    
    if response.status_code == 200:
        result = response.json()
        # API returns a list inside a list for our text
        if isinstance(result, list) and len(result) > 0:
            return result[0]
        return result
    else:
        raise Exception(f"HuggingFace API Error ({response.status_code}): {response.text}")

# ── Auth helpers ───────────────────────────────────────────────────────────────
def hash_password(password: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 200_000)
    return base64.b64encode(salt + dk).decode()

def verify_password(password: str, stored: str) -> bool:
    raw     = base64.b64decode(stored.encode())
    salt    = raw[:16]
    old_dk  = raw[16:]
    new_dk  = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 200_000)
    return hmac.compare_digest(old_dk, new_dk)

def get_current_user(request: Request):
    user = request.session.get("user")
    if not user:
        raise HTTPException(status_code=401, detail="Login required")
    return user

# ── Text utilities ─────────────────────────────────────────────────────────────
STOPWORDS = set("""
a an the is are am was were be been being
i me my mine you your yours we our ours they their theirs
to of in on at for from by with as and or but if then than
this that these those it its
kya kab kaise kahan kyun mera meri tum aap apka apki
""".split())

def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())

def normalize_text(s: str) -> str:
    s = (s or "").lower().strip()
    s = re.sub(r"[^a-z0-9\s#:/.-]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def clean_memory_text(text: str) -> str:
    text = normalize(text)
    if text.lower().startswith("remember "):
        text = text[9:].strip()
    return text

def tokens(s: str):
    s = normalize_text(s)
    return [t for t in s.split() if t and t not in STOPWORDS and not t.startswith("#")]

def suggest_auto_tags(text: str):
    t    = normalize_text(text)
    toks = set(tokens(t))
    tags = set()

    if toks & {"buy","bought","groceries","grocery","milk","bread","eggs","vegetables","fruits","shop","shopping","rice","sugar","oil"}:
        tags.add("#shopping")
    if toks & {"exam","paper","viva","assignment","project","lab","practical","class","study","subject","semester","notes","submission"}:
        tags.add("#study")
    if toks & {"meeting","client","office","internship","task","deadline","work","team","call","presentation"}:
        tags.add("#work")
    if toks & {"birthday","bday","friend","family","mom","dad","brother","sister","home","personal"}:
        tags.add("#personal")
    if toks & {"today","tomorrow","monday","tuesday","wednesday","thursday","friday","saturday","sunday","jan","feb","mar","apr","may","jun","jul","aug","sep","sept","oct","nov","dec"}:
        tags.add("#event")
    if re.search(r"\b\d{1,2}(?::\d{2})?\s*(am|pm)\b", t, re.I):
        tags.add("#event")
    if re.search(r"\b\d{1,2}\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\b", t, re.I):
        tags.add("#event")

    return list(tags)

def extract_tags(text: str):
    manual = set(re.findall(r"#\w+", (text or "").lower()))
    auto   = set(suggest_auto_tags(text))
    all_tags = manual | auto
    return sorted(all_tags) if all_tags else ["#general"]

def token_overlap_score(q: str, doc: str) -> float:
    qset, dset = set(tokens(q)), set(tokens(doc))
    if not qset or not dset:
        return 0.0
    return len(qset & dset) / max(1, len(qset))

def cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    return float(np.dot(a, b) / denom) if denom else 0.0

def today_str() -> str:
    return datetime.now().strftime("%Y-%m-%d")

def short_answer_from_text(question: str, text: str) -> str:
    q = (question or "").lower().strip()
    t = (text or "").strip()

    time_match = re.search(r"\b(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)\b", t, re.I)
    date_match = re.search(r"\b(\d{1,2}\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*)\b", t, re.I)

    if "name" in q:
        m = re.search(r"(?:my\s+name\s+is|name\s+is)\s+(.+)$", t, re.I)
        if m: return m.group(1).strip()
        m = re.search(r"\bname\s+([a-z][a-z\s]{2,})$", t, re.I)
        if m: return m.group(1).strip()
        m = re.search(r"^(.+?)\s+is\s+my\s+name$", t, re.I)
        if m: return m.group(1).strip()

    if any(k in q for k in ["time","timing","open","close","kab","when"]):
        if time_match: return time_match.group(1).strip()
        if date_match: return date_match.group(1).strip()

    if any(k in q for k in ["birthday","bday","b'day"]):
        if date_match: return date_match.group(1).strip()

    if any(k in q for k in ["date","exam","paper","viva","submission"]):
        if date_match: return date_match.group(1).strip()

    return t

def build_memory_payload(doc):
    return {
        "id":     str(doc["_id"]),
        "text":   doc.get("text", ""),
        "tags":   doc.get("tags", ["#general"]),
        "date":   doc.get("date", ""),
        "pinned": doc.get("pinned", False),
    }

# ── Routes ─────────────────────────────────────────────────────────────────────
@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    if not request.session.get("user"):
        return RedirectResponse("/login")
    return templates.TemplateResponse("index.html", {"request": request, "user": request.session["user"]})

@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login")

@app.post("/login")
async def login(request: Request, data: dict = Body(...)):
    username = normalize(data.get("username"))
    password = (data.get("password") or "").strip()
    if not username or not password:
        return JSONResponse({"ok": False, "msg": "Username & password required"})
    user = users_col.find_one({"username": username})
    if not user or not verify_password(password, user["passhash"]):
        return JSONResponse({"ok": False, "msg": "Invalid credentials ❌"})
    request.session["user"] = username
    return JSONResponse({"ok": True, "redirect": "/"})

@app.post("/signup")
async def signup(request: Request, data: dict = Body(...)):
    username = normalize(data.get("username"))
    password = (data.get("password") or "").strip()
    if not username or not password:
        return JSONResponse({"ok": False, "msg": "Username & password required"})
    if users_col.find_one({"username": username}):
        return JSONResponse({"ok": False, "msg": "Account already exists ⚠️"})
    users_col.insert_one({"username": username, "passhash": hash_password(password)})
    request.session["user"] = username
    return JSONResponse({"ok": True, "redirect": "/"})

@app.post("/chat")
async def chat(data: dict = Body(...), user=Depends(get_current_user)):
    msg = normalize(data.get("msg"))
    if not msg:
        return {"response": "Type something 🙂"}

    is_question = msg.startswith("?") or msg.endswith("?")

    if is_question:
        q = msg[1:].strip() if msg.startswith("?") else msg[:-1].strip()
        q = normalize(q)
        if not q:
            return {"response": "Type a question 🙂"}

        q_norm = normalize_text(q)
        try:
            q_vec = get_embedding(q_norm)
        except Exception as e:
            return {"response": f"API connection error: {e}"}

        memories = list(mem_col.find({"user": user}, {"text": 1, "text_lower": 1, "embedding": 1, "date": 1}))
        if not memories:
            return {"response": "No memories yet"}

        scored = []
        for m in memories:
            text       = m.get("text", "")
            text_lower = m.get("text_lower") or normalize_text(text)
            emb        = m.get("embedding")
            date       = m.get("date", "")

            s_sem = 0.0
            if emb:
                try:
                    s_sem = cosine_sim(np.array(q_vec, dtype=float), np.array(emb, dtype=float))
                except Exception:
                    pass

            s_lex    = token_overlap_score(q_norm, text_lower)
            s_sub    = 1.0 if (q_norm and q_norm in text_lower) else 0.0
            s_recent = 1.0 if date == today_str() else 0.0
            final    = (0.52 * s_sem) + (0.28 * s_lex) + (0.10 * s_sub) + (0.10 * s_recent)
            scored.append((final, text))

        scored.sort(key=lambda x: x[0], reverse=True)

        if not scored or scored[0][0] < 0.28:
            return {"response": "Not found"}

        return {"response": short_answer_from_text(q, scored[0][1])}

    # ── Save memory ────────────────────────────────────────────────────────────
    msg = clean_memory_text(msg)
    if not msg:
        return {"response": "Type something 🙂"}

    tags       = extract_tags(msg)
    text_lower = normalize_text(msg)
    try:
        emb = get_embedding(text_lower)
    except Exception as e:
        return {"response": f"API connection error: {e}"}

    mem_col.insert_one({
        "user":       user,
        "text":       msg,
        "text_lower": text_lower,
        "embedding":  emb,
        "tags":       tags,
        "date":       today_str(),
        "pinned":     False,
    })
    return {"response": "Saved ✅"}

@app.get("/all")
def all_memories(user=Depends(get_current_user)):
    rows = list(mem_col.find({"user": user}).sort([("pinned", -1), ("_id", -1)]))
    return [build_memory_payload(r) for r in rows]

@app.get("/tag/{tag}")
def tag_memories(tag: str, user=Depends(get_current_user)):
    t = normalize(tag).lower()
    if not t:
        return []
    if not t.startswith("#"):
        t = "#" + t
    rows = list(mem_col.find({"user": user, "tags": {"$in": [t]}}).sort([("pinned", -1), ("_id", -1)]))
    return [build_memory_payload(r) for r in rows]

@app.get("/summary")
def summary(user=Depends(get_current_user)):
    rows = list(mem_col.find({"user": user}, {"text": 1}).sort("_id", -1).limit(25))
    if not rows:
        return {"summary": "Nothing yet"}
    lines = [f"• {r.get('text', '')}" for r in rows if r.get("text")]
    return {"summary": "Memory Summary:\n" + "\n".join(lines)}

@app.get("/calendar")
def calendar(user=Depends(get_current_user)):
    rows = list(mem_col.find({"user": user}, {"date": 1}))
    if not rows:
        return {"calendar": "No calendar items"}
    counts = {}
    for r in rows:
        d = r.get("date", "unknown-date")
        counts[d] = counts.get(d, 0) + 1
    lines = [f"• {d} → {cnt} memories" for d, cnt in sorted(counts.items())]
    return {"calendar": "Calendar (saved date):\n" + "\n".join(lines)}

@app.get("/search")
def search_memories(q: str = Query(..., min_length=1), user=Depends(get_current_user)):
    q = normalize(q)
    if not q:
        return []

    q_norm = normalize_text(q)
    direct = list(mem_col.find(
        {"user": user, "text_lower": {"$regex": re.escape(q_norm), "$options": "i"}}
    ).sort([("pinned", -1), ("_id", -1)]).limit(50))

    if direct:
        return [build_memory_payload(r) for r in direct]

    memories = list(mem_col.find({"user": user}, {"text": 1, "text_lower": 1, "embedding": 1, "tags": 1, "date": 1, "pinned": 1}))
    if not memories:
        return []

    try:
        q_vec = get_embedding(q_norm)
    except Exception:
        return []

    scored = []
    for m in memories:
        text       = m.get("text", "")
        text_lower = m.get("text_lower") or normalize_text(text)
        date       = m.get("date", "")

        s_lex = token_overlap_score(q_norm, text_lower)
        s_sub = 1.0 if (q_norm and q_norm in text_lower) else 0.0
        s_sem = 0.0
        emb   = m.get("embedding")
        if emb:
            try:
                s_sem = cosine_sim(np.array(q_vec, dtype=float), np.array(emb, dtype=float))
            except Exception:
                pass

        s_recent = 1.0 if date == today_str() else 0.0
        s_pin    = 1.0 if m.get("pinned", False) else 0.0
        final    = (0.45 * s_sem) + (0.22 * s_lex) + (0.08 * s_sub) + (0.10 * s_recent) + (0.15 * s_pin)
        scored.append((final, m))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [build_memory_payload(m) for score, m in scored[:15] if score >= 0.22]

@app.put("/pin/{mem_id}")
def toggle_pin(mem_id: str, user=Depends(get_current_user)):
    doc = mem_col.find_one({"user": user, "_id": ObjectId(mem_id)})
    if not doc:
        return {"ok": False, "msg": "Not found"}
    new_val = not doc.get("pinned", False)
    mem_col.update_one({"user": user, "_id": ObjectId(mem_id)}, {"$set": {"pinned": new_val}})
    return {"ok": True, "pinned": new_val}

@app.delete("/delete/{mem_id}")
def delete_memory(mem_id: str, user=Depends(get_current_user)):
    mem_col.delete_one({"user": user, "_id": ObjectId(mem_id)})
    return {"ok": True}

@app.put("/edit/{mem_id}")
def edit_memory(mem_id: str, data: dict = Body(...), user=Depends(get_current_user)):
    new_text = normalize(data.get("new_text"))
    if not new_text:
        return {"ok": False, "msg": "Text required"}

    new_text   = clean_memory_text(new_text)
    tags       = extract_tags(new_text)
    text_lower = normalize_text(new_text)
    try:
        emb = get_embedding(text_lower)
    except Exception as e:
        return {"ok": False, "msg": f"API connection error: {e}"}

    res = mem_col.update_one(
        {"user": user, "_id": ObjectId(mem_id)},
        {"$set": {"text": new_text, "text_lower": text_lower, "tags": tags, "embedding": emb}}
    )
    if res.matched_count == 0:
        return {"ok": False, "msg": "Not found"}
    return {"ok": True, "msg": "Updated"}