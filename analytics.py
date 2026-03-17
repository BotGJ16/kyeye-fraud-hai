import json
import os
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, date

# Google Sheets connection
def get_sheet():
    try:
        creds_dict = json.loads(os.getenv("GOOGLE_CREDS", "{}"))
        if not creds_dict:
            return None
        creds = Credentials.from_service_account_info(
            creds_dict,
            scopes=[
                "https://spreadsheets.google.com/feeds",
                "https://www.googleapis.com/auth/drive"
            ]
        )
        client = gspread.authorize(creds)
        sheet = client.open("KyaYeFraudHai_Analytics").sheet1
        return sheet
    except:
        return None


def load_analytics() -> dict:
    default = {
        "total_visits": 0,
        "total_checks": 0,
        "total_frauds_found": 0,
        "total_safe_found": 0,
        "total_suspicious": 0,
        "today_checks": 0,
        "today_date": str(date.today()),
        "fraud_types": {},
        "check_types": {},
        "hourly_checks": {},
        "last_updated": ""
    }
    try:
        sheet = get_sheet()
        if sheet:
            data = sheet.acell("A1").value
            if data:
                loaded = json.loads(data)
                if loaded.get("today_date") != str(date.today()):
                    loaded["today_checks"] = 0
                    loaded["today_date"] = str(date.today())
                return loaded
    except:
        pass

    # Fallback — local file
    try:
        if os.path.exists("analytics.json"):
            with open("analytics.json", "r") as f:
                data = json.load(f)
                if data.get("today_date") != str(date.today()):
                    data["today_checks"] = 0
                    data["today_date"] = str(date.today())
                return data
    except:
        pass
    return default


def save_analytics(data: dict):
    data["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Google Sheets mein save karo
    try:
        sheet = get_sheet()
        if sheet:
            sheet.update("A1", json.dumps(data, ensure_ascii=False))
    except:
        pass

    # Local backup bhi rakhao
    try:
        with open("analytics.json", "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except:
        pass


def record_visit():
    data = load_analytics()
    data["total_visits"] += 1
    save_analytics(data)


def record_check(verdict: str, fraud_type: str = "Unknown", check_type: str = "text"):
    data = load_analytics()
    data["total_checks"] += 1
    data["today_checks"] += 1

    v = verdict.upper()
    if "FRAUD" in v:
        data["total_frauds_found"] += 1
    elif "REAL" in v or "SAFE" in v:
        data["total_safe_found"] += 1
    else:
        data["total_suspicious"] += 1

    if fraud_type and fraud_type not in ["Unknown", "ERROR", ""]:
        data["fraud_types"][fraud_type] = data["fraud_types"].get(fraud_type, 0) + 1

    data["check_types"][check_type] = data["check_types"].get(check_type, 0) + 1

    hour = datetime.now().strftime("%H:00")
    data["hourly_checks"][hour] = data["hourly_checks"].get(hour, 0) + 1

    save_analytics(data)


def get_stats() -> dict:
    return load_analytics()
