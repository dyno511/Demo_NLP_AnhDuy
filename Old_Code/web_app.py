import os
import time
import pandas as pd
import streamlit as st
from config import Config
from app.db.repository import Repository
from app.pipeline.pipeline import SocialListeningPipeline
from app.pipeline.scheduler import PipelineScheduler
from app.ai.entity_detector import OrganizationDetector
from app.ai.sentiment_analyzer import VietnameseSentimentAnalyzer
from app.discovery.service import DiscoveryService
from app.db.source_registry import SourceRegistry
from app.alert.service import AlertService, select_alert_candidates, build_alert_payload, evaluate_alert_eligibility
from app.parser.txt_parser import analyze_txt
from app.utils.logger import logger
from datetime import datetime

# Streamlit Page Setup
st.set_page_config(
    page_title="AI Social Listening System",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling
st.markdown("""
    <style>
    .main-title {
        font-size: 2.2rem;
        font-weight: 700;
        color: #1E293B;
        margin-bottom: 0.2rem;
    }
    .sub-title {
        font-size: 1.0rem;
        color: #64748B;
        margin-bottom: 1.5rem;
    }
    .metric-card {
        background-color: #F8FAFC;
        border: 1px solid #E2E8F0;
        border-radius: 10px;
        padding: 1.2rem;
        text-align: center;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    .metric-value {
        font-size: 1.8rem;
        font-weight: 700;
        color: #0F172A;
    }
    .metric-label {
        font-size: 0.85rem;
        color: #64748B;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    </style>
""", unsafe_allow_html=True)

# Initialize Session State
if "pipeline" not in st.session_state:
    with st.spinner("Khởi tạo Bộ não AI PhoBERT & Hệ thống Social Listening..."):
        st.session_state.pipeline = SocialListeningPipeline()
        st.session_state.scheduler = PipelineScheduler(pipeline=st.session_state.pipeline)
        st.session_state.repo = Repository()

repo: Repository = st.session_state.repo
source_registry = SourceRegistry(repo)
if "discovery_status" not in st.session_state:
    st.session_state.discovery_status = {
        "status": "NOT_RUN",
        "error": None,
        "query_count": 0,
        "candidate_count": 0,
        "platform_counts": {}
    }
if "discovered_sources" not in st.session_state:
    st.session_state.discovered_sources = []
if "txt_analysis" not in st.session_state:
    st.session_state.txt_analysis = None
if "txt_analysis_file" not in st.session_state:
    st.session_state.txt_analysis_file = None

# Header
st.markdown('<div class="main-title">🛡️ AI Social Listening - Phát Hiện Nội Dung Tiêu Cực</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">Hệ thống thực nghiệm tự động thu thập, phân tích cảm xúc tiếng Việt (PhoBERT) và cảnh báo khủng hoảng truyền thông.</div>', unsafe_allow_html=True)

# Sidebar - Configuration Panel
with st.sidebar:
    st.header("⚙️ Cấu Hình Hệ Thống")
    st.markdown("---")

    target_org = st.text_input("Tổ chức mục tiêu (Target Org)", value=Config.TARGET_ORGANIZATION)
    target_aliases_str = st.text_input("Tên viết tắt / Aliases (phân cách bằng dấu phẩy)", value=", ".join(Config.TARGET_ALIASES))

    platform = st.selectbox(
        "Nguồn dữ liệu Quét (Social Platform)",
        options=["mock", "facebook", "rss"],
        index=0 if Config.SOCIAL_PLATFORM == "mock" else (1 if Config.SOCIAL_PLATFORM == "facebook" else 2)
    )

    source_limit = st.selectbox("Số nguồn Top-N cần khám phá", [10, 20, 50, 100], index=0, key="source_limit_select")

    threshold = st.slider(
        "Ngưỡng tin cậy Cảnh báo (Sentiment Threshold)",
        min_value=0.50, max_value=0.99, value=Config.SENTIMENT_THRESHOLD, step=0.05
    )

    interval = st.number_input(
        "Chu kỳ quét tự động (phút)",
        min_value=1, max_value=1440, value=Config.SCHEDULE_INTERVAL_MINUTES
    )

    alert_channel = st.selectbox(
        "Kênh gửi cảnh báo (Alert Channel)",
        options=["mock", "telegram", "slack", "email", "all"],
        index=1 if Config.ALERT_CHANNEL == "mock" else ["mock", "telegram", "slack", "email", "all"].index(Config.ALERT_CHANNEL)
    )

    st.markdown("### 🔑 Kênh Telegram")
    telegram_token = st.text_input("Telegram Bot Token", value=Config.TELEGRAM_BOT_TOKEN, type="password")
    telegram_chat_id = st.text_input("Telegram Chat ID", value=Config.TELEGRAM_CHAT_ID)

    if st.button("💾 Lưu Cấu Hình", use_container_width=True):
        Config.TARGET_ORGANIZATION = target_org.strip()
        Config.TARGET_ALIASES = [a.strip() for a in target_aliases_str.split(",") if a.strip()]
        Config.SOCIAL_PLATFORM = platform
        Config.SENTIMENT_THRESHOLD = threshold
        Config.SCHEDULE_INTERVAL_MINUTES = interval
        Config.ALERT_CHANNEL = alert_channel
        Config.TELEGRAM_BOT_TOKEN = telegram_token
        Config.TELEGRAM_CHAT_ID = telegram_chat_id

        st.session_state.target_org = Config.TARGET_ORGANIZATION

        # Apply saved configuration to the running pipeline AI components.
        # (Config only; Source Discovery is triggered separately in the
        # "🚀 Kích Hoạt Quét Dữ Liệu" tab and is NOT run here.)
        st.session_state.pipeline.org_detector = OrganizationDetector(
            target_org=Config.TARGET_ORGANIZATION,
            aliases=Config.TARGET_ALIASES
        )
        st.session_state.pipeline.alert_service = AlertService(alert_channel)
        st.success("✅ Đã lưu cấu hình hệ thống. Để khám phá nguồn công khai, hãy vào tab '🚀 Kích Hoạt Quét Dữ Liệu' và bấm '🔎 Chạy Discovery'.")

tab_overview, tab_scan, tab_testbench, tab_history, tab_txt = st.tabs([
    "📊 Tổng Quan Hệ Thống", "🚀 Kích Hoạt Quét Dữ Liệu", "🧪 AI Test Bench", "📜 Lịch Sử Cảnh Báo & Dữ Liệu", "📄 Phân Tích Cảm Xúc Từ File TXT"
])

# TAB 1: OVERVIEW METRICS
with tab_overview:
    stats = repo.get_system_stats()

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">Tổng Số Mẫu Quét</div>
                <div class="metric-value">{stats['total_items']}</div>
            </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">Số Đề Cập Tổ Chức</div>
                <div class="metric-value">{stats['org_mentions']}</div>
            </div>
        """, unsafe_allow_html=True)
    with col3:
        st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">Phát Hiện Tiêu Cực</div>
                <div class="metric-value" style="color: #EF4444;">{stats['negative_items']}</div>
            </div>
        """, unsafe_allow_html=True)
    with col4:
        st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">Cảnh Báo Đã Gửi</div>
                <div class="metric-value" style="color: #F59E0B;">{stats['alerts_sent']}</div>
            </div>
        """, unsafe_allow_html=True)

    st.markdown("---")
    st.subheader("📌 Trạng Thái Hoạt Động & Lần Quét Gần Nhất")
    c1, c2 = st.columns(2)
    with c1:
        st.info(f"**Tổ chức đang theo dõi:** `{Config.TARGET_ORGANIZATION}`")
        st.info(f"**Danh sách Aliases:** `{', '.join(Config.TARGET_ALIASES)}`")
    with c2:
        st.info(f"**Lần quét cuối:** `{stats['last_scan']}`")
        st.info(f"**Kênh cảnh báo hoạt động:** `{Config.ALERT_CHANNEL.upper()}`")

# TAB 2: MANUAL SCAN OPERATOR
with tab_scan:
    st.subheader("🚀 Kích Hoạt Quét Dữ Liệu")
    st.write("Khu vực vận hành: khám phá nguồn công khai (Source Discovery) và kích hoạt chu kỳ quét thủ công. Discovery chỉ chạy khi bạn chủ động bấm nút bên dưới.")

    # ---- Source Discovery ----
    st.markdown("### 🔎 Chạy Discovery Nguồn Công Khai")
    st.write("Tìm kiếm các nguồn công khai (Facebook, TikTok, YouTube, Instagram, Reddit, Forum, News, Public Web) liên quan đến Target Org theo cấu hình đã lưu. Kết quả được cập nhật vào danh sách nguồn theo dõi (monitoring sources).")

    col_disc1, col_disc2 = st.columns([1, 3])
    with col_disc1:
        run_discovery = st.button("🔎 Chạy Discovery", type="secondary", use_container_width=True, key="btn_run_discovery")
    with col_disc2:
        if not Config.TARGET_ORGANIZATION.strip():
            st.caption("⚠️ Chưa có Target Org — cần lưu cấu hình trước.")

    if run_discovery:
        if not Config.TARGET_ORGANIZATION.strip():
            st.error("⚠️ Chưa có Target Org. Vui lòng nhập Tổ chức mục tiêu trong sidebar và bấm '💾 Lưu Cấu Hình' trước khi chạy Discovery. (MISSING_TARGET_ORG)")
        else:
            try:
                discovery_service = DiscoveryService(source_registry)
                with st.spinner("Đang khám phá nguồn công khai Đa nền tảng (Multi-Platform)..."):
                    st.session_state.discovered_sources = discovery_service.discover(
                        Config.TARGET_ORGANIZATION,
                        Config.TARGET_ALIASES,
                        st.session_state.get("source_limit_select", 10),
                    )
                    st.session_state.discovery_status = discovery_service.get_last_run()
            except Exception as exc:
                st.session_state.discovery_status = {
                    "status": "FAILED",
                    "error": f"{type(exc).__name__}: {exc}",
                    "query_count": 0,
                    "candidate_count": 0,
                    "platform_counts": {}
                }
                st.error(f"❌ Discovery thất bại: {st.session_state.discovery_status['error']} (DISCOVERY_FAILED)")

    run = st.session_state.discovery_status
    discovered = st.session_state.discovered_sources

    st.subheader(f"Target Org: {Config.TARGET_ORGANIZATION}")
    if run["status"] in {"SUCCESS", "PARTIAL_SUCCESS"}:
        status_color = "green"
    elif run["status"] in {"FAILED", "EMPTY_RESULT"}:
        status_color = "red"
    else:
        status_color = "orange"
    st.markdown(f"**Discovery Status:** :{status_color}[{run['status']}]")

    if run.get("error"):
        st.info(f"Thông báo Discovery: {run['error']}")

    counts = run.get("platform_counts", {})
    col_pf1, col_pf2, col_pf3, col_pf4 = st.columns(4)
    with col_pf1:
        st.caption(f"📘 Facebook: **{counts.get('facebook', 0)}**")
        st.caption(f"🎵 TikTok: **{counts.get('tiktok', 0)}**")
    with col_pf2:
        st.caption(f"▶️ YouTube: **{counts.get('youtube', 0)}**")
        st.caption(f"📸 Instagram: **{counts.get('instagram', 0)}**")
    with col_pf3:
        st.caption(f"🤖 Reddit: **{counts.get('reddit', 0)}**")
        st.caption(f"💬 Forum: **{counts.get('forum', 0)}**")
    with col_pf4:
        st.caption(f"📰 News: **{counts.get('news', 0)}**")
        st.caption(f"🌐 Public Web: **{counts.get('public_web', 0)}**")

    st.markdown("---")
    c_m1, c_m2, c_m3 = st.columns(3)
    with c_m1:
        st.metric("Total Extracted Results", run.get("search_results", 0))
    with c_m2:
        st.metric("Unique Candidate Sources", run.get("candidate_count", 0))
    with c_m3:
        st.metric("Selected Monitoring Sources (Top-N)", len(discovered))

    if discovered:
        rows = [{
            "Rank": x.get("rank", idx + 1),
            "Platform": x.get("platform", "public_web").upper(),
            "Source Name": x.get("source_name") or x.get("name", ""),
            "Source Type": x.get("source_type", ""),
            "URL": x.get("url", ""),
            "Relevance": x.get("relevance_score", 0.0),
            "Status": x.get("status", "")
        } for idx, x in enumerate(discovered)]
        st.dataframe(pd.DataFrame(rows), use_container_width=True)
    else:
        st.info("Chưa có nguồn nào được khám phá. Bấm '🔎 Chạy Discovery' để tìm kiếm nguồn công khai.")

    st.markdown("---")

    # ---- Manual Scan ----
    st.markdown("### 🚀 Kích Hoạt Chu Kỳ Quét Thủ Công")
    st.write("Bấm nút bên dưới để khởi chạy một chu kỳ thu thập, phân tích cảm xúc và gửi cảnh báo ngay lập tức.")

    col_btn1, col_btn2 = st.columns([1, 3])
    with col_btn1:
        run_scan = st.button("🔥 Kích Hoạt Quét Ngay", type="primary", use_container_width=True)

    if run_scan:
        with st.spinner("Đang thu thập dữ liệu và chạy phân tích AI PhoBERT..."):
            summary = st.session_state.pipeline.run_cycle()
            st.success(f"✅ Đã hoàn thành chu kỳ quét trong {summary['duration_seconds']}s!")
            st.json(summary)
            st.rerun()

# TAB 3: AI TEST BENCH PLAYGROUND
with tab_testbench:
    st.subheader("🧪 Thử Nghiệm Phân Tích Cảm Xúc & Nhận Diện Thực Thể Tiếng Việt")
    st.write("Nhập văn bản bất kỳ để kiểm thử khả năng phát hiện tổ chức và phân tích sentiment của mô hình PhoBERT / Heuristic AI.")

    test_input = st.text_area(
        "Nhập nội dung bài đăng / bình luận tiếng Việt:",
        value="Phòng đào tạo Đại học DNC làm việc quá chậm trễ, phục vụ tệ hại lừa đảo sinh viên!",
        height=100
    )

    if st.button("🔍 Phân Tích Văn Bản"):
        if test_input:
            det = st.session_state.pipeline.org_detector.detect(test_input)
            sent = st.session_state.pipeline.sentiment_analyzer.analyze(test_input)

            c1, c2 = st.columns(2)
            with c1:
                st.markdown("### 🏢 Nhận Diện Tổ Chức (Entity Detection)")
                if det["org_detected"]:
                    st.success(f"**Phát hiện tổ chức:** `{det['matched_org']}` (Độ tự tin: {det['confidence']*100:.0f}%)")
                else:
                    st.warning("Không tìm thấy đề cập đến tổ chức mục tiêu.")

            with c2:
                st.markdown("### 🎭 Phân Tích Cảm Xúc (Sentiment Analysis)")
                if sent:
                    label = sent["label"]
                    score = sent["confidence"]
                    if label == "NEGATIVE":
                        st.error(f"**Nhãn Cảm Xúc:** `{label}` (Độ tự tin: {score*100:.1f}%)")
                    elif label == "POSITIVE":
                        st.success(f"**Nhãn Cảm Xúc:** `{label}` (Độ tự tin: {score*100:.1f}%)")
                    else:
                        st.info(f"**Nhãn Cảm Xúc:** `{label}` (Độ tự tin: {score*100:.1f}%)")

            st.markdown("---")
            should_alert = det["org_detected"] and sent and sent["is_negative"] and (sent["confidence"] >= Config.SENTIMENT_THRESHOLD)
            if should_alert:
                st.error(f"🚨 **HỆ THỐNG RA QUYẾT ĐỊNH: ĐỦ ĐIỀU KIỆN KÍCH HOẠT CẢNH BÁO!** (Ngưỡng tin cậy {Config.SENTIMENT_THRESHOLD*100:.0f}%)")
                
                # Build alert payload and dispatch alert dynamically
                alert_payload = {
                    "target_organization": det.get("matched_org") or Config.TARGET_ORGANIZATION,
                    "sentiment": sent.get("label", "NEGATIVE"),
                    "confidence": sent.get("confidence", 0.0),
                    "text": test_input,
                    "source": "AI Test Bench Playground",
                    "post_url": "https://facebook.com/test_bench_playground",
                    "author": "Tester",
                    "detected_at": datetime.now().isoformat()
                }

                # Check if telegram token is missing
                is_telegram_chosen = Config.ALERT_CHANNEL.lower().strip() == "telegram"
                if is_telegram_chosen and (not Config.TELEGRAM_BOT_TOKEN or not Config.TELEGRAM_CHAT_ID):
                    st.warning("⚠️ Cảnh báo Telegram chưa được gửi: Bot Token hoặc Chat ID chưa cấu hình. (TELEGRAM_NOT_CONFIGURED)")
                else:
                    try:
                        success = st.session_state.pipeline.alert_service.dispatch_alert(alert_payload)
                        if success:
                            st.success("✅ Gửi cảnh báo thành công! (TELEGRAM_SEND_SUCCESS / SEND_SUCCESS)")
                        else:
                            st.error("❌ Gửi cảnh báo thất bại. Vui lòng kiểm tra lại cấu hình API / kết nối mạng. (TELEGRAM_SEND_FAILED)")
                    except Exception as e:
                        st.error(f"❌ Gửi cảnh báo gặp sự cố: {e} (TELEGRAM_SEND_FAILED)")
            else:
                st.info("ℹ️ **HỆ THỐNG RA QUYẾT ĐỊNH: KHÔNG GỬI CẢNH BÁO.** (Không thỏa mãn đủ điều kiện: ALERT_NOT_TRIGGERED)")


# TAB 4: HISTORY & AUDIT LOGS
with tab_history:
    st.subheader("📜 Dữ Liệu Thu Thập & Lịch Sử Cảnh Báo")
    sub_tab1, sub_tab2 = st.tabs(["Bài Viết / Bình Luận Đã Quét", "Lịch Sử Cảnh Báo Gửi Đi"])

    with sub_tab1:
        items = repo.get_recent_items(limit=100)
        if items:
            df_items = pd.DataFrame(items)
            st.dataframe(df_items[["item_id", "source", "author", "text", "org_detected", "detected_org_name", "sentiment_label", "confidence", "alert_sent", "processed_at"]], use_container_width=True)
        else:
            st.info("Chưa có dữ liệu bài viết nào trong SQLite database.")

    with sub_tab2:
        alerts = repo.get_recent_alerts(limit=50)
        if alerts:
            df_alerts = pd.DataFrame(alerts)
            st.dataframe(df_alerts[["id", "channel", "target_org", "sentiment_label", "confidence", "text", "post_url", "sent_at"]], use_container_width=True)
        else:
            st.info("Chưa có cảnh báo nào được gửi đi.")


# TAB 5: TXT FILE UPLOAD & SENTIMENT ANALYSIS
def _send_txt_telegram_alerts(analysis):
    """
    Send Telegram alerts for qualifying TXT analysis items.

    Reuses the SAME alert decision + dispatcher as the rest of the project:
        select_alert_candidates() -> AlertService("telegram").dispatch_alert()
    with the project's existing Config credentials and threshold.

    Status semantics:
        ALERT_NOT_TRIGGERED     - no item satisfies the alert policy
        ALERT_TRIGGERED         - at least one candidate satisfies the policy
        TELEGRAM_NOT_CONFIGURED - triggered, but Telegram credentials missing
        TELEGRAM_SEND_FAILED    - triggered, but Telegram API call(s) failed
        TELEGRAM_SEND_SUCCESS   - triggered and Telegram call(s) succeeded
    """
    if analysis is None or analysis.get("status") != "SUCCESS" or not analysis.get("items"):
        st.error("⚠️ Vui lòng upload và phân tích file trước khi gửi cảnh báo. (NOT_ANALYZED)")
        return

    candidates, diagnostics = evaluate_alert_eligibility(
        analysis["items"],
        st.session_state.pipeline.org_detector,
        Config.SENTIMENT_THRESHOLD,
    )

    negative_total = analysis.get("summary", {}).get("negative", 0)
    if not candidates:
        reason_counts = {}
        for diag in diagnostics:
            if diag.get("sentiment") != "NEGATIVE":
                continue
            reason = diag.get("reason")
            reason_counts[reason] = reason_counts.get(reason, 0) + 1
            logger.debug(
                f"[TXT Alert] Không đủ điều kiện: type={diag.get('type')}, "
                f"post_id={diag.get('post_id')}, username={diag.get('username')}, "
                f"confidence={diag.get('confidence')}, reason={reason}"
            )
        reason_labels = {
            "ORG_NOT_DETECTED": "không phát hiện tổ chức mục tiêu",
            "CONFIDENCE_BELOW_THRESHOLD": "confidence dưới ngưỡng",
            "DUPLICATE": "trùng lặp",
            "SENTIMENT_NOT_NEGATIVE": "không phải NEGATIVE",
        }
        breakdown = ", ".join(
            f"{reason_labels[r]} ({reason_counts[r]})"
            for r in ("ORG_NOT_DETECTED", "CONFIDENCE_BELOW_THRESHOLD", "DUPLICATE", "SENTIMENT_NOT_NEGATIVE")
            if reason_counts.get(r)
        )
        msg = (
            f"ℹ️ Không có nội dung đủ điều kiện cảnh báo "
            f"(NEGATIVE: {negative_total}, đủ điều kiện: 0). (ALERT_NOT_TRIGGERED)"
        )
        if breakdown:
            msg += f" Lý do: {breakdown}."
        st.info(msg)
        return

    st.info(
        f"🚨 Alert đã được kích hoạt: "
        f"NEGATIVE: {negative_total}, đủ điều kiện cảnh báo: {len(candidates)}. (ALERT_TRIGGERED)"
    )

    if not Config.TELEGRAM_BOT_TOKEN or not Config.TELEGRAM_CHAT_ID:
        st.warning(
            f"⚠️ Có {len(candidates)} cảnh báo đủ điều kiện nhưng Telegram chưa được cấu hình. "
            f"Vui lòng nhập Bot Token và Chat ID trong sidebar. (TELEGRAM_NOT_CONFIGURED)"
        )
        return

    telegram_service = AlertService("telegram")
    success_count = 0
    failure_count = 0
    for candidate in candidates:
        payload = build_alert_payload(candidate["item"], candidate["detection"], source="File TXT")
        try:
            ok = telegram_service.dispatch_alert(payload)
        except Exception:
            ok = False
        if ok:
            success_count += 1
        else:
            failure_count += 1

    if success_count > 0 and failure_count == 0:
        st.success(
            f"✅ Đã gửi {success_count}/{len(candidates)} cảnh báo về Telegram. "
            f"(TELEGRAM_SEND_SUCCESS)"
        )
    elif failure_count > 0 and success_count == 0:
        st.error(
            f"❌ Có {len(candidates)} cảnh báo đủ điều kiện nhưng không gửi được cảnh báo nào. "
            f"Vui lòng kiểm tra lại cấu hình API / kết nối mạng. (TELEGRAM_SEND_FAILED)"
        )
    else:
        st.warning(
            f"⚠️ Đã gửi {success_count}/{len(candidates)} cảnh báo, "
            f"thất bại {failure_count}. (PARTIAL_SEND)"
        )


with tab_txt:
    st.subheader("📄 Phân Tích Cảm Xúc Từ File TXT")
    st.write("Tải lên file `.txt` theo định dạng chuẩn: `=== BAI n ===` / `URL:` / `NOI DUNG:` / `--- BINH LUAN ---` / `N. Username: bình luận`. Hệ thống sẽ parse toàn bộ bài viết (POST) và bình luận (COMMENT), giữ nguyên URL / username / nội dung, sau đó phân tích sentiment riêng từng mẫu bằng AI Engine PhoBERT hiện có.")

    uploaded = st.file_uploader("Chọn file .txt để phân tích", type=["txt"], key="txt_uploader")

    # Invalidate stale analysis when a new file is picked
    current_file = uploaded.name if uploaded is not None else None
    if st.session_state.txt_analysis is not None and st.session_state.txt_analysis_file != current_file:
        st.session_state.txt_analysis = None
        st.session_state.txt_analysis_file = None

    col_btn1, col_btn2 = st.columns([1, 3])
    with col_btn1:
        analyze_btn = st.button("🔍 Phân Tích File", type="primary", use_container_width=True)
    with col_btn2:
        if uploaded is not None:
            st.caption(f"File: `{uploaded.name}` | Dung lượng: {len(uploaded.getvalue()):,} bytes")

    if analyze_btn:
        if uploaded is None:
            st.error("⚠️ Vui lòng chọn file `.txt` trước khi phân tích. (FILE_NOT_SELECTED)")
        else:
            progress_bar = st.progress(0.0, text="Đang đọc & parse file TXT...")

            def _update_progress(done, total):
                progress_bar.progress(done / total if total else 1.0, text=f"Đang phân tích cảm xúc {done}/{total} mẫu...")

            try:
                result = analyze_txt(
                    uploaded.getvalue(),
                    uploaded.name,
                    st.session_state.pipeline.sentiment_analyzer,
                    org_detector=st.session_state.pipeline.org_detector,
                    progress_cb=_update_progress,
                )
            except Exception as exc:
                result = {
                    "status": "ERROR",
                    "error_code": "ANALYSIS_ERROR",
                    "error_message": f"{type(exc).__name__}: {exc}",
                    "posts": [], "items": [], "summary": {}, "item_errors": [],
                }
            progress_bar.empty()
            st.session_state.txt_analysis = result
            st.session_state.txt_analysis_file = current_file

    analysis = st.session_state.txt_analysis
    if analysis is not None and analysis.get("status") == "ERROR":
        st.error(f"❌ Không thể phân tích file: {analysis['error_message']} ({analysis['error_code']})")

    if analysis is not None and analysis.get("status") == "SUCCESS":
        summary = analysis["summary"]

        if summary.get("item_errors", 0) > 0:
            st.warning(f"⚠️ Có {summary['item_errors']} mẫu bị lỗi phân tích (đã ghi nhận lỗi riêng). Các mẫu còn lại vẫn được xử lý bình thường.")

        heuristic_count = sum(1 for it in analysis["items"] if it.get("analyzer_type") == "heuristic")
        if heuristic_count:
            st.warning(f"⚠️ PhoBERT không khả dụng (không tải được model), {heuristic_count}/{summary['total_samples']} mẫu được phân tích bằng bộ từ điển heuristic — độ chính xác thấp hơn model AI.")

        st.markdown("### 📊 Tổng Quan Kết Quả")

        col_m1, col_m2, col_m3, col_m4 = st.columns(4)
        with col_m1:
            st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-label">Tổng Số Bài Viết</div>
                    <div class="metric-value">{summary['total_posts']}</div>
                </div>
            """, unsafe_allow_html=True)
        with col_m2:
            st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-label">Tổng Số Bình Luận</div>
                    <div class="metric-value">{summary['total_comments']}</div>
                </div>
            """, unsafe_allow_html=True)
        with col_m3:
            st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-label">Tổng Số Mẫu Phân Tích</div>
                    <div class="metric-value">{summary['total_samples']}</div>
                </div>
            """, unsafe_allow_html=True)
        with col_m4:
            st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-label">Confidence Trung Bình</div>
                    <div class="metric-value">{summary['mean_confidence']*100:.1f}%</div>
                </div>
            """, unsafe_allow_html=True)

        col_m5, col_m6, col_m7, col_m8 = st.columns(4)
        with col_m5:
            st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-label">Positive</div>
                    <div class="metric-value" style="color: #16A34A;">{summary['positive']}</div>
                </div>
            """, unsafe_allow_html=True)
        with col_m6:
            st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-label">Negative</div>
                    <div class="metric-value" style="color: #EF4444;">{summary['negative']}</div>
                </div>
            """, unsafe_allow_html=True)
        with col_m7:
            st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-label">Neutral</div>
                    <div class="metric-value" style="color: #64748B;">{summary['neutral']}</div>
                </div>
            """, unsafe_allow_html=True)
        with col_m8:
            st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-label">Mẫu Lỗi</div>
                    <div class="metric-value" style="color: #F59E0B;">{summary.get('item_errors', 0)}</div>
                </div>
            """, unsafe_allow_html=True)

        st.markdown("---")

        st.markdown("### 🔎 Lọc Kết Quả")
        c_filter1, c_filter2 = st.columns([2, 2])
        with c_filter1:
            filter_option = st.selectbox(
                "Bộ lọc nhanh:",
                options=[
                    "Tất cả",
                    "Negative",
                    "Positive",
                    "Neutral",
                    "Chỉ bài viết (POST)",
                    "Chỉ bình luận (COMMENT)",
                ],
                key="txt_filter",
            )
        with c_filter2:
            sort_negative_first = st.checkbox("Ưu tiên hiển thị Negative trước", value=True, key="txt_sort_negative")

        rows = [{
            "Type": item["type"],
            "Bài": item["post_id"],
            "Username": item["username"] if item["username"] else "—",
            "Nội dung": item["content"],
            "Sentiment": item["sentiment"] if item["sentiment"] else "LỖI",
            "Confidence": item["confidence"] if item["confidence"] is not None else 0.0,
            "Pos": item.get("sentiment_positive"),
            "Neg": item.get("sentiment_negative"),
            "Neu": item.get("sentiment_neutral"),
            "Engine": "AI" if item.get("analyzer_type") == "phobert" else ("Heuristic" if item.get("analyzer_type") else "—"),
            "URL": item["url"] if item["url"] else "—",
        } for item in analysis["items"]]
        df = pd.DataFrame(rows)

        if not df.empty:
            if filter_option == "Negative":
                df = df[df["Sentiment"] == "NEGATIVE"]
            elif filter_option == "Positive":
                df = df[df["Sentiment"] == "POSITIVE"]
            elif filter_option == "Neutral":
                df = df[df["Sentiment"] == "NEUTRAL"]
            elif filter_option == "Chỉ bài viết (POST)":
                df = df[df["Type"] == "POST"]
            elif filter_option == "Chỉ bình luận (COMMENT)":
                df = df[df["Type"] == "COMMENT"]

            if sort_negative_first:
                sentiment_rank = {"NEGATIVE": 0, "POSITIVE": 1, "NEUTRAL": 2, "LỖI": 3}
                df["__rank"] = df["Sentiment"].map(lambda s: sentiment_rank.get(s, 4))
                df = df.sort_values("__rank", kind="stable").drop(columns="__rank")

        st.markdown(f"**Chi tiết kết quả ({len(df)}/{len(rows)} mẫu):**")
        if not df.empty:
            st.dataframe(
                df,
                hide_index=True,
                column_config={
                    "Confidence": st.column_config.NumberColumn(format="percent"),
                    "Pos": st.column_config.ProgressColumn(
                        "Pos (%)", min_value=0, max_value=1, format="percent",
                        help="Xác suất tích cực (Positive)",
                    ),
                    "Neg": st.column_config.ProgressColumn(
                        "Neg (%)", min_value=0, max_value=1, format="percent",
                        help="Xác suất tiêu cực (Negative)",
                    ),
                    "Neu": st.column_config.ProgressColumn(
                        "Neu (%)", min_value=0, max_value=1, format="percent",
                        help="Xác suất trung lập (Neutral)",
                    ),
                    "URL": st.column_config.LinkColumn(display_text="Mở liên kết"),
                },
            )
        else:
            st.info("Không có mẫu nào khớp với bộ lọc hiện tại.")

        st.markdown("---")
        st.markdown("### 🚨 Gửi Cảnh Báo Telegram")
        st.caption(f"Chỉ gửi các mẫu đáp ứng điều kiện: Sentiment = NEGATIVE, Confidence ≥ {Config.SENTIMENT_THRESHOLD*100:.0f}%, và phát hiện tổ chức mục tiêu (dùng chung cơ chế Telegram & cấu hình hiện tại).")
        alert_btn = st.button("🚨 Gửi cảnh báo về Telegram", type="primary", key="txt_send_alert", use_container_width=True)
        if alert_btn:
            _send_txt_telegram_alerts(analysis)
