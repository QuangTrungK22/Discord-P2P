# SegmentChatClient/src/models/peer.py
from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True) # frozen=True làm cho đối tượng không thể thay đổi sau khi tạo (immutable), phù hợp cho thông tin kết nối
class Peer:
    """
    Đại diện cho một peer khác trong mạng P2P.
    Chứa thông tin cần thiết để kết nối.
    """
    ip_address: str # Địa chỉ IP của peer
    port: int       # Cổng lắng nghe P2P của peer
    peer_id: Optional[str] = None # ID duy nhất của peer trong bảng 'peers' (nếu có)
    user_id: Optional[str] = None # ID của người dùng liên kết với peer này (nếu peer đã đăng nhập)

    def get_address_tuple(self) -> tuple:
        """Trả về tuple (ip, port) để dùng với socket."""
        return (self.ip_address, self.port)

    def __str__(self) -> str:
        """Biểu diễn dạng string cho dễ debug."""
        user_part = f", UserID: {self.user_id}" if self.user_id else ""
        peerid_part = f", PeerID: {self.peer_id}" if self.peer_id else ""
        return f"Peer({self.ip_address}:{self.port}{user_part}{peerid_part})"

    # frozen=True nên không cần __eq__ và __hash__ mặc định đã ổn