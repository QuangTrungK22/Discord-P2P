# src/storage/local_storage_service.py
from typing import List, Optional, Any
import datetime
from . import local_store # Import các hàm từ file trước
from src.models.message import Message
from src.utils.logger import log_event

# Biến để đảm bảo init chỉ chạy 1 lần
_initialized = False

class LocalStorageService:
    """Lớp wrapper đơn giản cho các hàm trong local_store.py."""
    def __init__(self):
        global _initialized
        if not _initialized:
            try:
                local_store.init_storage()
                _initialized = True
            except Exception as e:
                log_event(f"[ERROR][STORAGE_SVC] Failed to initialize local storage: {e}")
                # Có thể raise lỗi ở đây để dừng ứng dụng nếu local storage là bắt buộc

    def add_message(self, message: Message) -> bool:
        """Lưu message vào local store."""
        # TODO: Cân nhắc chạy trong thread nếu thao tác DB tốn thời gian
        if not _initialized:
             log_event("[ERROR][STORAGE_SVC] Storage not initialized. Cannot add message.")
             return False
        log_event(f"[STORAGE_SVC] Requesting to add message {message.id} locally.")
        return local_store.add_message(message)

    def get_messages(self, channel_id: str, limit: int = 100, before_ts: Optional[datetime.datetime] = None) -> List[Message]:
        """Lấy messages từ local store."""
        # TODO: Cân nhắc chạy trong thread nếu thao tác DB tốn thời gian
        if not _initialized:
             log_event("[ERROR][STORAGE_SVC] Storage not initialized. Cannot get messages.")
             return []
        log_event(f"[STORAGE_SVC] Requesting to get messages for {channel_id} locally.")
        return local_store.get_messages_for_channel(channel_id, limit, before_ts)

    # Thêm các phương thức wrapper khác nếu cần (ví dụ: get_latest_timestamp)