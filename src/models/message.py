# SegmentChatClient/src/models/message.py
from dataclasses import dataclass, field
import datetime
from typing import Optional

@dataclass
class Message:
    """
    Đại diện cho một tin nhắn chat trong một kênh.
    """
    channel_id: str # ID của kênh chứa tin nhắn này
    user_id: str    # ID của người gửi tin nhắn
    content: str    # Nội dung tin nhắn
    timestamp: datetime.datetime = field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)) # Thời gian gửi (mặc định là UTC hiện tại)
    id: Optional[str] = None # UUID của tin nhắn từ DB (có thể None nếu chưa lưu)
    sender_display_name: Optional[str] = None # Tên hiển thị của người gửi (để tiện hiển thị trên UI)

    # Có thể thêm phương thức để định dạng thời gian hiển thị
    def get_formatted_timestamp(self, format_str: str = "%H:%M:%S %d/%m/%Y") -> str:
        """Trả về timestamp đã định dạng."""
        # Chuyển về múi giờ địa phương nếu cần
        local_tz = datetime.datetime.now().astimezone().tzinfo
        local_time = self.timestamp.astimezone(local_tz)
        return local_time.strftime(format_str)

    # __post_init__ có thể dùng để chuẩn hóa dữ liệu nếu cần
    # def __post_init__(self):
    #     self.content = self.content.strip()