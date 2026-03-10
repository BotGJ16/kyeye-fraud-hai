import google.generativeai as genai
import os
import re
import io
import base64
import tempfile
import requests
import numpy as np
from dotenv import load_dotenv
from urllib.parse import urlparse
from PIL import Image

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# ═══════════════════════════════════════════════════════
# MODEL CONFIG — 8 Models, Smart Fallback
# ═══════════════════════════════════════════════════════
# Jab ek model ka rate limit khatam ho → next use karo
# Gemini first (best quality) → Gemma (zyada free quota)

MODELS = [
    "gemini-2.5-flash",      # Best — 20 RPD
    "gemini-2.0-flash",      # Good — 20 RPD
    "gemini-3.1-flash-lite", # Good — 500 RPD
    "gemini-3.0-flash-lite", # Medium
    "gemma-3-27b-it",        # Gemma Large — 14,400 RPD 🔥
    "gemma-3-12b-it",        # Gemma Medium — 14,400 RPD
    "gemma-3-4b-it",         # Gemma Small — 14,400 RPD
    "gemma-3-1b-it",         # Gemma Tiny — 14,400 RPD (last resort)
]

# Vision models (image/video ke liye — Gemma vision support nahi karta)
VISION_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-3.1-flash-lite",
    "gemini-3.0-flash-lite",
]

# ─── Smart Model Selector — No Test Call ─────────────────
def get_model(vision: bool = False):
    """
    Models ko ek ek try karo.
    Rate limit pe next model pe jaao.
    Test call nahi karte — directly return karo.
    """
    model_list = VISION_MODELS if vision else MODELS
    for name in model_list:
        try:
            m = genai.GenerativeModel(name)
            return m, name
        except Exception:
            continue
    return None, None


def generate_with_fallback(prompt, vision: bool = False,
                           image_parts: list = None,
                           max_tokens: int = 600) -> tuple:
    """
    Smart generation — rate limit pe automatically next model try karo.
    Returns: (response_text, model_name_used)
    """
    model_list = VISION_MODELS if vision else MODELS
    last_error = ""

    for name in model_list:
        try:
            m = genai.GenerativeModel(name)
            config = {
                "temperature": 0.1,
                "max_output_tokens": max_tokens
            }

            if image_parts and vision:
                content = [prompt] + image_parts
            else:
                content = prompt

            response = m.generate_content(content, generation_config=config)
            return response.text.strip(), name

        except Exception as e:
            err = str(e)
            last_error = err

            # Rate limit — next model try karo
            if any(x in err.lower() for x in
                   ["429", "quota", "rate", "limit", "resource"]):
                continue

            # Model not found — next try karo
            if any(x in err.lower() for x in
                   ["404", "not found", "not supported", "deprecated"]):
                continue

            # Doosri error — bhi next try karo
            continue

    return None, f"ERROR: Sare models fail ho gaye. Last: {last_error}"


# ═══════════════════════════════════════════════════════
# TRUSTED / SUSPICIOUS LISTS
# ═══════════════════════════════════════════════════════
TRUSTED_DOMAINS = {
    "sbi.co.in", "hdfcbank.com", "icicibank.com", "axisbank.com",
    "kotakbank.com", "pnbindia.in", "bankofbaroda.in",
    "paytm.com", "phonepe.com", "razorpay.com",
    "npci.org.in", "upi.npci.org.in",
    "gov.in", "nic.in", "uidai.gov.in", "incometax.gov.in",
    "irctc.co.in", "mca.gov.in", "epfindia.gov.in",
    "google.com", "youtube.com", "facebook.com", "instagram.com",
    "whatsapp.com", "twitter.com", "linkedin.com", "github.com",
    "microsoft.com", "apple.com", "amazon.in", "amazon.com",
    "flipkart.com", "myntra.com", "zomato.com", "swiggy.com",
    "airtel.in", "jio.com", "bsnl.co.in",
}

SUSPICIOUS_TLDS = {
    ".tk", ".ml", ".ga", ".cf", ".gq",
    ".xyz", ".top", ".click", ".download",
    ".work", ".date", ".stream", ".loan",
    ".win", ".bid", ".review", ".gdn"
}

BRAND_KEYWORDS = [
    "sbi", "hdfc", "icici", "axis", "kotak", "rbi", "pnb",
    "paytm", "phonepe", "gpay", "uidai", "aadhaar",
    "irctc", "income-tax", "incometax",
    "amazon", "flipkart", "jio", "airtel",
]

UNICODE_CONFUSABLES = {
    'а': 'a', 'е': 'e', 'о': 'o', 'р': 'p', 'с': 'c',
    'х': 'x', 'у': 'y', 'і': 'i', 'ѕ': 's', 'ԁ': 'd',
    'ɡ': 'g', 'α': 'a', 'ο': 'o', 'ν': 'v',
}

# ═══════════════════════════════════════════════════════
# PROMPTS
# ═══════════════════════════════════════════════════════
BASE_FORMAT = """
VERDICT: [FRAUD ya REAL ya SUSPICIOUS]
RISK_SCORE: [sirf number 0-100]
FRAUD_TYPE: [KYC Fraud / Job Scam / Lottery Fraud / OTP Fraud / Bank UPI Fraud / Phishing Link / Fake Government Notice / Punycode Attack / Fake Screenshot / Fake QR / Safe / Unknown]
EXPLANATION: [2-3 Hindi sentences, EK LINE mein]
KYA_KARO: [Step 1; Step 2; Step 3 — semicolon se alag, EK LINE]
WARNING_SIGNS: [sign1, sign2 — comma se alag, EK LINE]
"""

TEXT_PROMPT = f"""Tu ek expert Indian cybersecurity fraud detector hai.
Niche diya message analyze karo aur SIRF ye EXACT format mein HINDI mein jawab do.
Har field EK HI LINE mein ho:

{BASE_FORMAT}

Rules: Sirf Hindi | Har field ek line | Risk 0=safe 100=fraud

User ka message:
\"\"\"
{{text}}
\"\"\"
"""

URL_PROMPT = f"""Tu ek expert cybersecurity URL analyzer hai.
URL ko deeply analyze karo — punycode aur brand impersonation pe khaas dhyan do.
SIRF ye EXACT format mein HINDI mein jawab do:

{BASE_FORMAT}
URL_ISSUES: [issue1, issue2 — comma se alag, EK LINE]

URL: {{url}}
Domain: {{domain}}
Protocol: {{protocol}}
Path: {{path}}
Suspicious Keywords: {{keywords}}
IP Address URL?: {{is_ip}}
URL Shortener?: {{is_shortener}}
Domain Length: {{domain_length}} chars
Subdomains: {{subdomains}}
Page Status: {{page_status}}
Punycode/Homograph: {{punycode_info}}
Brand Check: {{brand_info}}
"""

IMAGE_PROMPT = f"""Tu ek expert Indian fraud image analyzer hai.
Is image ko dhyan se dekho:
- Fake bank SMS/notification screenshot hai?
- Fake logos, wrong spellings, suspicious numbers?
- Genuine document hai?
Note: {{note}}

SIRF ye EXACT format mein HINDI mein jawab do:
{BASE_FORMAT}
"""


# ═══════════════════════════════════════════════════════
# RESPONSE PARSER
# ═══════════════════════════════════════════════════════
DEFAULT_KYA_KARO = (
    "Is cheez pe bilkul trust mat karo;"
    "Kisi ko personal/bank/Aadhaar details mat do;"
    "1930 pe call karo ya cybercrime.gov.in pe report karo"
)

def parse_response(raw: str) -> dict:
    result = {
        "verdict": "SUSPICIOUS",
        "risk_score": 50,
        "fraud_type": "Unknown",
        "explanation": "AI ne analyze kiya. Savdhan rahein.",
        "kya_karo": DEFAULT_KYA_KARO,
        "warning_signs": "Suspicious content mila",
        "url_issues": "",
        "raw": raw
    }
    if not raw:
        return result

    for line in raw.split("\n"):
        line = line.strip()
        if not line or ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip().upper()
        value = value.strip()
        if not value:
            continue

        if key == "VERDICT":
            result["verdict"] = value
        elif key == "RISK_SCORE":
            nums = re.findall(r'\d+', value)
            if nums:
                result["risk_score"] = max(0, min(100, int(nums[0])))
        elif key == "FRAUD_TYPE":
            result["fraud_type"] = value
        elif key == "EXPLANATION":
            result["explanation"] = value
        elif key == "KYA_KARO":
            result["kya_karo"] = value or DEFAULT_KYA_KARO
        elif key == "WARNING_SIGNS":
            result["warning_signs"] = value
        elif key == "URL_ISSUES":
            result["url_issues"] = value

    return result


# ═══════════════════════════════════════════════════════
# PUNYCODE / HOMOGRAPH ATTACK DETECTOR
# ═══════════════════════════════════════════════════════
def detect_punycode_attack(domain: str) -> dict:
    result = {
        "is_punycode": False,
        "is_homograph": False,
        "decoded_domain": domain,
        "normalized_domain": domain,
        "impersonates": None,
        "risk_modifier": 0,
        "details": []
    }
    try:
        import idna

        # Punycode (xn--) check
        if "xn--" in domain.lower():
            result["is_punycode"] = True
            result["risk_modifier"] += 40
            result["details"].append("⚠️ Punycode domain (xn-- prefix) — suspicious!")
            try:
                parts = domain.split(".")
                decoded_parts = []
                for part in parts:
                    if part.lower().startswith("xn--"):
                        decoded_parts.append(idna.decode(part.encode()).decode())
                    else:
                        decoded_parts.append(part)
                result["decoded_domain"] = ".".join(decoded_parts)
                result["details"].append(f"Decoded: {result['decoded_domain']}")
            except:
                result["details"].append("Decode fail — extra suspicious!")
                result["risk_modifier"] += 20

        # Unicode confusable chars check
        normalized = ""
        has_confusable = False
        for char in domain:
            if char in UNICODE_CONFUSABLES:
                normalized += UNICODE_CONFUSABLES[char]
                has_confusable = True
            else:
                normalized += char
        result["normalized_domain"] = normalized

        if has_confusable:
            result["is_homograph"] = True
            result["risk_modifier"] += 50
            result["details"].append(
                f"⚠️ Unicode lookalike chars! Actual domain: {normalized}"
            )

        # Mixed script check
        has_latin = bool(re.search(r'[a-zA-Z]', domain))
        has_unicode = bool(re.search(r'[^\x00-\x7F]', domain))
        if has_latin and has_unicode:
            result["is_homograph"] = True
            result["risk_modifier"] += 45
            result["details"].append(
                "⚠️ Mixed script (Latin + Unicode) = classic homograph attack!"
            )

        # Brand impersonation check
        check_domain = normalized.lower()
        for trusted in TRUSTED_DOMAINS:
            trusted_base = trusted.split(".")[0]
            check_base = check_domain.split(".")[0]
            if (trusted_base != check_base and
                    len(trusted_base) > 3 and
                    _similar(trusted_base, check_base)):
                result["impersonates"] = trusted
                result["risk_modifier"] += 60
                result["details"].append(
                    f"🚨 Brand impersonation! '{check_domain}' "
                    f"lagta hai '{trusted}' jaisa!"
                )
                break

    except Exception as e:
        result["details"].append(f"Punycode check error: {e}")

    return result


def _similar(s1: str, s2: str) -> bool:
    if abs(len(s1) - len(s2)) > 2:
        return False
    subs = {'rn': 'm', 'vv': 'w', 'ii': 'u', 'cl': 'd'}
    s2n = s2
    for fake, real in subs.items():
        s2n = s2n.replace(fake, real)
    if s1 == s2n:
        return True
    return _edit_distance(s1, s2) <= 2


def _edit_distance(s1: str, s2: str) -> int:
    m, n = len(s1), len(s2)
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(m + 1):
        dp[i][0] = i
    for j in range(n + 1):
        dp[0][j] = j
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            cost = 0 if s1[i-1] == s2[j-1] else 1
            dp[i][j] = min(
                dp[i-1][j] + 1,
                dp[i][j-1] + 1,
                dp[i-1][j-1] + cost
            )
    return dp[m][n]


# ═══════════════════════════════════════════════════════
# SMART PRE-CHECK (No API)
# ═══════════════════════════════════════════════════════
def smart_pre_check(text: str) -> dict:
    text_lower = text.lower()

    for domain in TRUSTED_DOMAINS:
        if domain in text_lower:
            return {
                "pre_verdict": "LIKELY_SAFE",
                "pre_score_modifier": -25,
                "pre_reason": f"Trusted domain '{domain}' mila"
            }

    for tld in SUSPICIOUS_TLDS:
        if tld in text_lower:
            return {
                "pre_verdict": "LIKELY_FRAUD",
                "pre_score_modifier": +30,
                "pre_reason": f"Suspicious TLD '{tld}' — free domain, scammer favorite"
            }

    for brand in BRAND_KEYWORDS:
        if brand in text_lower:
            has_official = any([
                f"{brand}.co.in" in text_lower,
                f"{brand}.com" in text_lower,
                f"{brand}.gov.in" in text_lower,
                f"{brand}.org.in" in text_lower,
            ])
            if not has_official:
                return {
                    "pre_verdict": "LIKELY_FRAUD",
                    "pre_score_modifier": +25,
                    "pre_reason": f"'{brand.upper()}' ka naam hai par official domain nahi!"
                }

    return {
        "pre_verdict": "NEUTRAL",
        "pre_score_modifier": 0,
        "pre_reason": "No strong signals"
    }


# ═══════════════════════════════════════════════════════
# URL ANALYZER
# ═══════════════════════════════════════════════════════
def extract_url_info(url: str) -> dict:
    try:
        if "://" not in url:
            url = "http://" + url
        parsed = urlparse(url)
        domain = parsed.netloc.lower().replace("www.", "")

        sus_keywords = [
            "free", "win", "prize", "claim", "verify", "kyc",
            "update", "urgent", "reward", "gift", "lucky",
            "login", "signin", "account", "wallet", "earn",
            "payment", "confirm", "suspend", "alert",
            "aadhaar", "pan", "otp", "bank"
        ]
        found = [kw for kw in sus_keywords if kw in url.lower()]

        is_ip = bool(re.search(
            r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b', domain
        ))
        shorteners = [
            "bit.ly", "tinyurl", "t.co", "goo.gl", "ow.ly",
            "tiny.cc", "is.gd", "rb.gy", "cutt.ly",
            "shorturl.at", "clck.ru"
        ]
        is_shortener = any(s in domain for s in shorteners)
        subdomains = max(0, len(domain.split(".")) - 2)

        return {
            "domain": domain,
            "path": parsed.path or "/",
            "protocol": parsed.scheme or "http",
            "keywords": ", ".join(found) if found else "koi nahi",
            "is_ip": "⚠️ YES — IP address URL!" if is_ip else "No",
            "is_shortener": "⚠️ YES — link hidden!" if is_shortener else "No",
            "domain_length": len(domain),
            "subdomains": subdomains,
            "raw_url": url
        }
    except Exception as e:
        return {"error": str(e)}


def fetch_page_status(url: str) -> str:
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        r = requests.get(
            url, headers=headers,
            timeout=5, verify=False,
            allow_redirects=True
        )
        redirect = (
            f" | Redirect→{r.url}" if r.url != url else ""
        )
        return f"HTTP {r.status_code}{redirect} | {len(r.text):,} bytes"
    except requests.exceptions.SSLError:
        return "⚠️ SSL ERROR — fake/expired certificate"
    except requests.exceptions.ConnectionError:
        return "⚠️ CONNECTION FAILED — domain exist nahi karta"
    except requests.exceptions.Timeout:
        return "⚠️ TIMEOUT — server respond nahi kar raha"
    except Exception as e:
        return f"Check failed: {e}"


# ═══════════════════════════════════════════════════════
# MAIN CHECK FUNCTIONS
# ═══════════════════════════════════════════════════════

def check_fraud_smart(text: str) -> dict:
    """Text/SMS fraud check with smart pre-screening + fallback"""
    pre = smart_pre_check(text)

    # Clearly safe — API save karo
    if (pre["pre_verdict"] == "LIKELY_SAFE" and
            "http" not in text.lower() and
            len(text) < 200):
        return {
            "verdict": "REAL",
            "risk_score": 10,
            "fraud_type": "Safe Content",
            "explanation": f"Ye content safe lagta hai. {pre['pre_reason']}.",
            "kya_karo": "Normal use karo; Personal info share mat karo; Doubt ho to 1930 pe call karo",
            "warning_signs": "Koi nahi",
            "pre_check": pre,
            "model_used": "Smart Pre-Check ✓ (API saved)"
        }

    text_response, model_used = generate_with_fallback(
        TEXT_PROMPT.format(text=text)
    )

    if text_response is None or "ERROR:" in str(model_used):
        return {
            "error": f"⏳ Sare models busy hain. 1 min baad try karo. ({model_used})",
            "verdict": "ERROR"
        }

    result = parse_response(text_response)

    # Pre-check modifier apply karo
    modifier = pre["pre_score_modifier"]
    if modifier != 0:
        result["risk_score"] = max(0, min(100, result["risk_score"] + modifier))
        result["explanation"] += f" [{pre['pre_reason']}]"

    result["pre_check"] = pre
    result["model_used"] = model_used
    return result


def deep_url_check(url: str) -> dict:
    """3-Layer URL analysis: Technical + Punycode + AI with fallback"""
    url_info = extract_url_info(url)
    if "error" in url_info:
        return {"error": url_info["error"]}

    # Layer 1: Punycode check
    punycode_result = detect_punycode_attack(url_info["domain"])
    punycode_info = (
        " | ".join(punycode_result["details"])
        if punycode_result["details"]
        else "Koi punycode/homograph attack nahi mila ✓"
    )

    # Layer 2: Brand pre-check
    pre = smart_pre_check(url)
    brand_info = pre["pre_reason"]

    # Layer 3: Page status
    page_status = fetch_page_status(url)

    # Layer 4: AI analysis with fallback
    url_response, model_used = generate_with_fallback(
        URL_PROMPT.format(
            url=url,
            domain=url_info["domain"],
            protocol=url_info["protocol"],
            path=url_info["path"],
            keywords=url_info["keywords"],
            is_ip=url_info["is_ip"],
            is_shortener=url_info["is_shortener"],
            domain_length=url_info["domain_length"],
            subdomains=url_info["subdomains"],
            page_status=page_status,
            punycode_info=punycode_info,
            brand_info=brand_info
        )
    )

    if url_response is None or "ERROR:" in str(model_used):
        return {
            "error": f"⏳ Sare models busy. 1 min baad try karo. ({model_used})",
            "verdict": "ERROR"
        }

    result = parse_response(url_response)

    # Punycode modifier
    if punycode_result["risk_modifier"] > 0:
        result["risk_score"] = min(
            100,
            result["risk_score"] + punycode_result["risk_modifier"]
        )
        if punycode_result["impersonates"]:
            result["verdict"] = "FRAUD"
            result["fraud_type"] = "Punycode Attack"

    result["technical_info"] = url_info
    result["page_status"] = page_status
    result["punycode_info"] = punycode_result
    result["model_used"] = model_used
    return result


def check_image_fraud(image_bytes: bytes) -> dict:
    """Image fraud check: OCR + AI Vision with fallback"""
    try:
        img = Image.open(io.BytesIO(image_bytes))

        # OCR
        try:
            import pytesseract
            extracted_text = pytesseract.image_to_string(
                img, lang="eng+hin"
            ).strip()
        except:
            extracted_text = ""

        note = (
            f"OCR text:\n{extracted_text}"
            if extracted_text
            else "OCR se text nahi mila."
        )

        # Image → base64
        buf = io.BytesIO()
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        img.save(buf, format="JPEG")
        img_data = base64.b64encode(buf.getvalue()).decode()
        image_part = {"mime_type": "image/jpeg", "data": img_data}

        img_response, model_used = generate_with_fallback(
            IMAGE_PROMPT.format(note=note),
            vision=True,
            image_parts=[image_part]
        )

        if img_response is None or "ERROR:" in str(model_used):
            return {
                "error": f"⏳ Vision models busy. Baad mein try karo. ({model_used})",
                "verdict": "ERROR"
            }

        result = parse_response(img_response)
        result["extracted_text"] = extracted_text
        result["check_type"] = "image"
        result["model_used"] = model_used
        return result

    except Exception as e:
        return {"error": str(e)}


def check_qr_fraud(image_bytes: bytes) -> dict:
    """QR decode + fraud check with fallback"""
    try:
        from pyzbar.pyzbar import decode as qr_decode
        import cv2

        img_array = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
        qr_codes = qr_decode(img)

        if not qr_codes:
            # QR nahi mila — image check karo
            r = check_image_fraud(image_bytes)
            r["qr_note"] = "QR code detect nahi hua — image analysis kiya"
            return r

        results = []
        for qr in qr_codes:
            qr_data = qr.data.decode("utf-8", errors="ignore").strip()

            if qr_data.startswith(("http", "https", "www")):
                r = deep_url_check(qr_data)
            elif "upi://" in qr_data.lower():
                r = check_fraud_smart(
                    f"Ye UPI QR code data hai:\n{qr_data}\n"
                    f"Kya ye legitimate UPI payment hai ya fraud?"
                )
                r["fraud_type"] = r.get("fraud_type", "UPI QR Check")
            else:
                r = check_fraud_smart(
                    f"Ye QR code ka content hai:\n{qr_data}"
                )

            r["qr_data"] = qr_data
            r["check_type"] = "qr"
            results.append(r)

        return max(results, key=lambda x: x.get("risk_score", 0))

    except ImportError:
        return {
            "error": "pip install opencv-python-headless pyzbar",
            "verdict": "ERROR"
        }
    except Exception as e:
        return {"error": str(e)}


def check_video_fraud(video_bytes: bytes, filename: str = "video.mp4") -> dict:
    """Video frames extract + analyze with fallback"""
    try:
        import cv2

        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=os.path.splitext(filename)[1] or ".mp4"
        ) as tmp:
            tmp.write(video_bytes)
            tmp_path = tmp.name

        cap = cv2.VideoCapture(tmp_path)
        fps = cap.get(cv2.CAP_PROP_FPS) or 25
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = total / fps

        frame_interval = max(1, int(fps * 5))
        frame_results = []
        frame_count = 0
        MAX_FRAMES = 5

        while cap.isOpened() and len(frame_results) < MAX_FRAMES:
            ret, frame = cap.read()
            if not ret:
                break
            if frame_count % frame_interval == 0:
                _, buf = cv2.imencode(".jpg", frame)
                r = check_image_fraud(buf.tobytes())
                r["frame_time"] = f"{frame_count / fps:.1f}s"
                frame_results.append(r)
            frame_count += 1

        cap.release()
        os.unlink(tmp_path)

        if not frame_results:
            return {"error": "Video frames analyze nahi ho sake"}

        worst = max(frame_results, key=lambda x: x.get("risk_score", 0))
        worst["total_frames_analyzed"] = len(frame_results)
        worst["video_duration"] = f"{duration:.1f}s"
        worst["all_frame_results"] = frame_results
        worst["check_type"] = "video"
        return worst

    except ImportError:
        return {"error": "pip install opencv-python-headless"}
    except Exception as e:
        return {"error": str(e)}
