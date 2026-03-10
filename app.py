import streamlit as st
from fraud_checker import (
    check_fraud_smart,
    deep_url_check,
    check_image_fraud,
    check_qr_fraud,
    check_video_fraud,
    detect_punycode_attack
)
from analytics import record_visit, record_check, get_stats

# ─── Page Config ──────────────────────────────────────────
st.set_page_config(
    page_title="Kya Ye Fraud Hai? 🔍",
    page_icon="🔐",
    layout="centered"
)

# ─── CSS ──────────────────────────────────────────────────
st.markdown("""
<style>
    .fraud-box {
        background: linear-gradient(135deg,#ff4444,#cc0000);
        color:white;padding:18px;border-radius:12px;
        text-align:center;font-size:22px;font-weight:bold;margin:10px 0;
    }
    .safe-box {
        background: linear-gradient(135deg,#00c853,#007a33);
        color:white;padding:18px;border-radius:12px;
        text-align:center;font-size:22px;font-weight:bold;margin:10px 0;
    }
    .suspicious-box {
        background: linear-gradient(135deg,#ff9800,#e65100);
        color:white;padding:18px;border-radius:12px;
        text-align:center;font-size:22px;font-weight:bold;margin:10px 0;
    }
    .punycode-box {
        background: linear-gradient(135deg,#7b1fa2,#4a148c);
        color:white;padding:18px;border-radius:12px;
        text-align:center;font-size:20px;font-weight:bold;margin:10px 0;
    }
    .info-card {
        background:#f0f4ff;border-left:4px solid #1976D2;
        padding:12px;border-radius:8px;margin:8px 0;
    }
    .warning-card {
        background:#fff8e1;border-left:4px solid #ffc107;
        padding:12px;border-radius:8px;margin:8px 0;
    }
    .danger-card {
        background:#fce4ec;border-left:4px solid #e91e63;
        padding:12px;border-radius:8px;margin:8px 0;
    }
    .step-card {
        background:#e8f5e9;border-left:4px solid #4CAF50;
        padding:12px;border-radius:8px;margin:6px 0;font-size:15px;
    }
    .stats-banner {
        background:linear-gradient(135deg,#1a237e,#283593);
        color:white;padding:15px;border-radius:12px;
        text-align:center;margin:10px 0;
    }
    .model-badge {
        background:#e3f2fd;color:#1565C0;
        padding:3px 10px;border-radius:20px;
        font-size:12px;font-weight:bold;
    }
    .rate-limit-box {
        background:#fff3cd;border:2px solid #ffc107;
        padding:15px;border-radius:10px;
        margin:10px 0;text-align:center;
    }
</style>
""", unsafe_allow_html=True)

# ─── Session State ────────────────────────────────────────
if "check_count" not in st.session_state:
    st.session_state.check_count = 0
if "visit_recorded" not in st.session_state:
    record_visit()
    st.session_state.visit_recorded = True

FREE_LIMIT = 5

# ─── Header ───────────────────────────────────────────────
st.title("🔐 Kya Ye Fraud Hai?")
st.markdown("**Text • URL • Image • QR • Video — Sab check karo, Hindi mein!**")

# ─── Live Stats Banner ────────────────────────────────────
stats = get_stats()
st.markdown(f"""
<div class="stats-banner">
🌍 <b>{stats['total_visits']:,}</b> Visitors &nbsp;|&nbsp;
🔍 <b>{stats['total_checks']:,}</b> Checks &nbsp;|&nbsp;
❌ <b>{stats['total_frauds_found']:,}</b> Frauds Pakde &nbsp;|&nbsp;
✅ <b>{stats['total_safe_found']:,}</b> Safe &nbsp;|&nbsp;
📅 Aaj: <b>{stats['today_checks']}</b>
</div>
""", unsafe_allow_html=True)

m1, m2, m3 = st.columns(3)
m1.metric("🆓 Free Checks Bache",
          f"{max(0, FREE_LIMIT - st.session_state.check_count)}/{FREE_LIMIT}")
m2.metric("❌ Frauds Found", stats['total_frauds_found'])
m3.metric("🌍 Total Visitors", f"{stats['total_visits']:,}")
st.markdown("---")


# ═══════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════
def show_rate_limit():
    st.markdown("""
    <div class="rate-limit-box">
    ⏳ <b>Rate Limit!</b><br><br>
    1️⃣ 1-2 minute wait karo<br>
    2️⃣ Kal aao — midnight pe reset<br>
    3️⃣ <a href="https://aistudio.google.com" target="_blank">Naya API key banao (free)</a>
    </div>
    """, unsafe_allow_html=True)


def show_limit_reached():
    st.error("🚫 Aaj ki 5 free checks khatam!")
    st.info("💎 Premium lo — ₹99/month mein unlimited checks!")


def display_kya_karo(kya_karo: str):
    default = [
        "Is cheez pe bilkul trust mat karo",
        "Kisi ko bhi personal/bank details mat do",
        "1930 pe call ya cybercrime.gov.in pe report karo"
    ]
    steps = [s.strip() for s in kya_karo.split(";") if s.strip()] if kya_karo else default
    if not steps:
        steps = default
    for i, step in enumerate(steps, 1):
        st.markdown(
            f'<div class="step-card"><b>✅ Step {i}:</b> {step}</div>',
            unsafe_allow_html=True
        )


def display_punycode_info(punycode_info: dict):
    """Punycode attack details dikhao"""
    if not punycode_info or not punycode_info.get("details"):
        return

    if punycode_info.get("is_punycode") or punycode_info.get("is_homograph"):
        st.markdown("""
        <div class="punycode-box">
        🔴 PUNYCODE / HOMOGRAPH ATTACK DETECTED!
        </div>
        """, unsafe_allow_html=True)

        st.markdown("### 🔬 Punycode Attack Details:")
        for detail in punycode_info["details"]:
            st.error(detail)

        if punycode_info.get("decoded_domain"):
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"""
                <div class="danger-card">
                <b>😈 Jo URL dikhti hai:</b><br>
                <code>{punycode_info.get('decoded_domain','')}</code><br>
                (naqli!)
                </div>
                """, unsafe_allow_html=True)
            with col2:
                st.markdown(f"""
                <div class="info-card">
                <b>✅ Asli trusted domain:</b><br>
                <code>{punycode_info.get('impersonates', 'Unknown')}</code>
                </div>
                """, unsafe_allow_html=True)


def display_result(result: dict, check_type: str = "text"):
    if "error" in result:
        err = str(result["error"])
        if any(x in err.lower() for x in ["429", "rate", "quota", "limit", "⏳"]):
            show_rate_limit()
        else:
            st.error(f"❌ Error: {err}")
        return

    # Analytics
    record_check(
        verdict=result.get("verdict", "UNKNOWN"),
        fraud_type=result.get("fraud_type", "Unknown"),
        check_type=check_type
    )

    verdict = result.get("verdict", "SUSPICIOUS").upper()
    score = result.get("risk_score", 50)
    model_used = result.get("model_used", "Gemini AI")
    punycode_info = result.get("punycode_info", {})

    # Punycode attack special banner
    if result.get("fraud_type") == "Punycode Attack" or (
        punycode_info and punycode_info.get("risk_modifier", 0) >= 50
    ):
        display_punycode_info(punycode_info)
    elif "FRAUD" in verdict:
        st.markdown(
            '<div class="fraud-box">❌ FRAUD HAI! SAVDHAN RAHO! 🚨</div>',
            unsafe_allow_html=True
        )
    elif "REAL" in verdict or "SAFE" in verdict:
        st.markdown(
            '<div class="safe-box">✅ YE SAFE LAGTA HAI 👍</div>',
            unsafe_allow_html=True
        )
    else:
        st.markdown(
            '<div class="suspicious-box">⚠️ SUSPICIOUS! DHYAN SE! 🤔</div>',
            unsafe_allow_html=True
        )

    st.markdown(f'<span class="model-badge">🤖 {model_used}</span>',
                unsafe_allow_html=True)
    st.markdown("")

    # Risk Score
    st.markdown("### 📊 Risk Score")
    emoji = "🔴" if score > 70 else "🟠" if score > 40 else "🟢"
    st.markdown(f"**{emoji} Risk Level: {score}/100**")
    st.progress(score / 100)

    # Type + Warning
    ca, cb = st.columns(2)
    with ca:
        st.markdown(f"""
        <div class="info-card">
        <b>🏷️ Fraud Type:</b><br>{result.get('fraud_type','Unknown')}
        </div>""", unsafe_allow_html=True)
    with cb:
        signs = result.get("warning_signs", "")
        card_cls = "warning-card" if signs and signs.lower() not in ["koi nahi","none",""] else "info-card"
        st.markdown(f"""
        <div class="{card_cls}">
        <b>⚠️ Warning Signs:</b><br>{signs or 'Koi nahi'}
        </div>""", unsafe_allow_html=True)

    # URL-specific info
    if check_type in ("url", "qr"):
        tech = result.get("technical_info", {})
        if tech:
            st.markdown("### 🔬 Technical Details")
            t1, t2, t3 = st.columns(3)
            with t1:
                st.markdown(f"""
                <div class="info-card">
                <b>🌐 Domain:</b><br><small>{tech.get('domain','N/A')}</small><br><br>
                <b>🔒 Protocol:</b><br>{str(tech.get('protocol','?')).upper()}
                </div>""", unsafe_allow_html=True)
            with t2:
                ip_cls = "danger-card" if "YES" in str(tech.get("is_ip","")) else "info-card"
                st.markdown(f"""
                <div class="{ip_cls}">
                <b>🖥️ IP URL?</b><br><small>{tech.get('is_ip','N/A')}</small><br><br>
                <b>✂️ Shortened?</b><br><small>{tech.get('is_shortener','N/A')}</small>
                </div>""", unsafe_allow_html=True)
            with t3:
                kw = tech.get("keywords", "koi nahi")
                kw_cls = "warning-card" if kw not in ["koi nahi","none",""] else "info-card"
                st.markdown(f"""
                <div class="{kw_cls}">
                <b>🚨 Sus. Words:</b><br><small>{kw}</small><br><br>
                <b>📏 Domain Len:</b><br>{tech.get('domain_length','?')} chars
                </div>""", unsafe_allow_html=True)

        pg = result.get("page_status", "")
        if pg:
            pg_cls = "danger-card" if "⚠️" in pg else "info-card"
            st.markdown(f"""
            <div class="{pg_cls}">
            <b>🌍 Page Status:</b> {pg}
            </div>""", unsafe_allow_html=True)

        if punycode_info:
            display_punycode_info(punycode_info)

        if result.get("url_issues"):
            st.markdown("### 🚩 URL Problems:")
            for issue in result["url_issues"].split(","):
                if issue.strip():
                    st.error(f"• {issue.strip()}")

    # QR data
    if result.get("qr_data"):
        st.markdown("### 📱 QR Mein Kya Tha:")
        st.code(result["qr_data"])

    # Image OCR text
    if result.get("extracted_text"):
        with st.expander("📄 Image Se Extract Hua Text"):
            st.code(result["extracted_text"])

    # Video frames
    if result.get("all_frame_results"):
        st.info(f"🎞️ {result.get('total_frames_analyzed',0)} frames analyzed | Duration: {result.get('video_duration','?')}")
        with st.expander("🎥 Har Frame Ka Result"):
            for i, fr in enumerate(result["all_frame_results"], 1):
                sc = fr.get("risk_score", 0)
                em = "🔴" if sc > 70 else "🟠" if sc > 40 else "🟢"
                st.markdown(
                    f"{em} **Frame {i}** ({fr.get('frame_time','?')}) "
                    f"— Risk: {sc}/100 — {fr.get('fraud_type','?')}"
                )

    # AI Analysis
    st.markdown("### 💬 AI Ka Analysis")
    exp = result.get("explanation", "").strip()
    st.info(exp if exp else "AI ne analyze kiya. Savdhan rahein.")

    # Kya Karo
    st.markdown("### ✅ Aapko Kya Karna Chahiye")
    display_kya_karo(result.get("kya_karo", ""))

    # Share
    st.markdown("---")
    st.markdown("### 📤 Dosto Ko Savdhan Karo!")
    share = (
        f"🔐 *Kya Ye Fraud Hai?* ne bataya:\n\n"
        f"*{verdict}* — Risk: {score}/100\n"
        f"Type: {result.get('fraud_type','Unknown')}\n\n"
        f"Check karo: kyeyefraudhai.in\n"
        f"#FraudAlert #CyberSafety"
    )
    st.code(share, language=None)
    st.caption("👆 Copy karo aur WhatsApp pe share karo!")

    left = max(0, FREE_LIMIT - st.session_state.check_count)
    if left == 0:
        st.error("🚫 Free checks khatam!")
    elif left <= 2:
        st.warning(f"⚠️ Sirf {left} check{'s' if left>1 else ''} bacha hai!")
    else:
        st.caption(f"ℹ️ {left} free checks bache hain.")


# ═══════════════════════════════════════════════════════
# TABS
# ═══════════════════════════════════════════════════════
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "📝 Text/SMS",
    "🔗 URL Scan",
    "📷 Image",
    "📱 QR Code",
    "🎥 Video",
    "ℹ️ Help"
])

# ── TAB 1: TEXT ───────────────────────────────────────────
with tab1:
    st.markdown("### 📩 Suspicious Message / SMS Paste Karo")
    user_input = st.text_area(
        "msg", height=150, label_visibility="collapsed",
        placeholder="Jaise: 'Congratulations! Prize jeet liya...'"
    )
    e1, e2, e3 = st.columns(3)
    with e1:
        if st.button("🎰 Lottery Scam", use_container_width=True):
            user_input = "Congratulations! Lucky draw mein 1 lakh jeete. Claim: bit.ly/claim99"
    with e2:
        if st.button("🏦 KYC Fraud", use_container_width=True):
            user_input = "URGENT: SBI account block hoga. 24 ghante mein KYC update karo: sbi-kyc.tk/verify"
    with e3:
        if st.button("💼 Job Scam", use_container_width=True):
            user_input = "WFH job! Rs50K/month. Registration fee Rs500. WhatsApp: 98XXXXXXXX"

    if st.button("🔍 CHECK KARO!", type="primary", use_container_width=True, key="t1"):
        if not user_input.strip():
            st.warning("Pehle kuch paste karo!")
        elif st.session_state.check_count >= FREE_LIMIT:
            show_limit_reached()
        else:
            with st.spinner("🤖 Analyzing..."):
                res = check_fraud_smart(user_input)
                st.session_state.check_count += 1
            display_result(res, "text")

# ── TAB 2: URL ────────────────────────────────────────────
with tab2:
    st.markdown("### 🔗 Suspicious URL Paste Karo")
    st.info("🛡️ **Punycode Attack bhi detect karega** — jab fake domain asli jaisi dikhti hai!")
    url_input = st.text_input(
        "url", label_visibility="collapsed",
        placeholder="https://suspicious-site.com/claim"
    )

    # Punycode live demo
    with st.expander("🧪 Punycode Attack Demo — Dekho kaise kaam karta hai"):
        st.markdown("""
        **Ye domains asli lagte hain par FAKE hain:**
        ```
        xn--80ak6aa92e.com     → выдаёт себя за google.com
        xn--pple-43d.com       → apple.com jaisa dikhta hai
        раурал.com (Cyrillic)  → paytm.com jaisa!
        ```
        Copy karo aur niche scan karo 👇
        """)

    u1, u2 = st.columns(2)
    with u1:
        if st.button("🧪 Fake KYC URL", use_container_width=True):
            url_input = "http://sbi-kyc.tk/verify?ref=urgent"
    with u2:
        if st.button("🧪 Shortened URL", use_container_width=True):
            url_input = "https://bit.ly/free-iphone-claim"

    if st.button("🔬 DEEP SCAN!", type="primary", use_container_width=True, key="t2"):
        if not url_input.strip():
            st.warning("Pehle URL paste karo!")
        elif st.session_state.check_count >= FREE_LIMIT:
            show_limit_reached()
        else:
            with st.spinner("🔎 Deep scanning..."):
                res = deep_url_check(url_input)
                st.session_state.check_count += 1
            display_result(res, "url")

# ── TAB 3: IMAGE ──────────────────────────────────────────
with tab3:
    st.markdown("### 📷 Suspicious Image Upload Karo")
    st.info("""
    **Detect karta hai:**
    - 📸 Fake bank SMS screenshots
    - 🎁 Fake prize offer images
    - 📄 Fake government notices
    - 💳 Fake payment confirmations
    """)
    img_file = st.file_uploader("Image (JPG/PNG)", type=["jpg","jpeg","png","webp"], key="img")
    if img_file:
        st.image(img_file, use_container_width=True)
        if st.button("🔍 IMAGE CHECK!", type="primary", use_container_width=True, key="t3"):
            if st.session_state.check_count >= FREE_LIMIT:
                show_limit_reached()
            else:
                with st.spinner("🤖 Image analyze ho rahi hai..."):
                    res = check_image_fraud(img_file.read())
                    st.session_state.check_count += 1
                display_result(res, "image")

# ── TAB 4: QR ─────────────────────────────────────────────
with tab4:
    st.markdown("### 📱 QR Code Check Karo")
    st.warning("⚠️ **Kabhi bhi unknown QR scan mat karo pehle check kiye bina!**")
    st.info("""
    **QR Fraud Types:**
    - 💸 Fake UPI QR — paisa gaya, wapas nahi
    - 🔗 QR ke andar chhupa phishing link
    - 📦 Fake delivery/cashback QR
    """)
    qr_file = st.file_uploader("QR Code Image", type=["jpg","jpeg","png"], key="qr")
    if qr_file:
        st.image(qr_file, width=250)
        if st.button("📱 QR SCAN & CHECK!", type="primary", use_container_width=True, key="t4"):
            if st.session_state.check_count >= FREE_LIMIT:
                show_limit_reached()
            else:
                with st.spinner("📱 QR decode + analyze..."):
                    res = check_qr_fraud(qr_file.read())
                    st.session_state.check_count += 1
                display_result(res, "qr")

# ── TAB 5: VIDEO ──────────────────────────────────────────
with tab5:
    st.markdown("### 🎥 Suspicious Video Check Karo")
    st.info("""
    **Video Fraud Types:**
    - 🎭 Deepfake scam videos
    - 💰 Fake investment videos
    - 🎁 Fake giveaway videos
    - 📱 Scam tutorial recordings
    """)
    vid_file = st.file_uploader("Video (MP4/AVI — max 50MB)", type=["mp4","avi","mov"], key="vid")
    if vid_file:
        size_mb = len(vid_file.getvalue()) / (1024*1024)
        if size_mb > 50:
            st.error("❌ 50MB se bada file nahi!")
        else:
            st.video(vid_file)
            st.info(f"📊 Size: {size_mb:.1f} MB")
            if st.button("🎥 VIDEO ANALYZE!", type="primary", use_container_width=True, key="t5"):
                if st.session_state.check_count >= FREE_LIMIT:
                    show_limit_reached()
                else:
                    with st.spinner("🎥 Frames analyze ho rahe hain..."):
                        res = check_video_fraud(vid_file.read(), vid_file.name)
                        st.session_state.check_count += 1
                    display_result(res, "video")

# ── TAB 6: HELP ───────────────────────────────────────────
with tab6:
    st.markdown("### ℹ️ Kaise Use Karein?")
    with st.expander("📝 Text/SMS Check", expanded=True):
        st.markdown("Suspicious message → Paste karo → CHECK KARO!")
    with st.expander("🔗 URL Scan"):
        st.markdown("Suspicious link → Paste karo → DEEP SCAN — Punycode bhi detect hoga!")
    with st.expander("📷 Image Check"):
        st.markdown("Fake screenshot ya offer image → Upload → Check karo")
    with st.expander("📱 QR Code"):
        st.markdown("Unknown QR image → Upload → Scan se pehle check karo")
    with st.expander("🎥 Video"):
        st.markdown("Suspicious video → Upload → Frames analyze honge")
    with st.expander("📞 Report Karo"):
        st.markdown("""
        | Service | Detail |
        |---|---|
        | 📞 Helpline | **1930** |
        | 🌐 Website | **cybercrime.gov.in** |
        """)

    st.markdown("### 📊 All-Time Stats")
    s = get_stats()
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("🌍 Visits", f"{s['total_visits']:,}")
    c2.metric("🔍 Checks", f"{s['total_checks']:,}")
    c3.metric("❌ Frauds", f"{s['total_frauds_found']:,}")
    c4.metric("✅ Safe", f"{s['total_safe_found']:,}")

# ─── Footer ───────────────────────────────────────────────
st.markdown("---")
st.markdown("""
<div style='text-align:center;color:gray;font-size:12px;padding:10px;'>
🔐 <b>Kya Ye Fraud Hai?</b> — India ka Smart Hindi Fraud Checker 🇮🇳<br>
🆘 Helpline: <b>1930</b> | <b>cybercrime.gov.in</b><br>
Made with ❤️ for India
</div>
""", unsafe_allow_html=True)
