# SegmentChatClient/src/api/client.py
import os
# === THAY ĐỔI IMPORT ===
# from supabase import create_client, Client # Không dùng create_client nữa
from supabase.client import AsyncClient # Import trực tiếp AsyncClient
# =======================
from typing import Optional
import config
from src.utils.logger import log_event

# Đổi type hint thành AsyncClient
_supabase_client: Optional[AsyncClient] = None

# Hàm này vẫn là sync, nhưng khởi tạo AsyncClient
def init_supabase_client():
    """
    Khởi tạo Supabase AsyncClient (hàm này là sync).
    Nó tạo ra một client bất đồng bộ.
    Hàm này nên được gọi một lần khi ứng dụng khởi động.
    """
    global _supabase_client
    if _supabase_client is None:
        url: str = config.SUPABASE_URL
        key: str = config.SUPABASE_KEY
        if not url or url == "YOUR_SUPABASE_URL_DEFAULT" or not key or key == "YOUR_SUPABASE_ANON_KEY_DEFAULT":
            log_event("[ERROR][API_CLIENT] Supabase URL hoặc Key chưa được cấu hình trong config.py.")
            print("[ERROR] Vui lòng cấu hình Supabase URL và Key trong config.py")
            _supabase_client = None
            return

        try:
            log_event("[API_CLIENT] Initializing Supabase AsyncClient...")
            # === THAY ĐỔI KHỞI TẠO ===
            # _supabase_client = create_client(url, key) # Bỏ dòng này
            _supabase_client = AsyncClient(url, key) # Khởi tạo AsyncClient
            # =========================
            log_event("[API_CLIENT] Supabase AsyncClient instance created successfully.")
        except Exception as e:
            log_event(f"[ERROR][API_CLIENT] Failed to initialize Supabase AsyncClient: {e}", exc_info=True) # Thêm exc_info
            print(f"[ERROR] Không thể tạo Supabase AsyncClient: {e}")
            _supabase_client = None

# Đổi type hint thành AsyncClient
def get_supabase_client() -> Optional[AsyncClient]:
    """
    Trả về instance của Supabase AsyncClient đã được khởi tạo.
    Trả về None nếu client chưa được khởi tạo thành công.
    """
    if _supabase_client is None:
         log_event("[WARN][API_CLIENT] get_supabase_client called before client was initialized!")
    return _supabase_client

# Lưu ý:
# - Không cần gọi .close() cho client ở đây vì thư viện có thể tự quản lý.
# - Các hàm trong auth.py và database.py VẪN PHẢI LÀ ASYNC và dùng await
#   khi gọi phương thức của _supabase_client (là AsyncClient).
