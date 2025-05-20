# src/core/peer_manager.py
import asyncio
from typing import List, Optional, Callable
from src.models.peer import Peer
from src.api import database as api_db
from src.utils.logger import log_event

class PeerManager:
    """Quản lý danh sách peer lấy từ Tracker và gửi thông tin của client lên Tracker."""

    def __init__(self, get_current_user_id_func: Callable[[], Optional[str]]):
        self._get_current_user_id = get_current_user_id_func
        self.known_peers: List[Peer] = []
        log_event("[PEER_MGR] Initialized.")

    async def submit_my_info(self, ip_address: str, port: int) -> bool:
        """Gửi thông tin của client hiện tại lên Tracker (Supabase)."""
        user_id = self._get_current_user_id()
        # Cho phép submit cả khi là visitor (user_id=None) theo logic trong api_db
        log_event(f"[PEER_MGR] Submitting info: IP={ip_address}, Port={port}, User={user_id}")
        result = await api_db.submit_peer_info(user_id, ip_address, port)
        if result.get("success"):
            log_event("[PEER_MGR] Successfully submitted peer info.")
            return True
        else:
            log_event(f"[ERROR][PEER_MGR] Failed to submit peer info: {result.get('error')}")
            return False

    async def refresh_known_peers(self) -> List[Peer]:
        """Lấy danh sách peer mới nhất từ Tracker và cập nhật."""
        my_user_id = self._get_current_user_id()
        log_event("[PEER_MGR] Refreshing known peer list from tracker...")
        try:
            peers_from_api = await api_db.get_active_peer_list()
            # Lọc bỏ chính mình khỏi danh sách (nếu đã đăng nhập)
            if my_user_id:
                self.known_peers = [p for p in peers_from_api if p.user_id != my_user_id]
            else:
                self.known_peers = peers_from_api # Visitor thấy tất cả?
            log_event(f"[PEER_MGR] Known peer list updated. Found {len(self.known_peers)} other peers.")
            return self.known_peers
        except Exception as e:
            log_event(f"[ERROR][PEER_MGR] Failed to refresh known peers: {e}")
            self.known_peers = []
            return []

    def get_known_peers(self) -> List[Peer]:
        """Trả về danh sách peer hiện tại đã biết."""
        return self.known_peers

    def find_peer_by_user_id(self, user_id: str) -> Optional[Peer]:
        """Tìm kiếm peer trong danh sách đã biết dựa trên user_id."""
        if not user_id: return None
        for peer in self.known_peers:
            if peer.user_id == user_id:
                return peer
        return None

    def find_peer_by_address(self, host: str, port: int) -> Optional[Peer]:
         """Tìm kiếm peer trong danh sách đã biết dựa trên địa chỉ."""
         for peer in self.known_peers:
             if peer.ip_address == host and peer.port == port:
                 return peer
         return None