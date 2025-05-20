# src/core/sync_service.py
import asyncio
import datetime
from typing import TYPE_CHECKING, Optional, List
from src.api import database as api_db
from src.storage.local_storage_service import LocalStorageService
from src.p2p.p2p_service import P2PService
from src.models.message import Message
from src.utils.logger import log_event

if TYPE_CHECKING:
    from .app_controller import AppController

class SyncService:
    """Xử lý logic đồng bộ hóa dữ liệu."""

    def __init__(self, controller: 'AppController', local_storage: LocalStorageService, p2p_service: P2PService):
        self.controller = controller
        self.local_storage = local_storage
        self.p2p_service = p2p_service
        log_event("[SYNC_SVC] Initialized.")

    async def backup_message_to_server(self, message: Message):
        """Gửi một bản sao tin nhắn lên server Supabase (để backup)."""
        current_user = self.controller.current_user
        if not current_user:
            log_event("[WARN][SYNC_SVC] Cannot backup message, no current user.")
            return

        # Chỉ backup nếu người gửi là user hiện tại? Hay backup cả tin nhắn nhận được?
        # Theo logic P2P, chỉ cần backup tin nhắn mình gửi đi hoặc tin nhắn mình nhận khi là host?
        # Giả định: Chỉ backup tin nhắn do chính user này gửi đi.
        if message.user_id != current_user.id:
             # log_event(f"[SYNC_SVC] Skipping backup for message not sent by current user.")
             # return # Tạm thời cho phép backup cả tin nhắn nhận được (để đơn giản sync)
             pass


        log_event(f"[SYNC_SVC] Requesting backup for message {message.id or '(new)'} to server...")
        success = await api_db.add_message_backup(
            channel_id=message.channel_id,
            user_id=message.user_id,
            content=message.content
        )
        if success:
            log_event(f"[SYNC_SVC] Message backed up successfully.")
        else:
            log_event(f"[ERROR][SYNC_SVC] Message backup failed.")

    async def perform_initial_sync(self, channel_id: str):
        """
        Thực hiện đồng bộ ban đầu cho một kênh (phiên bản đơn giản).
        Hiện tại chỉ tập trung vào việc Host tải backup từ server về local.
        """
        current_user = self.controller.current_user
        if not current_user or not channel_id: return

        is_host = self.controller.current_channel and self.controller.current_channel.owner_id == current_user.id

        log_event(f"[SYNC_SVC] Performing initial sync for channel {channel_id}. Is host: {is_host}")
        self.controller.status_update_signal.emit(f"Đang đồng bộ kênh...")

        try:
            if is_host:
                # Host: Lấy backup từ server và lưu vào local nếu chưa có
                log_event(f"[SYNC_SVC][HOST] Fetching recent server backups for {channel_id}...")
                server_messages = await api_db.get_message_backups(channel_id, limit=200) # Lấy nhiều hơn chút
                log_event(f"[SYNC_SVC][HOST] Fetched {len(server_messages)} messages from server.")

                new_messages_added = 0
                # TODO: Chạy local_storage trong thread
                for msg in reversed(server_messages):
                    # Cần hàm kiểm tra message tồn tại bằng ID trong local_store
                    # if not self.local_storage.message_exists(msg.id):
                    #     if self.local_storage.add_message(msg):
                    #         new_messages_added += 1
                    # Tạm thời cứ add
                    if self.local_storage.add_message(msg):
                        new_messages_added += 1

                log_event(f"[SYNC_SVC][HOST] Added {new_messages_added} messages from server backup to local store.")
                # TODO: Có thể cần emit signal để UI refresh nếu có message mới từ server

                # TODO: Phần đẩy local mới lên server cần logic phức tạp hơn (dựa trên timestamp) -> Bỏ qua ở bước này
                log_event(f"[SYNC_SVC][HOST] Pushing new local messages to server is deferred.")

            else:
                # Joined User: Logic đồng bộ khi online lại (ví dụ: đẩy tin nhắn offline)
                # TODO: Implement logic đẩy tin nhắn tạo khi offline (lấy từ local cache/db?)
                log_event(f"[SYNC_SVC][JOINED] Pushing offline messages is deferred.")
                # Việc tải lịch sử đã làm ở fetch_channel_history

            self.controller.status_update_signal.emit("Đồng bộ hóa hoàn tất.")
            log_event(f"[SYNC_SVC] Basic sync process finished for channel {channel_id}.")

        except Exception as e:
             log_event(f"[ERROR][SYNC_SVC] Error during basic sync for channel {channel_id}: {e}")
             self.controller.status_update_signal.emit("Lỗi đồng bộ hóa.")