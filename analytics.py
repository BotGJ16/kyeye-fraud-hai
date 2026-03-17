import json
import os
from datetime import datetime, date

SHEET_NAME = "KyaYeFraudHai_Analytics"

# ─── Google Sheets Connection ─────────────────────────
def get_sheet():
    try:
        import streamlit as st
        import gspread
        from google.oauth2.service_account import Credentials

        creds_dict = dict(st.secrets["GOOGLE_CREDS"])

        # private_key newlines fix
        if "private_key" in creds_dict:
            creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")

        creds = Credentials.from_service_account_info(
            creds_dict,
            scopes=[
                "https://spreadsheets.google.com/feeds",
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive"
            ]
        )
        client = gspread.authorize(creds)
        sheet = client.open(SHEET_NAME).sheet1
        return sheet, "connected ✅"

    except KeyError:
        return None, "GOOGLE_CREDS secret missing!"
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"


# ─── Default Structure ────────────────────────────────
def _default() -> dict:
    return {
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
        "sheets_status": "not_connected",
        "last_updated": ""
    }


# ─── Load Analytics ───────────────────────────────────
def load_analytics() -> dict:
    data = _default()

    # Try Google Sheets first
    try:
        sheet, status = get_sheet()
        if sheet:
            cell_val = sheet.acell("A1").value
            if cell_val and cell_val.strip():
                loaded = json.loads(cell_val)
                # Reset today's count if new day
                if loaded.get("today_date") != str(date.today()):
                    loaded["today_checks"] = 0
                    loaded["today_date"] = str(date.today())
                loaded["sheets_status"] = status
                return loaded
            else:
                # Sheet empty — initialize karo
                data["sheets_status"] = "connected ✅ (initialized)"
                save_analytics(data)
                return data
        else:
            data["sheets_status"] = f"sheets error: {status}"
    except Exception as e:
        data["sheets_status"] = f"load error: {e}"

    # Fallback — local file
    try:
        if os.path.exists("analytics.json"):
            with open("analytics.json", "r", encoding="utf-8") as f:
                local_data = json.load(f)
                if local_data.get("today_date") != str(date.today()):
                    local_data["today_checks"] = 0
                    local_data["today_date"] = str(date.today())
                local_data["sheets_status"] = "local only ⚠️"
                return local_data
    except Exception:
        pass

    return data


# ─── Save Analytics ───────────────────────────────────
def save_analytics(data: dict) -> bool:
    data["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Google Sheets mein save karo
    saved_to_sheets = False
    try:
        sheet, status = get_sheet()
        if sheet:
            sheet.update(range_name="A1", values=[[json.dumps(data, ensure_ascii=False)]])
            data["sheets_status"] = "connected ✅"
            saved_to_sheets = True
    except Exception as e:
        data["sheets_status"] = f"save error: {e}"

    # Local backup bhi rakhao
    try:
        with open("analytics.json", "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception:
        pass

    return saved_to_sheets


# ─── Record Visit ─────────────────────────────────────
def record_visit():
    data = load_analytics()
    data["total_visits"] = data.get("total_visits", 0) + 1
    save_analytics(data)


# ─── Record Check ─────────────────────────────────────
def record_check(
    verdict: str,
    fraud_type: str = "Unknown",
    check_type: str = "text"
):
    data = load_analytics()

    data["total_checks"] = data.get("total_checks", 0) + 1
    data["today_checks"] = data.get("today_checks", 0) + 1

    v = verdict.upper()
    if "FRAUD" in v:
        data["total_frauds_found"] = data.get("total_frauds_found", 0) + 1
    elif "REAL" in v or "SAFE" in v:
        data["total_safe_found"] = data.get("total_safe_found", 0) + 1
    else:
        data["total_suspicious"] = data.get("total_suspicious", 0) + 1

    # Fraud type track karo
    if fraud_type and fraud_type not in ["Unknown", "ERROR", "Safe Content", ""]:
        ft = data.get("fraud_types", {})
        ft[fraud_type] = ft.get(fraud_type, 0) + 1
        data["fraud_types"] = ft

    # Check type track karo
    ct = data.get("check_types", {})
    ct[check_type] = ct.get(check_type, 0) + 1
    data["check_types"] = ct

    # Hourly stats
    hour = datetime.now().strftime("%H:00")
    hc = data.get("hourly_checks", {})
    hc[hour] = hc.get(hour, 0) + 1
    data["hourly_checks"] = hc

    save_analytics(data)


# ─── Get Stats ────────────────────────────────────────
def get_stats() -> dict:
    return load_analytics()


# ─── Debug Function ───────────────────────────────────
def test_connection() -> str:
    """Sheets connection test karo"""
    sheet, status = get_sheet()
    if sheet:
        try:
            val = sheet.acell("A1").value
            return f"✅ Connected! A1 = {val[:50] if val else 'empty'}..."
        except Exception as e:
            return f"⚠️ Connected but read error: {e}"
    return f"❌ Not connected: {status}"
