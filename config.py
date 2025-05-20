# SegmentChatClient/config.py
import os

# Code config.py sẽ đọc từ biến môi trường
SUPABASE_URL = "https://iyzsjpezwpnkwbnqithb.supabase.co" # Có thể để giá trị mặc định nếu muốn
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Iml5enNqcGV6d3Bua3dibnFpdGhiIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDUzOTU2NzAsImV4cCI6MjA2MDk3MTY3MH0.bdsV1wLVXZYar5ew4jxb4iU10aQF4phiY7Dj9r5GNmU"

LOG_FILE = "client_log.txt"
LOG_MAX_RECORDS = 10000

# --- Kiểm tra xem đã cấu hình chưa ---
if SUPABASE_URL == "YOUR_SUPABASE_URL_DEFAULT" or SUPABASE_KEY == "YOUR_SUPABASE_ANON_KEY_DEFAULT":
    print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
    print("!!! CẢNH BÁO: SUPABASE_URL hoặc SUPABASE_KEY chưa được cấu hình.")
    print("!!! Vui lòng sửa file config.py hoặc tạo file .env.")
    print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")