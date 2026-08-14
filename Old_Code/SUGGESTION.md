Yêu cầu tạo sản phẩm cá nhân:

- Thời hạn hoàn thành và gửi vào Giỏ cá nhân: Trước 17h00, ngày 09.08.2026.
- Sản phẩm hoàn thành xuất lên nền Web để sử dụng.

Mô tả về sản phẩm:

Hãy xây 1 AI thực nghiệm, tự động cào bình luận trên mạng xã hội tự chọn (Facebook, Tiktok,…) để phát hiện nói xấu về một tổ chức tự chọn (Trường DNC, Cty ABC nào đó,…), gửi link nói xấu đó về công cụ lựa chọn (Telegram, Slack, Email, SMS,…) theo thời gian thực.

Thầy Huy gợi ý các Module tối thiểu cần xây:

- Module Thu thập dữ liệu (Crawler/Scraper data): Quét định kỳ (ví dụ: mỗi giờ một lần) các bài đăng và bình luận từ một nhóm hoặc trang Facebook công khai được chỉ định.
- Module Trí tuệ (AI Engine): Nhận dữ liệu văn bản tiếng Việt, đưa qua mô hình PhoBERT (vì dữ liệu là tiếng Việt) đã được tinh chỉnh để phân tích cảm xúc (Tích cực /Tiêu cực / Bình thường) và trích xuất thực thể (ví dụ: có nhắc đến tên tổ chức hay không).
- Module Cảnh báo (Alerting System): Nếu AI phát hiện bình luận tiêu cực, gửi cảnh báo (kèm link) qua Telegram hoặc Slack hoặc Email.

Anh/Chị tham khảo các bước thực hiện sau đây:

**BƯỚC 1: XÂY DỰNG MODULE THU THẬP DỮ LIỆU TỪ FACEBOOK (CRAWLER)**

**Thầy Huy lưu ý:**

Trước khi viết code cho Module 1, Anh/Chị cần lưu ý:

- **Năm nay** Facebook bảo vệ dữ liệu cực kỳ nghiêm ngặt. Việc dùng các công cụ "cào" thô bạo (như Selenium, Puppeteer) lướt trang liên tục sẽ khiến tài khoản bị khóa (Checkpoint) hoặc bị cấm IP chỉ sau vài giờ.
- **Cách né:** Để tránh bị khóa, chúng ta sẽ sử dụng một thư viện Python nhẹ nhàng và ít bị chặn là facebook-scraper. Công cụ này không cần phải giả lập trình duyệt.
- **Giới hạn:** Anh/Chị **chỉ được phép cào dữ liệu từ các Page hoặc Nhóm Công khai**. Vì nếu cào dữ liệu trên các trang cá nhân là vi phạm điều khoản dịch vụ của Meta.
- **Chiến thuật có thể qua mặt tạm thời:** Trong mã nguồn, Anh/Chị nên đặt lệnh time.sleep(5) để tạo độ trễ. Nghĩa là cứ qua một post hệ thống cần tạm nghỉ 5 giây để Facebook tưởng rằng đây là một người thật đang cuộn trang từ từ.

**Cách chuẩn bị để chạy Code:**

1.  Mở Terminal (Command Prompt) và chạy lệnh cài đặt: pip install facebook-scraper. Nếu chạy trên google Colab thì không cần chạy cái này cũng được.
2.  Tạo một file Python và đặt tên nhất quán (ví dụ đặt tên là step1_crawler.py) và bắt đâu coding cho bước 1.

Anh/Chị tham khảo sườn code Python (Anh Chị code trên nền nào, Ngôn ngữ nào tùy thích, không nhất thiết phải Python): \[Anh Chị thêm bớt, tinh chỉnh Code cho phù hợp với Yêu cầu cụ thể từ đầu\].

from facebook_scraper import get_posts

import time

import re

def scrape_facebook_page(page_name, target_keyword, max_pages=2):

&nbsp;   """

&nbsp;   Quét các bài đăng gần đây từ một trang Facebook công khai.

&nbsp;   """

&nbsp;   print(f"\[\*\] Bắt đầu quét trang: {page_name}")

&nbsp;   scraped_data = \[\]

&nbsp;   try:

&nbsp;       # options={"comments": True} yêu cầu thư viện cố gắng lấy cả bình luận

&nbsp;       # Tuy nhiên, tính năng lấy bình luận của facebook-scraper hiện tại khá thiếu ổn định

&nbsp;       for post in get_posts(page_name, pages=max_pages, options={"comments": True}):

&nbsp;           # Kiểm tra xem bài đăng có chứa từ khóa mục tiêu không (không phân biệt hoa thường)

&nbsp;           text_content = str(post.get('text', '')).lower()

&nbsp;           if target_keyword.lower() in text_content:

&nbsp;               data = {

&nbsp;                   'post_id': post\['post_id'\],

&nbsp;                   'post_url': post\['post_url'\],

&nbsp;                   'text': post\['text'\],

&nbsp;                   'time': post\['time'\],

&nbsp;                   'comments': post.get('comments_full', \[\]) # Lấy danh sách bình luận chi tiết

&nbsp;               }

&nbsp;               scraped_data.append(data)

&nbsp;               print(f"    - Đã thu thập bài viết: {post\['post_id'\]}")

&nbsp;              

&nbsp;           # Nghỉ 5 giây giữa các bài để tránh bị block

&nbsp;           time.sleep(5)

&nbsp;          

&nbsp;   except Exception as e:

&nbsp;        print(f"\[!\] Lỗi khi cào dữ liệu: {e}")

&nbsp;   return scraped_data

if \__name__ == "\__main_\_":

&nbsp;   # Ví dụ: Quét trang fanpage của một tờ báo, tìm kiếm các bài có nhắc đến "Tổ chức X"

&nbsp;   # LƯU Ý: facebook-scraper chỉ hoạt động tốt với Page công khai.

&nbsp;   target_org = "Đại học DNC"

&nbsp;   data = scrape_facebook_page("baotuoitre", target_org, max_pages=1)

&nbsp;   print(f"\[\*\] Tổng số bài viết thu thập được có nhắc đến '{target_org}': {len(data)}")

### BƯỚC 2: XÂY DỰNG MODULE TRÍ TUỆ NHÂN TẠO BẰNG MÁY HỌC NÂNG CAO VÀ HỌC SÂU

**Thầy Huy lưu ý:**

Trước khi viết code cho Module 2, Anh/Chị cần lưu ý:

Trong bước này, hệ thống của Anh Chị sẽ sử dụng công nghệ Transfer Learning (Học chuyển giao). Cụ thể là tải một bộ não AI (PhoBERT) đã được huấn luyện sẵn bằng hàng tỷ từ tiếng Việt, và hệ thống này đã được Huấn luyện cách phân biệt câu chê (Tiêu cực) và câu khen (Tích cực). Áp dụng cách học chuyển giao để đỡ phải huấn luyện mô hình lại từ đầu.

**Cách chuẩn bị để chạy Code:**

1.  **Cài đặt thư viện AI:** Anh Chị cần mở Terminal và chạy lệnh sau để tải các thư viện của Hugging Face và PyTorch (lõi toán học chạy mạng nơ-ron) nếu chạy trên máy cá nhân: pip install transformers torch. Nếu chạy trên Google CoLab thì khỏi.
2.  **Khởi tạo Pipeline:** Trong code, Anh Chị dùng hàm pipeline("text-classification"). Đây là một hàm của Hugging Face, nó tự động làm 3 việc:
    - Tải cuốn "từ điển" (Tokenizer) để băm chữ thành số.
    - Tải bộ não Nơ-ron (Model Weights) nặng hàng trăm MB từ máy chủ về.
    - Chuyển số vào bộ não và ép ra kết quả dự đoán (Label & Score).
3.  **Giới hạn đầu vào:** Mô hình PhoBERT gốc chỉ đọc được tối đa 256 ‘từ’ (subwords) cùng một lúc. Do đó, trong code Anh Chị nên dùng lệnh cắt bớt (text\[:500\]) để đảm bảo không bị lỗi tràn bộ nhớ (Out-of-memory) nếu người dùng viết bình luận quá dài.
4.  Tạo một file Python và đặt tên nhất quán (ví dụ đặt tên là step2_ai_engine.py) và bắt đâu coding cho bước 2.

Anh/Chị tham khảo sườn code Python (Anh Chị code trên nền nào, Ngôn ngữ nào tùy thích, không nhất thiết phải Python): \[Anh Chị thêm bớt, tinh chỉnh Code cho phù hợp với Yêu cầu cụ thể từ đầu\].

from transformers import pipeline

class VietnameseSentimentAnalyzer:

&nbsp;   def \__init_\_(self):

&nbsp;       print("\[\*\] Đang tải mô hình AI PhoBERT...")

&nbsp;       # Sử dụng một mô hình PhoBERT đã được cộng đồng Fine-tune cho Sentiment Analysis

&nbsp;       # Trong thực tế, em nên tự Fine-tune một mô hình bằng dữ liệu riêng của tổ chức để độ chính xác cao nhất

&nbsp;       self.analyzer = pipeline(

&nbsp;           "text-classification",

&nbsp;           model="wonrax/phobert-base-vietnamese-sentiment", # Cập nhật mô hình chuyên dụng tiếng Việt

&nbsp;           tokenizer="wonrax/phobert-base-vietnamese-sentiment"

&nbsp;       )

&nbsp;       print("\[\*\] Tải mô hình hoàn tất!")

&nbsp;   def analyze(self, text):

&nbsp;       """

&nbsp;       Phân tích một đoạn văn bản và trả về nhãn (LABEL) và độ tự tin (SCORE)

&nbsp;       """

&nbsp;       try:

&nbsp;           # Giới hạn độ dài text (PhoBERT nhận tối đa 256 subwords)

&nbsp;           truncated_text = text\[:500\]

&nbsp;           result = self.analyzer(truncated_text)\[0\]

&nbsp;          

&nbsp;           # Map kết quả của mô hình cụ thể này (thường trả về nhãn NEG, POS, NEU)

&nbsp;           label = result\['label'\]

&nbsp;           score = result\['score'\]

&nbsp;          

&nbsp;           # Quy chuẩn nhãn (tùy thuộc vào model em chọn trên Hugging Face)

&nbsp;           # Mô hình "wonrax/phobert-base-vietnamese-sentiment" trả về 'NEG' cho tiêu cực

&nbsp;           is_negative = False

&nbsp;           if label == 'NEG' or label == 'LABEL_0':

&nbsp;               is_negative = True

&nbsp;           return {

&nbsp;               'text': text,

&nbsp;               'is_negative': is_negative,

&nbsp;               'confidence': score,

&nbsp;               'raw_label': label

&nbsp;           }

&nbsp;       except Exception as e:

&nbsp;           print(f"\[!\] Lỗi AI khi phân tích: {text\[:50\]}... Lỗi: {e}")

&nbsp;           return None

if \__name__ == "\__main_\_":

&nbsp;   ai = VietnameseSentimentAnalyzer()

&nbsp;  

&nbsp;   test_texts = \[

&nbsp;       "Dịch vụ của trường này dạo này chán quá, nhân viên thái độ lồi lõm.",

&nbsp;       "Trường học cơ sở vật chất rất tốt, đáng tiền."

&nbsp;   \]

&nbsp;  

&nbsp;   for t in test_texts:

&nbsp;       res = ai.analyze(t)

&nbsp;       print(f"Nhận xét: {res\['text'\]}")

&nbsp;       print(f"-> Phân tích: {'TIÊU CỰC' if res\['is_negative'\] else 'BÌNH THƯỜNG/TÍCH CỰC'} (Độ tự tin: {res\['confidence'\]\*100:.1f}%)\\n")

### BƯỚC 3: XÂY DỰNG MODULE CẢNH BÁO QUA TELEGRAM

**Thầy Huy lưu ý:**

Trước khi viết code cho Module 3, Anh/Chị cần lưu ý:

Trong môi trường doanh nghiệp, khi có khủng hoảng truyền thông (khách hàng phàn nàn gắt gắt, bóc phốt), tốc độ xử lý cần nhanh để ngăn chặn khủng hoảng. Không ai giao nhân viên ngồi canh màn hình 24/7 cả. Vì vậy, ta sẽ dùng API của Telegram để máy tính tự động gửi tin nhắn báo động vào nhóm chat của công ty ngay khi có bình luận xấu.

**Lý do ai cũng xài** Telegram là vì API của Telegram hoàn toàn miễn phí, không bị giới hạn quá khắt khe như Zalo hay Messenger, và tin nhắn được đẩy đi gần như không có độ trễ (Real-time).

**Anh Chị cần thực hiện trên điện thoại/máy tính trước khi coding Module 3 này:**

1.  **Tạo Bot:** Mở ứng dụng Telegram, tìm kiếm tài khoản có tên @BotFather (có tích xanh). Nhắn lệnh /newbot và làm theo hướng dẫn để tạo một con Bot. Nó sẽ cấp cho Anh Chị một đoạn mã gọi là **Bot Token** (ví dụ: 123456789:ABCdefGHI...). Anh Chị lưu mã này lại.
2.  **Tạo Nhóm (Group):** Tạo một nhóm chat mới trên Telegram (ví dụ: "Team Xử lý Khủng hoảng"). Sau đó, Anh Chị add con Bot vừa tạo vào nhóm này.
3.  **Lấy Chat ID:** Anh Chị cần biết "địa chỉ" của nhóm chat này để Bot gửi tin đúng chỗ. Cách dễ nhất là add thêm một con bot có tên @getidsbot vào nhóm, nó sẽ in ra mã **Chat ID** (thường là một dãy số bắt đầu bằng dấu trừ, ví dụ: -1001234567890).
4.  **Cài đặt thư viện:** Mở Terminal và chạy lệnh pip install requests (thư viện này giúp Python gửi tín hiệu HTTP lên máy chủ của Telegram).
5.  Tạo một file Python và đặt tên nhất quán (ví dụ đặt tên là step3_alert.py) và bắt đâu coding cho bước 3.

Anh/Chị tham khảo sườn code Python (Anh Chị code trên nền nào, Ngôn ngữ nào tùy thích, không nhất thiết phải Python): \[Anh Chị thêm bớt, tinh chỉnh Code cho phù hợp với Yêu cầu cụ thể từ đầu và thay thế Token và Chat ID cho phù hợp thực tế\].

import requests

def send_telegram_alert(bot_token, chat_id, text_content, post_url, confidence_score):

&nbsp;   """

&nbsp;   Gửi cảnh báo đến nhóm Telegram.

&nbsp;   """

&nbsp;   # ĐỊNH DẠNG TIN NHẮN (Sử dụng Markdown để in đậm, in nghiêng)

&nbsp;   message = f"🚨 \*\*CẢNH BÁO TIÊU CỰC PHÁT HIỆN\*\* 🚨\\n\\n"

&nbsp;   message += f"\*\*Nội dung:\*\*\\n_{text_content}\_\\n\\n"

&nbsp;   message += f"\*\*Độ tự tin của AI:\*\* {confidence_score\*100:.1f}%\\n"

&nbsp;   message += f"\*\*Link bài viết:\*\* {post_url}"

&nbsp;   # ĐƯỜNG DẪN API CỦA TELEGRAM

&nbsp;   url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

&nbsp;  

&nbsp;   # GÓI DỮ LIỆU ĐỂ GỬI ĐI

&nbsp;   payload = {

&nbsp;       "chat_id": chat_id,

&nbsp;       "text": message,

&nbsp;       "parse_mode": "Markdown"

&nbsp;   }

&nbsp;   try:

&nbsp;       # Gửi tín hiệu POST lên máy chủ Telegram

&nbsp;       response = requests.post(url, json=payload)

&nbsp;      

&nbsp;       # Kiểm tra xem máy chủ có nhận thành công không (Mã 200 là thành công)

&nbsp;       if response.status_code == 200:

&nbsp;           print("\[\*\] Đã gửi cảnh báo qua Telegram thành công!")

&nbsp;       else:

&nbsp;           print(f"\[!\] Lỗi gửi Telegram: {response.text}")

&nbsp;   except Exception as e:

&nbsp;       print(f"\[!\] Lỗi kết nối mạng khi gửi Telegram: {e}")

if \__name__ == "\__main_\_":

&nbsp;   # ---> LƯU Ý: THAY BẰNG TOKEN VÀ CHAT ID THỰC TẾ CỦA EM Ở ĐÂY <---

&nbsp;   TOKEN = "123456789:ABCdefGHIjklMNOpqrSTUvwxYZ"

&nbsp;   CHAT_ID = "-1001234567890"

&nbsp;  

&nbsp;   print("\[\*\] Đang test chức năng gửi cảnh báo...")

&nbsp;   # Thử gửi một tin nhắn giả lập

&nbsp;   send_telegram_alert(

&nbsp;       bot_token=TOKEN,

&nbsp;       chat_id=CHAT_ID,

&nbsp;       text_content="Dịch vụ quá tệ, nhân viên thái độ lồi lõm, tẩy chay!",

&nbsp;       post_url="https://facebook.com/123456789",

&nbsp;       confidence_score=0.95

&nbsp;   )

### BƯỚC 4: RÁP NỐI 3 MODULE TRÊN ĐÂY VÀ LẬP LỊCH CHẠY TỰ ĐỘNG

**Thầy Huy lưu ý:**

Trước khi viết code cho Module 4-Là Module Chính để kết nối 3 Module trên lại thành một con AI hoàn chỉnh-Kiểu như ta viết hàm Main hồi trước học Ngôn ngữ lập trình vậy, Anh/Chị cần lưu ý:

Trong bước này, Anh Chị sẽ tạo một file main_pipeline.py. File này đóng vai trò là Ma Ma Tổng Quản, gọi các hàm từ 3 file trước đó để tạo thành một chu trình khép kín: **Quét Facebook Đưa cho AI đọc Nếu có nói xấu thì Báo động**.

**Những điểm kỹ thuật cốt lõi Anh Chị cần lưu ý:**

1.  **Khởi tạo AI một lần duy nhất:** Bộ não PhoBERT nặng vài trăm MB. Ta phải khởi tạo nó ở ngoài vòng lặp để tránh việc mỗi lần quét lại tải lại AI làm treo máy.
2.  **Lọc từ khóa (Keyword Filtering):** Không phải bình luận tiêu cực nào cũng đáng báo động. Ta chỉ báo động nếu bình luận đó **có nhắc đến tên tổ chức của Anh Chị** (Ví dụ: "Đại học DNC"). Điều này giúp lọc bớt rác trên mạng.
3.  **Lập lịch (Scheduling):** Anh Chị không thể tự tay bấm nút chạy liên tục được. Đâm ra sẽ dùng thư viện schedule của Python để hẹn giờ (Ví dụ: cứ tròn 1 tiếng thì tự động chạy quét 1 lần).

**Cách chuẩn bị:**

1.  Cài đặt thư viện lập lịch: Mở Terminal chạy lệnh pip install schedule.
2.  Đảm bảo 3 file step1_crawler.py, step2_ai_engine.py, step3_alert.py đang nằm chung trong một thư mục với file main_pipeline.py sắp tạo.
3.  Điền đúng mã Token và Chat ID Telegram của Anh Chị vào cấu hình.
4.  Để chạy hệ thống, Anh Chị gõ lệnh python main_pipeline.py.

Anh/Chị tham khảo sườn code Python (Anh Chị code trên nền nào, Ngôn ngữ nào tùy thích, không nhất thiết phải Python): \[Anh Chị thêm bớt, tinh chỉnh Code cho phù hợp với Yêu cầu cụ thể từ đầu và thay thế Token và Chat ID cho phù hợp thực tế\].

import time

import schedule

\# Import các hàm từ 3 module đã viết ở các bước trước

from step1_crawler import scrape_facebook_page

from step2_ai_engine import VietnameseSentimentAnalyzer

from step3_alert import send_telegram_alert

\# --- CẤU HÌNH HỆ THỐNG ---

TARGET_ORGANIZATION = "Đại học DNC"

FACEBOOK_PAGES_TO_MONITOR = \["baotuoitre", "confessions_truong_DNC"\] # Danh sách các page cần theo dõi

TELEGRAM_BOT_TOKEN = "ĐIỀN_TOKEN_CỦA_ANH CHỊ_VÀO_ĐÂY"

TELEGRAM_CHAT_ID = "ĐIỀN_CHAT_ID_VÀO_ĐÂY"

\# Khởi tạo "Bộ não" AI một lần duy nhất khi bật chương trình

print("\[\*\] Khởi động Hệ thống Social Listening...")

ai_engine = VietnameseSentimentAnalyzer()

def job_social_listening():

&nbsp;   """

&nbsp;   Hàm này chứa toàn bộ logic nghiệp vụ, sẽ được gọi định kỳ.

&nbsp;   """

&nbsp;   print(f"\\n==================================================")

&nbsp;   print(f"\[\*\] BẮT ĐẦU CHU KỲ LẮNG NGHE MẠNG XÃ HỘI LÚC {time.ctime()}")

&nbsp;   print(f"==================================================")

&nbsp;   for page in FACEBOOK_PAGES_TO_MONITOR:

&nbsp;       # 1. Cào dữ liệu từ Page (Quét 1 trang gần nhất để test)

&nbsp;       crawled_data = scrape_facebook_page(page, TARGET_ORGANIZATION, max_pages=1)

&nbsp;      

&nbsp;       for item in crawled_data:

&nbsp;           # 2. Phân tích nội dung bài post (Caption)

&nbsp;           post_analysis = ai_engine.analyze(item\['text'\])

&nbsp;          

&nbsp;           # Nếu AI phán đoán là Tiêu cực, lập tức bắn Telegram

&nbsp;           if post_analysis and post_analysis\['is_negative'\]:

&nbsp;               send_telegram_alert(

&nbsp;                   bot_token=TELEGRAM_BOT_TOKEN,

&nbsp;                   chat_id=TELEGRAM_CHAT_ID,

&nbsp;                   text_content=post_analysis\['text'\],

&nbsp;                   post_url=item\['post_url'\],

&nbsp;                   confidence_score=post_analysis\['confidence'\]

&nbsp;               )

&nbsp;          

&nbsp;           # 3. Phân tích sâu vào các bình luận bên trong bài post (Nếu cào được)

&nbsp;           for comment in item.get('comments', \[\]):

&nbsp;               comment_text = comment.get('comment_text', '')

&nbsp;              

&nbsp;               # Chỉ phân tích bình luận nếu có nhắc đến tên tổ chức (Target Keyword)

&nbsp;               if TARGET_ORGANIZATION.lower() in comment_text.lower():

&nbsp;                   comment_analysis = ai_engine.analyze(comment_text)

&nbsp;                  

&nbsp;                   if comment_analysis and comment_analysis\['is_negative'\]:

&nbsp;                       # Gửi cảnh báo bình luận tiêu cực

&nbsp;                       send_telegram_alert(

&nbsp;                           bot_token=TELEGRAM_BOT_TOKEN,

&nbsp;                           chat_id=TELEGRAM_CHAT_ID,

&nbsp;                           text_content=comment_analysis\['text'\],

&nbsp;                           post_url=item\['post_url'\],

&nbsp;                           confidence_score=comment_analysis\['confidence'\]

&nbsp;                       )

&nbsp;   print("\[\*\] CHU KỲ HOÀN TẤT. ĐANG CHỜ ĐẾN CHU KỲ TIẾP THEO...\\n")

if \__name__ == "\__main_\_":

&nbsp;   print("\[\*\] Hệ thống sẵn sàng! Đang tiến hành chạy chu kỳ đầu tiên...")

&nbsp;  

&nbsp;   # Chạy ngay lập tức lần đầu tiên khi vừa bật file

&nbsp;   job_social_listening()

&nbsp;  

&nbsp;   # Hẹn giờ chạy lại mỗi 1 giờ (có thể đổi thành .minutes cho phút)

&nbsp;   schedule.every(1).hours.do(job_social_listening)

&nbsp;  

&nbsp;   # Vòng lặp vô tận giữ cho chương trình luôn chạy ngầm và theo dõi lịch

&nbsp;   while True:

&nbsp;       schedule.run_pending()

&nbsp;       time.sleep(1)