# 🛡️ AI Social Listening System — Organization Negative Content Detector

Hệ thống AI thực nghiệm **Social Listening tiếng Việt** phát hiện tự động nội dung tiêu cực (bốc phốt, khiếu nại, phản ánh) liên quan đến một **Tổ chức mục tiêu** (Ví dụ: *Đại học DNC*, *Công ty ABC*) trên Mạng xã hội, sau đó tự động gửi cảnh báo thời gian thực qua Telegram / Slack / Email và hiển thị trên Web Dashboard.

---

## 🏗️ Kiến Trúc Hệ Thống

```text
               +----------------------------------+
               | Social Media Sources             |
               | (Facebook, TikTok, RSS, Mock)    |
               +----------------------------------+
                                |
                                v
               +----------------------------------+
               | Module 1: Data Collection        |
               | (Crawler + Fallback Adapter)     |
               +----------------------------------+
                                |
                                v
               +----------------------------------+
               | Deduplication Engine (SQLite)    |
               +----------------------------------+
                                |
                                v
               +----------------------------------+
               | Module 2: AI Engine              |
               |  - Entity Recognition (Target Org|
               |    + Aliases Regex Matching)     |
               |  - PhoBERT Sentiment Analysis    |
               |    (wonrax/phobert-base-sentiment)|
               +----------------------------------+
                                |
                                v
               +----------------------------------+
               | Alert Decision Logic             |
               | (Org Mentioned AND Negative      |
               |  AND Confidence >= Threshold)    |
               +----------------------------------+
                                |
                                v
               +----------------------------------+
               | Module 3: Multi-Channel Alert    |
               | (Telegram / Slack / Email / Mock)|
               +----------------------------------+
                                |
                                v
               +----------------------------------+
               | Streamlit Web UI & Scheduler     |
               +----------------------------------+
```

---

## 🚀 Hướng Dẫn Nhanh (Quick Start)

### 1. Tạo môi trường ảo và cài đặt Dependencies
> Bắt buộc cài vào môi trường ảo `.venv` của dự án — PhoBERT (`transformers`, `torch`) chỉ được cài trong `.venv`, KHÔNG cài vào Python hệ thống.
```bash
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

### 2. Cấu hình Môi trường (.env)
Sao chép `.env.example` thành `.env` và tùy chỉnh:
```bash
TARGET_ORGANIZATION=Đại học DNC
TARGET_ALIASES=ĐH DNC, DNC, Trường DNC, Nam Cần Thơ
SOCIAL_PLATFORM=mock
SCHEDULE_INTERVAL_MINUTES=60
SENTIMENT_THRESHOLD=0.80
ALERT_CHANNEL=mock
TELEGRAM_BOT_TOKEN=your_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
```

### 3. Kiểm Thử Hệ Thống (Unit Tests)
Chạy bộ test tự động kiểm tra 4 modules (bằng Python của `.venv`):
```bash
.venv\Scripts\python main.py --mode test
```

### 4. Chạy Chu Kỳ Phân Tích (Single Scan Mode)
```bash
.venv\Scripts\python main.py --mode once
```

### 5. Khởi Chạy Web Interface (Streamlit Dashboard)

LUÔN chạy bằng môi trường ảo `.venv` của dự án. Nếu gõ `streamlit run web_app.py` mà lệnh `streamlit` trỏ tới Python hệ thống (ví dụ `C:\Tep_python\Scripts\streamlit.exe`), tiến trình sẽ chạy bằng Python hệ thống — không có `transformers`/`torch` → **PhoBERT không load được** → hệ thống tự rơi vào heuristic.

**Cách 1 (khuyên dùng) — launcher tự động dùng `.venv`:**
```bash
run_web_app.bat
```
hoặc trong PowerShell:
```powershell
.\run_web_app.ps1
```

**Cách 2 — kích hoạt `.venv` rồi chạy:**
```bash
.venv\Scripts\activate
streamlit run web_app.py
```

**Cách 3 — chạy trực tiếp bằng Python của `.venv`:**
```bash
.venv\Scripts\python -m streamlit run web_app.py
```

**Muốn `streamlit run web_app.py` (gõ ngay tại thư mục gốc dự án, trong cmd) vẫn dùng `.venv`:** project có sẵn shim `streamlit.cmd` ở thư mục gốc. Windows tìm file thực thi ở **thư mục hiện tại trước PATH**, nên khi bạn gõ lệnh tại thư mục gốc dự án, cmd sẽ chạy `streamlit.cmd` và route sang `.venv\Scripts\python.exe -m streamlit`. (Nếu gõ từ thư mục khác, hoặc thêm thư mục gốc dự án vào `PATH`, hiệu lực cũng được áp dụng.)

---

## 💻 Giao Diện Web Dashboard

Giao diện Web cung cấp 4 Tab chức năng:
1. **Tổng Quan Hệ Thống**: Xem tổng số mẫu quét, số bài viết nhắc tới tổ chức, số bài tiêu cực và số cảnh báo đã gửi.
2. **Kích Hoạt Quét Dữ Liệu**: Nút bấm chạy quét thủ công tức thời với tiến trình theo dõi.
3. **AI Test Bench**: Công cụ kiểm thử trực tiếp mô hình PhoBERT và thuật toán nhận diện tên tổ chức với bất kỳ văn bản tiếng Việt nào.
4. **Lịch Sử Cảnh Báo**: Bảng tra cứu lịch sử chi tiết lưu trữ trong cơ sở dữ liệu SQLite.

---

## 🛠️ Cấu Trúc Dự Án

```text
AUTO-BOT/
├── config.py                 # Centralized configuration & environment loader
├── .env.example              # Environment variables template
├── requirements.txt          # Python library dependencies
├── app/
│   ├── crawler/              # Module 1: Data Collection & Normalization
│   │   ├── base.py           # Abstract Crawler Interface
│   │   ├── mock_crawler.py   # Realistic Vietnamese dataset simulator
│   │   ├── facebook_crawler.py # Public Facebook page scraper with delay & fallback
│   │   └── factory.py        # Crawler Factory pattern
│   ├── ai/                   # Module 2: AI Engine (PhoBERT + NER)
│   │   ├── entity_detector.py # Named Entity Recognition & Alias Pattern Matching
│   │   └── sentiment_analyzer.py # PhoBERT Vietnamese Sentiment Classifier
│   ├── alert/                # Module 3: Alerting System
│   │   ├── base.py           # Abstract Alert Interface
│   │   ├── telegram.py       # Telegram Bot API implementation
│   │   ├── slack.py          # Slack Webhook implementation
│   │   ├── email_alert.py    # SMTP Email implementation
│   │   ├── mock_alert.py     # Simulated logger alert
│   │   └── service.py        # Multi-channel alert orchestrator
│   ├── db/                   # Storage & Deduplication Engine
│   │   └── repository.py     # SQLite persistence layer & deduplication store
│   ├── pipeline/             # Module 4: Core Pipeline & Scheduler
│   │   ├── pipeline.py       # End-to-end processing pipeline
│   │   └── scheduler.py      # Background thread scheduler
│   └── utils/
│       └── logger.py         # System logging setup
├── tests/                    # Unit Test Suite
│   ├── test_crawler.py
│   ├── test_ai.py
│   ├── test_alert.py
│   └── test_pipeline.py
├── main.py                   # CLI & Background Daemon Entrypoint
├── web_app.py                # Streamlit Web UI Dashboard
├── run_web_app.bat           # Web launcher (cmd) — tự dùng .venv
├── run_web_app.ps1           # Web launcher (PowerShell) — tự dùng .venv
├── streamlit.cmd             # Shim: "streamlit run web_app.py" tại thư mục gốc → .venv
└── README.md                 # Technical Documentation
```

---

## ⚠️ Giới Hạn & Phạm Vi Thực Nghiệm (Limitations)

1. **Giới hạn Crawler Facebook**: Do chính sách bảo vệ dữ liệu nghiêm ngặt của Meta, crawler tự động có thể bị cấm IP/checkpoint nếu tần suất quá cao. Hệ thống được tích hợp **Fallback Adapter** tự động chuyển sang chế độ Mock Data khi phát hiện rào cản mạng để không đứt gãy luồng xử lý.
2. **Giới hạn độ dài văn bản PhoBERT**: Mô hình PhoBERT nhận tối đa 256 subwords (~500 ký tự). AI Engine đã được tích hợp cơ chế cắt ngắn an toàn `text[:500]` nhằm ngăn lỗi tràn bộ nhớ (Out-Of-Memory).
3. **Cảnh Báo Giả (False Positive / False Negative)**: Cảm xúc tiếng Việt có thể chứa mỉa mai, nói giảm nói tránh. Ngưỡng tin cậy `SENTIMENT_THRESHOLD` có thể điều chỉnh linh hoạt từ `0.50` đến `0.99` trên giao diện Web để tối ưu hóa độ chính xác.
