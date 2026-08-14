# 🛡️ AI Social Listening System (Gradio UI) — Organization Negative Content Detector

Hệ thống AI thực nghiệm **Social Listening tiếng Việt** phát hiện tự động nội dung tiêu cực (bốc phốt, khiếu nại, phản ánh) liên quan đến một **Tổ chức mục tiêu** trên Mạng xã hội, sau đó tự động gửi cảnh báo thời gian thực qua Telegram / Slack / Email và hiển thị trên Web Dashboard (Gradio).

> Dự án này được **clone từ `Old_Code/`** (bản Streamlit) — toàn bộ logic nghiệp vụ (`app/`, `config.py`, `main.py`, `tests/`) được giữ nguyên, chỉ thay giao diện Web từ **Streamlit → Gradio** (`gradio_app.py`). Extension Chrome (`chrome-extension/`, **v3.4**) được nâng cấp thêm tính năng **đồng bộ bài quét lên server** qua `POST /api/extension/ingest`.

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
|  - Entity Recognition (Target    |
|    Org + Aliases Regex Matching) |
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
| Gradio Web UI & Scheduler        |
+----------------------------------+
```

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
```bash
.venv\Scripts\python main.py --mode test
```

### 4. Chạy Chu Kỳ Phân Tích (Single Scan Mode)
```bash
.venv\Scripts\python main.py --mode once
```

### 5. Khởi Chạy Web Interface (Gradio Dashboard)

LUÔN chạy bằng môi trường ảo `.venv` của dự án.

**Cách 1 (khuyên dùng) — launcher tự động dùng `.venv`:**
```bash
run_gradio_app.bat
```
hoặc trong PowerShell:
```powershell
.\run_gradio_app.ps1
```

**Cách 2 — kích hoạt `.venv` rồi chạy:**
```bash
.venv\Scripts\activate
python gradio_app.py
```

**Cách 3 — chạy trực tiếp bằng Python của `.venv`:**
```bash
.venv\Scripts\python gradio_app.py
```

Giao diện mở tại `http://127.0.0.1:8501`.

## 💻 Giao Diện Web Dashboard (Gradio)

Giao diện Web cung cấp 6 Tab chức năng (tương đương với bản Streamlit cũ):

1. **📊 Tổng Quan Hệ Thống**: Tổng số mẫu quét, số bài viết nhắc tới tổ chức, số bài tiêu cực, số cảnh báo đã gửi và lần quét gần nhất.
2. **⚙️ Cấu Hình Hệ Thống**: Tổ chức mục tiêu + aliases, nguồn dữ liệu, Top-N discovery, ngưỡng tin cậy, chu kỳ quét, kênh cảnh báo, thông tin Telegram (tương đương Sidebar của bản cũ).
3. **🚀 Kích Hoạt Quét Dữ Liệu**: Chạy Discovery nguồn công khai đa nền tảng + chu kỳ quét thủ công với kết quả chi tiết.
4. **🧪 AI Test Bench**: Kiểm thử trực tiếp PhoBERT và thuật toán nhận diện tổ chức với bất kỳ văn bản tiếng Việt nào (kèm chức năng gửi cảnh báo thử).
5. **📜 Lịch Sử Cảnh Báo & Dữ Liệu**: Bảng tra cứu bài viết/bình luận đã quét và lịch sử cảnh báo.
6. **📄 Phân Tích Cảm Xúc Từ File TXT**: Upload file `.txt` định dạng chuẩn, phân tích theo từng mẫu, lọc kết quả và gửi cảnh báo Telegram.
7. **📡 Dữ Liệu Từ Extension**: Xem trước nội dung Chrome Extension quét và tự động đẩy lên (raw + bản ghi đã phân tích).

## 🔌 Đồng Bộ Từ Chrome Extension (Extension → Server)

Khi web app chạy với **public URL** (VD `https://xxxxxx.gradio.live`), Chrome Extension có thể
tự động gửi bài viết + bình luận đã quét lên server để hệ thống phân tích bằng đúng pipeline AI
(detect tổ chức + sentiment PhoBERT + cảnh báo) và lưu vào DB.

**Cách dùng:**
1. Mở extension → **Cài đặt** → nhập **Server URL** đầy đủ:
   `https://xxxxxx.gradio.live/api/extension/ingest` → **Lưu cấu hình**.
2. Bấm **Quét ngay** trên trang group → sau khi quét xong, extension **tự động đồng bộ**
   (hoặc bấm nút **Đồng bộ lên server** để gửi lại dữ liệu đã lưu).
3. Trên web app mở tab **📡 Dữ Liệu Từ Extension** để xem bản ghi vừa nhận + kết quả phân tích.

Endpoint public:
- `POST /api/extension/ingest` — nhận JSON `{ "source", "group_id", "items": [{url, postText, comments, ...}] }`
- `GET  /api/extension/health` — kiểm tra server sống
- Hỗ trợ CORS `Access-Control-Allow-Origin: *` để extension gửi được từ mọi nguồn.

> Extension được clone từ `Old_Code/` và **đã được nâng cấp** (v3.4): thêm trường Server URL
> trong trang Cài đặt, nút "Đồng bộ lên server" và tự động đồng bộ sau khi quét.

## 🛠️ Cấu Trúc Dự Án

```text
Gradio_App/
├── config.py                 # Centralized configuration & environment loader
├── .env.example              # Environment variables template
├── requirements.txt          # Python library dependencies
├── gradio_app.py             # Gradio Web UI Dashboard (thay thế web_app.py Streamlit)
├── run_gradio_app.bat        # Web launcher (cmd) — tự dùng .venv
├── run_gradio_app.ps1        # Web launcher (PowerShell) — tự dùng .venv
├── chrome-extension/         # Chrome Extension (v3.4, có đồng bộ lên server)
├── app/
│   ├── crawler/              # Module 1: Data Collection & Normalization
│   ├── ai/                   # Module 2: AI Engine (PhoBERT + NER)
│   ├── alert/                # Module 3: Alerting System
│   ├── db/                   # Storage & Deduplication Engine
│   ├── discovery/            # Multi-platform Public Source Discovery (5-tier fallback)
│   ├── parser/               # TXT Upload Parser
│   ├── pipeline/             # Module 4: Core Pipeline & Scheduler
│   └── utils/                # System logging setup
├── tests/                    # Unit Test Suite
├── main.py                   # CLI & Background Daemon Entrypoint
└── README.md                 # Technical Documentation
```

## ⚠️ Giới Hạn & Phạm Vi Thực Nghiệm (Limitations)

1. **Giới hạn Crawler Facebook**: Do chính sách bảo vệ dữ liệu nghiêm ngặt của Meta, crawler tự động có thể bị cấm IP/checkpoint nếu tần suất quá cao. Hệ thống được tích hợp **Fallback Adapter** tự động chuyển sang chế độ Mock Data khi phát hiện rào cản mạng.
2. **Giới hạn độ dài văn bản PhoBERT**: Mô hình PhoBERT nhận tối đa 256 subwords (~500 ký tự). AI Engine đã có cơ chế cắt ngắn an toàn `text[:500]`.
3. **Cảnh Báo Giả**: Cảm xúc tiếng Việt có thể chứa mỉa mai, nói giảm nói tránh. Ngưỡng tin cậy `SENTIMENT_THRESHOLD` có thể điều chỉnh từ `0.50` đến `0.99` trong tab Cấu Hình.