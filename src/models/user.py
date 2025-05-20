# SegmentChatClient/src/models/user.py
from dataclasses import dataclass
from typing import Optional

@dataclass
class User:
    """
    Đại diện cho một người dùng trong hệ thống.
    Thông tin này thường lấy từ Supabase Auth và có thể bổ sung.
    """
    id: str  # UUID từ Supabase Auth, luôn phải có
    email: Optional[str] = None # Email của người dùng
    display_name: Optional[str] = None # Tên hiển thị người dùng tự đặt (lấy từ user_metadata)
    status: str = "offline" # Trạng thái hiện tại: 'online', 'offline', 'invisible'

    def __post_init__(self):
        # Đảm bảo display_name có giá trị mặc định nếu là None sau khi khởi tạo
        if self.display_name is None and self.email:
            self.display_name = self.email # Mặc định dùng email nếu không có display_name
        elif self.display_name is None:
             self.display_name = f"User_{self.id[:4]}" # Hoặc dùng ID nếu không có cả email

    # Có thể thêm các phương thức tiện ích khác nếu cần
    # def is_online(self) -> bool:
    #     return self.status == 'online' or self.status == 'invisible'