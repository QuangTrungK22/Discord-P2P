# src/core/app_controller.py
import asyncio
import threading
import datetime
import uuid
import time
import socket # Đảm bảo đã import socket
# Đảm bảo import đầy đủ các kiểu từ typing
from typing import Optional, List, Dict, Any, Tuple

from PySide6.QtCore import QObject, Slot, Signal, QTimer, Qt
from PySide6.QtWidgets import QListWidgetItem, QMessageBox, QInputDialog

# Sử dụng TYPE_CHECKING để tránh import vòng tròn thực sự
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from src.ui.main_window import ChatMainWindow
    from src.ui.chat_page import ChatPage

# Import các thành phần cần thiết
from src.api import auth as api_auth
from src.api import database as api_db # Đảm bảo đã import
from src.p2p.p2p_service import P2PService
from src.p2p import protocol as p2p_proto
from src.storage.local_storage_service import LocalStorageService
from .peer_manager import PeerManager
from .sync_service import SyncService
# Đảm bảo import đủ các models
from src.models.user import User
from src.models.peer import Peer
from src.models.message import Message
from src.models.channel import Channel
from src.utils.logger import log_event # Đảm bảo đã import
from src.core.livestream_service import LivestreamService
from src.ui.livestream_host_window import LivestreamHostWindow
from src.ui.livestream_viewer_window import LivestreamViewerWindow

# Hàm lấy IP cục bộ (đã sửa ở bước trước)
def get_local_ip():
    """Cố gắng lấy địa chỉ IP cục bộ của máy."""
    s = None
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.1)
        s.connect(('8.8.8.8', 1))
        ip = s.getsockname()[0]
    except Exception as e:
        log_event(f"[WARN][UTIL] Không thể tự động lấy IP cục bộ: {e}. Sử dụng fallback 127.0.0.1.")
        ip = '127.0.0.1'
    finally:
        if s:
            s.close()
    return ip

class AppController(QObject):
    # ----- Định nghĩa các Signals (Giữ nguyên) -----
    login_successful = Signal(User)
    login_failed = Signal(str)
    signup_successful = Signal()
    signup_failed = Signal(str)
    logout_finished = Signal()
    status_update_signal = Signal(str)
    connection_status_signal = Signal(str)
    networkStatusChanged = Signal(bool)
    peer_list_updated = Signal(list)
    channelsUpdated = Signal(list, list)
    channelCreated = Signal(Channel)
    channel_joined = Signal(Channel)
    channel_error = Signal(str)
    new_message_signal = Signal(Message)
    current_channel_history_cleared = Signal()
    messageSent = Signal(Message)
    messageError = Signal(str)
    requestPageChange = Signal(str)
    livestream_status_changed = Signal(bool, str, str)

    def __init__(self, main_window: 'ChatMainWindow'):
        super().__init__()
        self.main_window = main_window
        self.current_user: Optional[User] = None
        self.current_channel: Optional[Channel] = None
        self.p2p_listening_port: Optional[int] = None
        self.is_online: bool = False
        self.user_profiles_cache: Dict[str, Dict[str, Any]] = {}
        self.livestream_service: Optional[LivestreamService] = None
        self.livestream_host_window: Optional[LivestreamHostWindow] = None
        self.livestream_viewer_window: Optional[LivestreamViewerWindow] = None

        log_event("[CTRL] Initializing core components...")
        self.local_storage = LocalStorageService()
        self.peer_manager = PeerManager(
            get_current_user_id_func=lambda: self.current_user.id if self.current_user else None
        )
        self.p2p_service = P2PService(
            peer_manager=self.peer_manager,
            message_callback=self._handle_p2p_message
        )
        self.sync_service = SyncService(
            local_storage=self.local_storage,
            p2p_service=self.p2p_service,
            controller=self
        )
        self._connect_ui_signals() # Sẽ gọi sau khi controller được set cho main_window
        log_event("[CTRL] Core components initialized.")

        self.peer_refresh_interval_ms = 30 * 1000
        self.peer_update_timer = QTimer(self)
        self.peer_update_timer.timeout.connect(self._schedule_peer_refresh)
        self.network_check_timer = QTimer(self)
        self.network_check_timer.setInterval(15000)
        self.network_check_timer.timeout.connect(self._check_network_status)

    def _initialize_livestream_service(self):
        if self.p2p_service and self.current_user:
            self.livestream_service = LivestreamService(
                self.p2p_service,
                self.current_user.id,
                self.current_user.display_name or f"User_{self.current_user.id[:6]}"
            )
            self.livestream_service.livestream_started_signal.connect(self._on_livestream_started_globally)
            self.livestream_service.livestream_ended_signal.connect(self._on_livestream_ended_globally)
            log_event("[CTRL] LivestreamService initialized.")
        else:
            log_event("[WARN][CTRL] Cannot initialize LivestreamService: P2PService or CurrentUser not ready.")

    def _connect_ui_signals(self):
        """Kết nối các tín hiệu từ UI pages tới các slots/handlers trong Controller."""
        log_event("[CTRL] Connecting UI signals...")
        if not self.main_window:
            log_event("[ERROR][CTRL] Cannot connect signals: MainWindow instance is not available.")
            return
        try:
            login_page = getattr(self.main_window, 'login_page', None)
            signup_page = getattr(self.main_window, 'signup_page', None)
            chat_page: Optional['ChatPage'] = getattr(self.main_window, 'chat_page', None)
            start_page = getattr(self.main_window, 'start_page', None)

            if login_page:
                login_page.login_requested.connect(self.handle_login_attempt)
                login_page.back_clicked.connect(lambda: self.requestPageChange.emit("start"))
            else: log_event("[WARN][CTRL] MainWindow missing 'login_page'.")

            if signup_page:
                signup_page.register_requested.connect(self.handle_signup_attempt)
                signup_page.back_clicked.connect(lambda: self.requestPageChange.emit("start"))
            else: log_event("[WARN][CTRL] MainWindow missing 'signup_page'.")

            if chat_page:
                chat_page.logout_requested.connect(self.handle_logout)
                chat_page.send_message_requested.connect(self.send_chat_message)
                chat_page.create_channel_requested.connect(self._request_create_channel)
                chat_page.join_channel_requested.connect(self._request_join_channel)
                chat_page.leave_channel_requested.connect(self._request_leave_channel)
                chat_page.channel_selected.connect(self.handle_channel_selected_id)
                self.peer_list_updated.connect(chat_page.update_member_list_ui)
                self.new_message_signal.connect(chat_page.display_message_object)
                self.current_channel_history_cleared.connect(chat_page.clear_message_display)

                if hasattr(chat_page, 'status_changed') and hasattr(self, 'handle_status_change_request'):
                    chat_page.status_changed.connect(self.handle_status_change_request)
                    log_event("[CTRL] Đã kết nối chat_page.status_changed với AppController.handle_status_change_request.")
                else:
                    if not hasattr(chat_page, 'status_changed'):
                        log_event("[WARN][CTRL] ChatPage không có signal 'status_changed'.")
                    if not hasattr(self, 'handle_status_change_request'):
                        log_event("[WARN][CTRL] AppController không có slot 'handle_status_change_request'.")

                # ===== THÊM KẾT NỐI CHO LIVESTREAM SIGNALS TỪ CHAT_PAGE =====
                if hasattr(chat_page, 'request_start_livestream') and hasattr(self, 'handle_request_start_livestream'):
                    chat_page.request_start_livestream.connect(self.handle_request_start_livestream)
                    log_event("[CTRL] Đã kết nối chat_page.request_start_livestream với AppController.handle_request_start_livestream.")
                else:
                    if not hasattr(chat_page, 'request_start_livestream'):
                        log_event("[WARN][CTRL] ChatPage thiếu signal 'request_start_livestream'.")
                    if not hasattr(self, 'handle_request_start_livestream'):
                        log_event("[WARN][CTRL] AppController thiếu slot 'handle_request_start_livestream'.")

                if hasattr(chat_page, 'request_view_livestream') and hasattr(self, 'handle_request_view_livestream'):
                    chat_page.request_view_livestream.connect(self.handle_request_view_livestream)
                    log_event("[CTRL] Đã kết nối chat_page.request_view_livestream với AppController.handle_request_view_livestream.")
                else:
                    if not hasattr(chat_page, 'request_view_livestream'):
                        log_event("[WARN][CTRL] ChatPage thiếu signal 'request_view_livestream'.")
                    if not hasattr(self, 'handle_request_view_livestream'):
                        log_event("[WARN][CTRL] AppController thiếu slot 'handle_request_view_livestream'.")
                # ============================================================

            else: log_event("[WARN][CTRL] MainWindow missing 'chat_page'.")

            if start_page:
                 start_page.login_clicked.connect(lambda: self.requestPageChange.emit("login"))
                 start_page.signup_clicked.connect(lambda: self.requestPageChange.emit("signup"))
            else: log_event("[WARN][CTRL] MainWindow missing 'start_page'.")

            log_event("[CTRL] UI signal connection process completed successfully.")
        except AttributeError as e:
            log_event(f"[ERROR][CTRL] Failed to connect UI signals due to AttributeError: {e}. Check page/signal names.", exc_info=True)
        except Exception as e:
            log_event(f"[ERROR][CTRL] Unexpected error during UI signal connection: {e}", exc_info=True)

    @Slot(str, str)
    def handle_login_attempt(self, email: str, password: str):
        log_event(f"[CTRL] Handle Login Attempt for: {email}")
        self.status_update_signal.emit("Đang đăng nhập...")
        asyncio.create_task(self._perform_login(email, password), name=f"LoginTask_{email}")

    async def _perform_login(self, email: str, password: str):
        log_event(f"[CTRL][ASYNC] Performing login for {email}...")
        login_result = None
        try:
            login_result = await api_auth.sign_in(email, password)
            if login_result and login_result.get("success"):
                user_data = login_result.get("user")
                if user_data and user_data.id:
                     display_name_from_meta = getattr(user_data, 'user_metadata', {}).get('display_name')
                     self.current_user = User(
                         id=user_data.id,
                         email=getattr(user_data, 'email', None),
                         display_name=display_name_from_meta
                     )
                     log_event(f"[CTRL] Login successful for User: {self.current_user.id}, Email: {self.current_user.email}, Name: {self.current_user.display_name}")
                     status_updated = await api_db.update_user_status(self.current_user.id, "online")
                     if status_updated:
                        log_event(f"[CTRL] User {self.current_user.id} status set to 'online' successfully.")
                     else:
                        log_event(f"[WARN][CTRL] Failed to set user {self.current_user.id} status to 'online'.")
                     await self._post_login_setup()
                     self.login_successful.emit(self.current_user)
                else:
                    raise ValueError("Login successful but user data or ID is missing from API response.")
            else:
                error_msg = login_result.get("error", "Lỗi không xác định") if isinstance(login_result, dict) else "Phản hồi API không hợp lệ"
                log_event(f"[CTRL] Login failed for {email}: {error_msg}")
                self.login_failed.emit(error_msg)
        except Exception as e:
            error_msg = f"Lỗi hệ thống khi đăng nhập: {e}"
            log_event(f"[ERROR][CTRL] Exception during login for {email}: {e}", exc_info=True)
            self.login_failed.emit(error_msg)

    @Slot(str, str, str)
    def handle_signup_attempt(self, display_name: str, email: str, password: str):
        log_event(f"[CTRL] Handle Signup Attempt for: {email}, Name: {display_name}")
        self.status_update_signal.emit("Đang đăng ký...")
        asyncio.create_task(self._perform_signup(display_name, email, password), name=f"SignupTask_{email}")

    async def _perform_signup(self, display_name: str, email: str, password: str):
        log_event(f"[CTRL][ASYNC] Performing signup for {email}...")
        try:
            signup_result = await api_auth.sign_up(email, password, display_name)
            if signup_result and signup_result.get("success"):
                log_event(f"[CTRL] Signup successful for {email}.")
                if signup_result.get("needs_verification"):
                    msg = "Đăng ký thành công! Vui lòng kiểm tra email để xác thực."
                else:
                    msg = "Đăng ký thành công! Bạn có thể đăng nhập ngay."
                self.status_update_signal.emit(msg)
                self.signup_successful.emit()
            else:
                error_msg = signup_result.get("error", "Lỗi không xác định") if isinstance(signup_result, dict) else "Phản hồi API không hợp lệ"
                log_event(f"[CTRL] Signup failed for {email}: {error_msg}")
                self.signup_failed.emit(error_msg)
        except Exception as e:
            error_msg = f"Lỗi hệ thống khi đăng ký: {e}"
            log_event(f"[ERROR][CTRL] Exception during signup for {email}: {e}", exc_info=True)
            self.signup_failed.emit(error_msg)

    @Slot()
    def handle_logout(self):
        log_event("[CTRL] Logout initiated by user.")
        self.status_update_signal.emit("Đang đăng xuất...")
        self.peer_update_timer.stop()
        self.stop_network_check()
        asyncio.create_task(self._perform_logout(), name="LogoutTask")

    async def _perform_logout(self):
        log_event("[CTRL][ASYNC] Performing logout...")
        user_id_to_set_offline = None
        if self.current_user and self.current_user.id:
            user_id_to_set_offline = self.current_user.id
        try:
            if self.p2p_service and self.p2p_service.is_listening():
                log_event("[CTRL] Stopping P2P service...")
                await self.p2p_service.stop_server()
                log_event("[CTRL] P2P service stopped.")
            if user_id_to_set_offline:
                status_updated = await api_db.update_user_status(user_id_to_set_offline, "offline")
                if status_updated:
                    log_event(f"[CTRL] User {user_id_to_set_offline} status set to 'offline' successfully.")
                else:
                    log_event(f"[WARN][CTRL] Failed to set user {user_id_to_set_offline} status to 'offline'.")
            signout_success = await api_auth.sign_out()
            if signout_success:
                log_event("[CTRL] Supabase sign out successful.")
            else:
                log_event("[WARN][CTRL] Supabase sign out call failed or returned false.")
            self.current_user = None
            self.current_channel = None
            self.peer_manager.known_peers = []
            self.p2p_listening_port = None
            self.is_online = False
            log_event("[CTRL] Local state cleared after logout.")
            self.logout_finished.emit()
        except Exception as e:
            log_event(f"[ERROR][CTRL] Exception during logout: {e}", exc_info=True)
            self.logout_finished.emit()

    async def _post_login_setup(self):
        if not self.current_user:
            log_event("[ERROR][CTRL] Post login setup called without a current user.")
            return

        log_event("[CTRL] Running post-login setup...")
        self.status_update_signal.emit("Đang khởi tạo kết nối P2P...")
        if not self.p2p_service.is_listening():
            host, port = await self.p2p_service.start_server(port=0)
            if not port:
                log_event("[ERROR][CTRL] Failed to start P2P server during post-login setup!")
                self.status_update_signal.emit("Lỗi khởi tạo P2P!")
                return
            self.p2p_listening_port = port
            log_event(f"[CTRL] P2P listening on {host}:{port}")
        else:
             self.p2p_listening_port = self.p2p_service.get_listening_port()
             log_event(f"[CTRL] P2P service already listening on port {self.p2p_listening_port}.")
        my_ip = get_local_ip()
        log_event(f"[CTRL] Submitting peer info (IP={my_ip}, Port={self.p2p_listening_port}) to tracker...")
        if self.p2p_listening_port is not None:
            submit_success = await self.peer_manager.submit_my_info(my_ip, self.p2p_listening_port)
            if not submit_success:
                log_event("[WARN][CTRL] Failed to submit peer info to tracker (check RLS/connection).")
        else:
            log_event("[WARN][CTRL] Cannot submit peer info: Listening port is None.")
        self.status_update_signal.emit("Đang tải dữ liệu người dùng và kênh...")
        try:
            await asyncio.gather(
                self._run_peer_refresh_and_connect(),
                self.fetch_channels(),
                return_exceptions=True
            )
        except Exception as e:
             log_event(f"[ERROR][CTRL] Error during initial data fetch gather: {e}", exc_info=True)
        self._initialize_livestream_service()
        self.peer_update_timer.start(self.peer_refresh_interval_ms)
        self.start_network_check()
        log_event("[CTRL] Peer refresh and network check timers started.")
        log_event("[CTRL] Post-login setup complete.")
        self.status_update_signal.emit("Sẵn sàng!")

    async def check_existing_session(self):
        log_event("[CTRL] Checking for existing login session...")
        try:
            existing_user_data = await api_auth.get_current_session_user()
            log_event(f"[CTRL] Session check result: {'Found' if existing_user_data else 'None'}")
            if existing_user_data and existing_user_data.id:
                display_name_from_meta = getattr(existing_user_data, 'user_metadata', {}).get('display_name')
                self.current_user = User(
                    id=existing_user_data.id,
                    email=getattr(existing_user_data, 'email', None),
                    display_name=display_name_from_meta
                )
                log_event(f"[CTRL] Found active session for User ID: {self.current_user.id}, Name: {self.current_user.display_name}")
                self.login_successful.emit(self.current_user)
                await self._post_login_setup()
            else:
                log_event("[CTRL] No active session found. Requesting start page.")
                self.requestPageChange.emit('start')
        except Exception as e:
            log_event(f"[ERROR][CTRL] Error checking existing session: {e}", exc_info=True)
            self.requestPageChange.emit('start')

    @Slot()
    def _schedule_peer_refresh(self):
        if self.current_user and self.is_online:
            log_event("[CTRL] Scheduling peer list refresh task...")
            asyncio.create_task(self._run_peer_refresh_and_connect(), name="PeerRefreshTask")
        elif not self.is_online:
             log_event("[CTRL] Skipping peer refresh: Currently offline.")

    # src/core/app_controller.py

# ... (các import và phần đầu của class AppController giữ nguyên) ...

    async def _run_peer_refresh_and_connect(self):
        if not self.current_user or not self.is_online:
            # Thêm kiểm tra self.p2p_service đã được khởi tạo
            if not self.p2p_service:
                log_event("[WARN][CTRL] P2P Service not initialized, skipping peer refresh.")
                return
            log_event(f"[CTRL][ASYNC] Skipping peer refresh: User not logged in ({not self.current_user}), offline ({not self.is_online}), or P2P service not ready.")
            return

        log_event("[CTRL][ASYNC] Refreshing peer list and P2P connections...")
        known_peers: List[Peer] = []
        try:
            known_peers = await self.peer_manager.refresh_known_peers()
            log_event(f"[CTRL] Refreshed peer list from tracker, found {len(known_peers)} OTHER peers.")

            current_p2p_writers = self.p2p_service.get_connected_peers_addresses()
            log_event(f"[CTRL] Currently managing {len(current_p2p_writers)} P2P writers: {current_p2p_writers}")

            target_addrs = {p.get_address_tuple() for p in known_peers if p.ip_address and p.port}
            log_event(f"[CTRL] Target P2P addresses from tracker: {target_addrs}")

            # --- Logic kết nối các peer mới ---
            peers_to_connect = target_addrs - current_p2p_writers
            connect_tasks = []
            if peers_to_connect:
                 log_event(f"[CTRL] Peers to connect: {peers_to_connect}")
                 my_current_ip = get_local_ip() # Lấy IP hiện tại một lần
                 for ip, port in peers_to_connect:
                      # Kiểm tra để không tự kết nối đến chính mình qua tracker
                      if ip == my_current_ip and port == self.p2p_listening_port:
                          log_event(f"[CTRL] Skipping connect to self: {ip}:{port}")
                          continue
                      connect_tasks.append(asyncio.create_task(self.p2p_service.connect_to_peer(ip, port), name=f"ConnectTask_{ip}:{port}"))

            # --- Logic ngắt kết nối các peer không còn trong tracker (ĐÃ SỬA ĐỔI) ---
            potential_peers_to_disconnect = current_p2p_writers - target_addrs
            disconnect_tasks = []
            if potential_peers_to_disconnect:
                log_event(f"[CTRL] Potential peers to disconnect (not in tracker): {potential_peers_to_disconnect}")
                for ip, port in potential_peers_to_disconnect:
                    peer_addr_tuple = (ip, port)
                    should_disconnect = True # Mặc định là ngắt kết nối

                    # Tìm thông tin peer từ PeerManager bằng địa chỉ
                    peer_object = self.peer_manager.find_peer_by_address(ip, port)
                    peer_id_to_check = peer_object.user_id if peer_object else None

                    if self.livestream_service and peer_id_to_check:
                        # 1. Không ngắt kết nối nếu peer này là HOST của stream mà MÌNH đang xem
                        if self.livestream_service.is_viewing and \
                           self.livestream_service.active_streamer_id == peer_id_to_check:
                            log_event(f"[CTRL] Keeping connection with {ip}:{port} (User ID: {peer_id_to_check}) - They are hosting the stream I am viewing.")
                            should_disconnect = False

                        # 2. Không ngắt kết nối nếu MÌNH là HOST và peer này là viewer đang xem stream của MÌNH
                        #    Điều này cần P2PService hoặc LivestreamService theo dõi danh sách viewer đang kết nối.
                        #    Hiện tại, LivestreamService không có danh sách viewer rõ ràng ở mức P2P connection.
                        #    Tuy nhiên, nếu P2PService duy trì kết nối tốt, broadcast sẽ tự động đến họ.
                        #    Giải pháp đơn giản ở đây là: nếu MÌNH đang HOST, thì không chủ động ngắt kết nối với ai cả
                        #    từ logic này, để P2P layer tự xử lý (ví dụ: peer tự ngắt).
                        #    Hoặc, có thể cân nhắc không ngắt nếu mình đang host và peer này có trong danh sách người tham gia kênh hiện tại.
                        if self.livestream_service.is_hosting:
                            # Kiểm tra xem peer này có phải là một trong những người đang xem stream của mình không.
                            # Cách đơn giản: nếu mình đang host, có thể tạm thời không ngắt ai cả từ logic này
                            # và để kết nối tự nhiên đóng nếu peer viewer không còn hoạt động.
                            # Đây là một điểm có thể cần cải thiện thêm nếu muốn chính xác hơn.
                            # Ví dụ: có thể thêm một danh sách "active_viewer_connections" vào LivestreamService
                            # Tuy nhiên, để đơn giản hóa bước đầu, chúng ta có thể làm như sau:
                            log_event(f"[CTRL] I am hosting. Evaluating disconnection for {ip}:{port} (User ID: {peer_id_to_check}).")
                            # Nếu muốn giữ kết nối với tất cả khi đang host:
                            # log_event(f"[CTRL] Keeping connection with {ip}:{port} because I am currently hosting a livestream.")
                            # should_disconnect = False

                            # Một cách tiếp cận khác: chỉ giữ kết nối nếu peer đó có trong kênh hiện tại
                            # (giả định stream liên quan đến kênh)
                            if self.current_channel and peer_id_to_check:
                                member_ids_in_channel = await api_db.get_channel_member_ids(self.current_channel.id) # Cần await
                                if peer_id_to_check in member_ids_in_channel:
                                    log_event(f"[CTRL] Keeping connection with {ip}:{port} (User ID: {peer_id_to_check}) - They are in my current channel and I am hosting.")
                                    should_disconnect = False
                                else:
                                    log_event(f"[CTRL] Peer {peer_id_to_check} is not in current channel {self.current_channel.id}. Will disconnect if not in tracker.")


                    if should_disconnect:
                        log_event(f"[CTRL] Scheduling disconnect for {ip}:{port} (User ID: {peer_id_to_check})")
                        disconnect_tasks.append(asyncio.create_task(self.p2p_service.disconnect_from_peer(ip, port), name=f"DisconnectTask_{ip}:{port}"))
                    # else: đã log lý do không ngắt kết nối ở trên

            if connect_tasks or disconnect_tasks:
                log_event(f"[CTRL] Executing {len(connect_tasks)} connect and {len(disconnect_tasks)} disconnect tasks...")
                results = await asyncio.gather(*(connect_tasks + disconnect_tasks), return_exceptions=True)
                # Log kết quả chi tiết hơn
                for i, res in enumerate(results):
                    task_name = "Unknown Task"
                    if i < len(connect_tasks):
                        task_name = connect_tasks[i].get_name()
                    else:
                        task_name = disconnect_tasks[i - len(connect_tasks)].get_name()

                    if isinstance(res, Exception):
                        log_event(f"[ERROR][CTRL] Task {task_name} failed: {res}")
                    else:
                        log_event(f"[CTRL] Task {task_name} completed with result: {res}")
            else:
                 log_event("[CTRL] No P2P connection changes needed based on tracker and livestream status.")
        except socket.gaierror as e:
            log_event(f"[ERROR][CTRL] Socket/DNS error during peer refresh/connect (e.g., tracker unavailable): {e}", exc_info=False) # Không cần full traceback cho lỗi DNS
        except Exception as e:
            log_event(f"[ERROR][CTRL] Exception during peer refresh/connect: {e}", exc_info=True)

# ... (phần còn lại của class AppController giữ nguyên) ...

    @Slot()
    def refresh_channels(self):
        if self.current_user and self.is_online:
            log_event("[CTRL] Scheduling channel list refresh task...")
            asyncio.create_task(self.fetch_channels(), name="FetchChannelsTask")
        elif not self.is_online:
             log_event("[CTRL] Skipping channel refresh: Currently offline.")

    async def fetch_channels(self):
         if not self.current_user: return
         if not self.current_user.id:
              log_event("[ERROR][CTRL] Cannot fetch channels: current_user has no ID.")
              return
         log_event("[CTRL][ASYNC] Fetching channel lists from database...")
         joined_channels: List[Channel] = []
         hosted_channels: List[Channel] = []
         try:
             joined_task = asyncio.create_task(api_db.get_my_joined_channels(self.current_user.id))
             hosted_task = asyncio.create_task(api_db.get_my_hosted_channels(self.current_user.id))
             results = await asyncio.gather(joined_task, hosted_task, return_exceptions=True)
             if isinstance(results[0], Exception):
                 log_event(f"[ERROR][CTRL] Failed to fetch joined channels: {results[0]}", exc_info=True)
             elif isinstance(results[0], list):
                 joined_channels = results[0]
             else:
                 log_event(f"[WARN][CTRL] Unexpected result type for joined channels: {type(results[0])}")
             if isinstance(results[1], Exception):
                 log_event(f"[ERROR][CTRL] Failed to fetch hosted channels: {results[1]}", exc_info=True)
             elif isinstance(results[1], list):
                 hosted_channels = results[1]
             else:
                 log_event(f"[WARN][CTRL] Unexpected result type for hosted channels: {type(results[1])}")
             log_event(f"[CTRL] Fetched {len(joined_channels)} joined and {len(hosted_channels)} hosted channels.")
             self.channelsUpdated.emit(joined_channels, hosted_channels)
         except Exception as e:
              log_event(f"[ERROR][CTRL] Unexpected error during channel fetch gather: {e}", exc_info=True)
              self.channelsUpdated.emit([], [])

    @Slot(str)
    def handle_channel_selected_id(self, channel_id: Optional[str]):
         log_event(f"[CTRL] Handling channel selection change. Selected ID: {channel_id}")
         if not channel_id:
              log_event("[CTRL] Channel deselected.")
              if self.current_channel:
                    self.current_channel = None
                    self.current_channel_history_cleared.emit()
                    self.peer_list_updated.emit([])
              return
         found_channel = self._find_channel_by_id(channel_id)
         if not found_channel:
              log_event(f"[WARN][CTRL] Could not find Channel object for selected ID: {channel_id}. Maybe list is outdated?")
              self.status_update_signal.emit(f"Lỗi: Không tìm thấy thông tin kênh.")
              return
         if self.current_channel is None or self.current_channel.id != found_channel.id:
             self.current_channel = found_channel
             log_event(f"[CTRL] Current channel set to: {self.current_channel.name} (ID: {self.current_channel.id})")
             self.status_update_signal.emit(f"Đã vào kênh: {self.current_channel.name}")
             self.current_channel_history_cleared.emit()
             self.peer_list_updated.emit([])
             if self.main_window and self.main_window.chat_page:
                 self.main_window.chat_page.set_current_channel_name(self.current_channel.name)
             asyncio.create_task(self.fetch_channel_history_and_peers(), name=f"FetchHistory_{channel_id}")
         else:
              log_event(f"[CTRL] Channel {channel_id} already selected.")

    def _find_channel_by_id(self, channel_id: str) -> Optional[Channel]:
        chat_page = getattr(self.main_window, 'chat_page', None)
        if not chat_page: return None
        all_channels = []
        for i in range(chat_page.channel_list.count()):
            item = chat_page.channel_list.item(i)
            data = item.data(Qt.UserRole) if item else None
            if isinstance(data, Channel): all_channels.append(data)
        for i in range(chat_page.hosting_list.count()):
            item = chat_page.hosting_list.item(i)
            data = item.data(Qt.UserRole) if item else None
            if isinstance(data, Channel): all_channels.append(data)
        return next((c for c in all_channels if c.id == channel_id), None)

    async def fetch_channel_history_and_peers(self):
         if not self.current_channel or not self.current_user:
             log_event("[CTRL][FETCH_CHAN_DATA] Không thể tải: không có kênh hiện tại hoặc người dùng hiện tại.")
             self.current_channel_history_cleared.emit()
             self.peer_list_updated.emit([])
             return
         channel_id = self.current_channel.id
         channel_name = self.current_channel.name
         is_host = self.current_channel.owner_id == self.current_user.id
         my_actual_user_id = self.current_user.id
         log_event(f"[CTRL][FETCH_CHAN_DATA] Bắt đầu tải lịch sử và thành viên cho kênh '{channel_name}' (ID: {channel_id}). Host: {is_host}")
         self.status_update_signal.emit(f"Đang tải dữ liệu kênh {channel_name}...")
         messages: List[Message] = []
         channel_members_info_for_ui: List[Dict[str, Any]] = []
         try:
             log_event(f"[CTRL][FETCH_CHAN_DATA] Đang tải lịch sử tin nhắn cho kênh {channel_id}...")
             if is_host:
                 messages = self.local_storage.get_messages(channel_id, limit=100)
                 log_event(f"[CTRL][FETCH_CHAN_DATA] Đã tải {len(messages)} tin nhắn từ local store (host).")
             else:
                 messages = await api_db.get_message_backups(channel_id, limit=100)
                 log_event(f"[CTRL][FETCH_CHAN_DATA] Đã tải {len(messages)} tin nhắn từ server backup.")
             for msg_obj in messages:
                 self.new_message_signal.emit(msg_obj)
             log_event(f"[CTRL][FETCH_CHAN_DATA] Đã hiển thị {len(messages)} tin nhắn đã tải.")
             log_event(f"[CTRL][FETCH_CHAN_DATA] Đang tải ID thành viên cho kênh {channel_id}...")
             member_ids_in_channel = await api_db.get_channel_member_ids(channel_id)
             if not member_ids_in_channel:
                 log_event(f"[CTRL][FETCH_CHAN_DATA] Không tìm thấy ID thành viên nào cho kênh {channel_id}.")
                 self.peer_list_updated.emit([])
             else:
                 log_event(f"[CTRL][FETCH_CHAN_DATA] Tìm thấy {len(member_ids_in_channel)} ID thành viên: {member_ids_in_channel}. Đang lấy profiles...")
                 profiles_data_map = await api_db.get_user_profiles(member_ids_in_channel)
                 log_event(f"[CTRL][FETCH_CHAN_DATA] Đã lấy được thông tin profile cho {len(profiles_data_map)} users. Dữ liệu profiles: {profiles_data_map}")
                 active_p2p_user_ids_from_manager = {p.user_id for p in self.peer_manager.get_known_peers() if p.user_id}
                 log_event(f"[CTRL][FETCH_CHAN_DATA] User IDs đang active P2P (từ PeerManager, không bao gồm self): {active_p2p_user_ids_from_manager}")
                 for member_id in member_ids_in_channel:
                     profile = profiles_data_map.get(member_id)
                     display_name_for_ui = f"User_{member_id[:6]}"
                     user_db_status = "offline"
                     if profile:
                         display_name_for_ui = profile.get("display_name", display_name_for_ui)
                         user_db_status = profile.get("status", user_db_status)
                     else:
                         log_event(f"[WARN][CTRL][FETCH_CHAN_DATA] Không tìm thấy dữ liệu profile cho member_id {member_id} trong kênh {channel_id}.")
                     is_online_for_display_color = (user_db_status == "online")
                     actual_status_for_ui_tooltip = user_db_status
                     has_p2p_activity_flag = False
                     if member_id == my_actual_user_id:
                        has_p2p_activity_flag = self.p2p_service.is_listening()
                     elif member_id in active_p2p_user_ids_from_manager:
                        has_p2p_activity_flag = True
                     log_event(f"[CTRL_MEMBER_STATUS_FINAL] User ID: {member_id}, Name: '{display_name_for_ui}', DB_Status: '{user_db_status}', DisplayAsOnlineColor: {is_online_for_display_color}")
                     channel_members_info_for_ui.append({
                         "user_id": member_id,
                         "display_name": display_name_for_ui,
                         "is_online": is_online_for_display_color,
                         "actual_status": actual_status_for_ui_tooltip,
                         "has_p2p_activity": has_p2p_activity_flag
                     })
                 log_event(f"[CTRL][FETCH_CHAN_DATA] Đã xử lý {len(channel_members_info_for_ui)} thông tin thành viên cho kênh {channel_id} để gửi đến UI.")
                 self.peer_list_updated.emit(channel_members_info_for_ui)
             if is_host:
                 log_event("[CTRL][FETCH_CHAN_DATA] Kênh này do user hiện tại làm host. Lên lịch chạy initial sync...")
                 asyncio.create_task(self.sync_service.perform_initial_sync(channel_id), name=f"PostFetchSyncTask_{channel_id}")
             self.status_update_signal.emit(f"Đã tải xong dữ liệu kênh {channel_name}.")
         except Exception as e:
              log_event(f"[ERROR][CTRL][FETCH_CHAN_DATA] Lỗi khi tải lịch sử/thành viên cho kênh {channel_id}: {e}", exc_info=True)
              self.status_update_signal.emit(f"Lỗi tải dữ liệu kênh {channel_name}.")
              self.peer_list_updated.emit([])

    @Slot(str)
    def _request_create_channel(self, channel_name: str):
        log_event(f"[CTRL] Received request to create channel: '{channel_name}'")
        if not self.current_user:
            self.channel_error.emit("Vui lòng đăng nhập để tạo kênh.")
            return
        if not channel_name:
             self.channel_error.emit("Tên kênh không được để trống.")
             return
        self.status_update_signal.emit(f"Đang tạo kênh '{channel_name}'...")
        asyncio.create_task(self._perform_create_channel(channel_name), name=f"CreateChannel_{channel_name}")

    async def _perform_create_channel(self, channel_name: str):
        if not self.current_user: return
        log_event(f"[CTRL][ASYNC] Performing create channel '{channel_name}'...")
        try:
            new_channel = await api_db.create_channel(self.current_user.id, channel_name)
            if new_channel:
                log_event(f"[CTRL] Channel created successfully via API: {new_channel.name} (ID: {new_channel.id})")
                self.channelCreated.emit(new_channel)
                await self.fetch_channels()
                self.status_update_signal.emit(f"Đã tạo kênh: {new_channel.name}")
                await api_db.join_channel(self.current_user.id, new_channel.id)
                log_event(f"[CTRL] Auto-joined created channel {new_channel.id}")
            else:
                error_msg = f"Không thể tạo kênh '{channel_name}'. Lỗi server hoặc RLS."
                log_event(f"[ERROR][CTRL] Channel creation failed for '{channel_name}': API returned None.")
                self.channel_error.emit(error_msg)
        except Exception as e:
            error_msg = f"Lỗi hệ thống khi tạo kênh '{channel_name}': {e}"
            log_event(f"[ERROR][CTRL] Exception during create channel '{channel_name}': {e}", exc_info=True)
            self.channel_error.emit(error_msg)

    @Slot(str)
    def _request_join_channel(self, channel_id: str):
        log_event(f"[CTRL] Received request to join channel: {channel_id}")
        if not self.current_user:
            self.channel_error.emit("Vui lòng đăng nhập để tham gia kênh.")
            return
        if not channel_id:
            self.channel_error.emit("ID kênh không hợp lệ.")
            return
        self.status_update_signal.emit(f"Đang tham gia kênh {channel_id}...")
        asyncio.create_task(self._perform_join_channel(channel_id), name=f"JoinChannel_{channel_id}")

    async def _perform_join_channel(self, channel_id: str):
        if not self.current_user: return
        log_event(f"[CTRL][ASYNC] Performing join channel {channel_id}...")
        try:
            success = await api_db.join_channel(self.current_user.id, channel_id)
            if success:
                log_event(f"[CTRL] Successfully joined channel {channel_id} via API.")
                await self.fetch_channels()
                self.status_update_signal.emit(f"Đã tham gia kênh {channel_id}")
            else:
                error_msg = f"Không thể tham gia kênh {channel_id}. Kênh không tồn tại hoặc lỗi."
                log_event(f"[ERROR][CTRL] Failed to join channel {channel_id}: API returned False.")
                self.channel_error.emit(error_msg)
        except Exception as e:
            error_msg = f"Lỗi hệ thống khi tham gia kênh {channel_id}: {e}"
            log_event(f"[ERROR][CTRL] Exception during join channel {channel_id}: {e}", exc_info=True)
            self.channel_error.emit(error_msg)

    @Slot(str)
    def _request_leave_channel(self, channel_id: str):
        log_event(f"[CTRL] Received request to leave channel: {channel_id}")
        if not self.current_user:
             self.channel_error.emit("Lỗi: Chưa đăng nhập.")
             return
        if not channel_id:
             self.channel_error.emit("Lỗi: Không có kênh nào được chọn để rời.")
             return
        self.status_update_signal.emit(f"Đang rời khỏi kênh {channel_id}...")
        asyncio.create_task(self._perform_leave_channel(channel_id), name=f"LeaveChannel_{channel_id}")

    async def _perform_leave_channel(self, channel_id: str):
        if not self.current_user: return
        log_event(f"[CTRL][ASYNC] Performing leave channel {channel_id}...")
        try:
            success = await api_db.leave_channel(self.current_user.id, channel_id)
            if success:
                log_event(f"[CTRL] Successfully left channel {channel_id} via API.")
                if self.current_channel and self.current_channel.id == channel_id:
                     self.handle_channel_selected_id(None)
                await self.fetch_channels()
                self.status_update_signal.emit(f"Đã rời khỏi kênh {channel_id}")
            else:
                error_msg = f"Không thể rời kênh {channel_id}. Có lỗi xảy ra."
                log_event(f"[ERROR][CTRL] Failed to leave channel {channel_id}: API returned False.")
                self.channel_error.emit(error_msg)
        except Exception as e:
            error_msg = f"Lỗi hệ thống khi rời kênh {channel_id}: {e}"
            log_event(f"[ERROR][CTRL] Exception during leave channel {channel_id}: {e}", exc_info=True)
            self.channel_error.emit(error_msg)

    @Slot(str)
    def send_chat_message(self, message_text: str):
        log_event(f"[CTRL] Handling request to send message: '{message_text[:50]}...'")
        if not message_text.strip():
            self.messageError.emit("Không thể gửi tin nhắn trống.")
            return
        if not self.current_user:
            self.messageError.emit("Vui lòng đăng nhập để gửi tin nhắn.")
            return
        if not self.current_channel:
            self.messageError.emit("Vui lòng chọn kênh để gửi tin nhắn.")
            return
        try:
            message = Message(
                id=str(uuid.uuid4()),
                channel_id=self.current_channel.id,
                user_id=self.current_user.id,
                content=message_text.strip(),
                timestamp=datetime.datetime.now(datetime.timezone.utc),
                sender_display_name=self.current_user.display_name
            )
            log_event(f"[CTRL] Created Message object: ID={message.id}, Channel={message.channel_id}")
            save_success = self.local_storage.add_message(message)
            if save_success:
                log_event(f"[CTRL] Message {message.id} saved to local storage.")
                self.new_message_signal.emit(message)
            else:
                log_event(f"[ERROR][CTRL] Failed to save message {message.id} to local storage!")
                self.messageError.emit("Lỗi lưu tin nhắn cục bộ.")
                return
            if self.is_online and self.p2p_service:
                asyncio.create_task(self._broadcast_message_p2p(message), name=f"BroadcastMsg_{message.id}")
            else: log_event(f"[CTRL] Skipping P2P broadcast for message {message.id}: Offline or P2P unavailable.")
            if self.is_online and self.sync_service:
                 asyncio.create_task(self.sync_service.backup_message_to_server(message), name=f"BackupMsg_{message.id}")
            else: log_event(f"[CTRL] Skipping server backup for message {message.id}: Offline or Sync unavailable.")
        except Exception as e:
            error_msg = f"Lỗi không mong muốn khi gửi tin nhắn: {str(e)}"
            log_event(f"[ERROR][CTRL] {error_msg}", exc_info=True)
            self.messageError.emit(error_msg)

    async def _broadcast_message_p2p(self, message: Message):
        if not self.p2p_service: return
        log_event(f"[CTRL][ASYNC] Broadcasting message {message.id} via P2P...")
        try:
            payload = p2p_proto.create_chat_payload(
                sender_id=message.user_id,
                channel_id=message.channel_id,
                content=message.content,
                timestamp_iso=message.timestamp.isoformat()
            )
            p2p_message = p2p_proto.create_message(p2p_proto.MSG_TYPE_CHAT_MESSAGE, payload)
            await self.p2p_service.broadcast_message(p2p_message)
            log_event(f"[CTRL] Message {message.id} broadcast via P2P initiated.")
        except Exception as e:
            log_event(f"[ERROR][CTRL] Failed to broadcast P2P message {message.id}: {e}", exc_info=True)

    def _handle_p2p_message(self, peer_addr: Tuple[str, int], message_dict: Dict[str, Any]):
        msg_type = message_dict.get("type")
        payload = message_dict.get("payload")
        peer_ip, peer_port = peer_addr
        log_event(f"[CTRL] Received P2P message type '{msg_type}' from {peer_ip}:{peer_port}")
        try:
            if self.livestream_service and msg_type in [
                p2p_proto.MSG_TYPE_LIVESTREAM_START,
                p2p_proto.MSG_TYPE_LIVESTREAM_END,
                p2p_proto.MSG_TYPE_VIDEO_FRAME
            ]:
                self.livestream_service.handle_incoming_p2p_livestream_message(peer_addr, message_dict)
                return
            if msg_type == p2p_proto.MSG_TYPE_CHAT_MESSAGE:
                if not payload:
                    log_event(f"[WARN][CTRL] Received chat message from {peer_ip}:{peer_port} with empty payload.")
                    return
                channel_id = payload.get("channel_id")
                if self.current_channel and channel_id == self.current_channel.id:
                    sender_id = payload.get("sender_id")
                    content = payload.get("content")
                    timestamp_iso = payload.get("timestamp_iso")
                    sender_name = payload.get("sender_name")
                    if not sender_id or content is None:
                         log_event(f"[WARN][CTRL] Invalid chat message payload from {peer_ip}:{peer_port}: Missing sender_id or content.")
                         return
                    timestamp = datetime.datetime.now(datetime.timezone.utc)
                    if timestamp_iso:
                        try: timestamp = datetime.datetime.fromisoformat(timestamp_iso.replace('Z', '+00:00'))
                        except ValueError: log_event(f"[WARN][CTRL] Invalid timestamp format from {peer_ip}:{peer_port}: {timestamp_iso}")
                    if not sender_name:
                         sender_name = self._get_user_display_name_from_cache_or_fallback(sender_id)
                    msg = Message(
                        id=str(uuid.uuid4()),
                        channel_id=channel_id,
                        user_id=sender_id,
                        content=content,
                        timestamp=timestamp,
                        sender_display_name=sender_name
                    )
                    log_event(f"[CTRL] Processing received chat message {msg.id} for channel {channel_id}.")
                    is_host = self.current_channel.owner_id == self.current_user.id if self.current_user else False
                    if is_host:
                        pass
                    self.new_message_signal.emit(msg)
            elif msg_type == p2p_proto.MSG_TYPE_GREETING:
                 user_id = payload.get("user_id")
                 display_name = payload.get("display_name")
                 log_event(f"[CTRL] Received GREETING from {peer_ip}:{peer_port} - User: {user_id}, Name: {display_name}")
            else:
                 log_event(f"[WARN][CTRL] Received unhandled P2P message type '{msg_type}' from {peer_ip}:{peer_port}")
        except Exception as e:
            log_event(f"[ERROR][CTRL] Error handling P2P message from {peer_ip}:{peer_port}. Type: {msg_type}. Error: {e}", exc_info=True)

    def _get_user_display_name_from_cache_or_fallback(self, user_id: Optional[str]) -> str:
         log_event(f"[DISPLAY_NAME_HELPER] Called for user_id: {user_id}")
         if not user_id: return "Unknown User"
         log_event(f"[DISPLAY_NAME_HELPER] Attempting to find peer via PeerManager for user_id: {user_id}")
         peer = self.peer_manager.find_peer_by_user_id(user_id)
         if peer and hasattr(peer, 'display_name') and peer.display_name:
             log_event(f"Tìm thấy tên cho: {user_id}")
             return peer.display_name
         log_event(f"Không tìm thấy tên cho: {user_id}")
         return f"User_{user_id[:6]}"

    @Slot()
    def _check_network_status(self):
        try:
            has_active_writers = bool(self.p2p_service.get_connected_peers_addresses())
            is_listening = self.p2p_service.is_listening()
            current_status = is_listening or has_active_writers
            if current_status != self.is_online:
                self.is_online = current_status
                status_text = "Trực tuyến" if self.is_online else "Ngoại tuyến"
                log_event(f"[CTRL] Network status changed: {status_text} (Listening: {is_listening}, ActiveWriters: {has_active_writers})")
                self.networkStatusChanged.emit(self.is_online)
                self.connection_status_signal.emit(status_text)
                if self.is_online and self.current_user:
                     log_event("[CTRL] Reconnected to network. Triggering data refresh...")
                     self._schedule_peer_refresh()
                     self.refresh_channels()
                     if self.current_channel:
                          log_event("[CTRL] Reconnected: Re-fetching current channel data...")
                          asyncio.create_task(self.fetch_channel_history_and_peers(), name=f"RefetchOnReconnect_{self.current_channel.id}")
        except Exception as e:
            log_event(f"[ERROR][CTRL] Error checking network status: {e}", exc_info=True)
            if self.is_online:
                self.is_online = False
                self.networkStatusChanged.emit(self.is_online)
                self.connection_status_signal.emit("Lỗi kết nối")

    def start_network_check(self):
        log_event("[CTRL] Starting periodic network status check.")
        if not self.network_check_timer.isActive():
            self._check_network_status()
            self.network_check_timer.start()

    def stop_network_check(self):
        log_event("[CTRL] Stopping periodic network status check.")
        self.network_check_timer.stop()

    def close(self):
        log_event("[CTRL] Closing AppController resources...")
        self.stop_network_check()
        self.peer_update_timer.stop()
        log_event("[CTRL] AppController state cleared. P2P cleanup handled by main exit.")

    @Slot(str)
    def handle_status_change_request(self, new_status: str):
        if not self.current_user or not self.current_user.id:
            log_event("[WARN][CTRL] Status change requested but no current user.")
            return
        status_to_set_db = new_status.lower()
        valid_db_statuses = ["online", "offline", "invisible", "away"]
        if status_to_set_db not in valid_db_statuses:
            log_event(f"[WARN][CTRL] Invalid status value received from UI for DB: '{status_to_set_db}' (original: '{new_status}')")
            return
        log_event(f"[CTRL] User {self.current_user.id} requested status change to '{new_status}' (DB value: '{status_to_set_db}')")
        self.status_update_signal.emit(f"Đang cập nhật trạng thái thành {new_status}...")
        async def _update_status_async():
            success = await api_db.update_user_status(self.current_user.id, status_to_set_db)
            if success:
                self.status_update_signal.emit(f"Trạng thái đã cập nhật thành {new_status}.")
                log_event(f"[CTRL] Status for user {self.current_user.id} updated to '{status_to_set_db}' in DB.")
                if self.current_channel:
                    await self.fetch_channel_history_and_peers()
            else:
                self.status_update_signal.emit(f"Lỗi cập nhật trạng thái.")
                log_event(f"[ERROR][CTRL] Failed to update status for user {self.current_user.id} to '{status_to_set_db}' in DB.")
        asyncio.create_task(_update_status_async(), name=f"UpdateUserStatus_{self.current_user.id}")

    @Slot()
    def handle_request_start_livestream(self):
        log_event(f"[CTRL][LIVESTREAM] Slot handle_request_start_livestream ĐƯỢC GỌI.") # Log kiểm tra
        if not self.livestream_service:
            log_event("[ERROR][CTRL][LIVESTREAM] LivestreamService not initialized. Cannot start stream.")
            self.status_update_signal.emit("Lỗi: Dịch vụ Livestream chưa sẵn sàng.")
            return
        if self.livestream_service.is_hosting or self.livestream_service.is_viewing:
            log_event("[WARN][CTRL][LIVESTREAM] Already hosting or viewing a stream.")
            self.status_update_signal.emit("Bạn đang trong một stream khác hoặc đang host.")
            return
            
        if self.current_channel and self.current_user:
            log_event(f"[CTRL][LIVESTREAM] User {self.current_user.id} requests to start livestream in channel {self.current_channel.id}")
            
            if self.livestream_host_window and self.livestream_host_window.isVisible():
                log_event("[WARN][CTRL][LIVESTREAM] Cửa sổ host cũ đang hiển thị, sẽ đóng lại.")
                self.livestream_host_window.close()

            self.livestream_host_window = LivestreamHostWindow(self.livestream_service.current_display_name, self.main_window)
            
            try:
                self.livestream_service.host_preview_frame.disconnect(self.livestream_host_window.update_preview_frame)
            except RuntimeError:
                pass 
            self.livestream_service.host_preview_frame.connect(self.livestream_host_window.update_preview_frame)
            
            try:
                self.livestream_host_window.stop_livestream_requested.disconnect(self.livestream_service.stop_hosting_livestream)
            except RuntimeError:
                pass
            self.livestream_host_window.stop_livestream_requested.connect(self.livestream_service.stop_hosting_livestream)
            
            self.livestream_service.start_hosting_livestream()
            self.livestream_host_window.exec() 
            
            log_event("[CTRL][LIVESTREAM] LivestreamHostWindow closed.")
            if self.livestream_service.is_hosting:
                 log_event("[CTRL][LIVESTREAM] Stream was still active after host window closed. Stopping explicitly.")
                 self.livestream_service.stop_hosting_livestream(notify_peers=True)
            self.livestream_host_window = None
        else:
            log_event("[WARN][CTRL][LIVESTREAM] Cannot start livestream: No current channel or user selected.")
            self.status_update_signal.emit("Vui lòng chọn kênh để bắt đầu livestream.")

    @Slot(str, str)
    def handle_request_view_livestream(self, streamer_id: str, streamer_name: str):
        log_event(f"[CTRL][LIVESTREAM] Slot handle_request_view_livestream ĐƯỢC GỌI cho streamer: {streamer_name} ({streamer_id}).") # Log kiểm tra
        if not self.livestream_service:
            log_event("[ERROR][CTRL][LIVESTREAM] LivestreamService not initialized. Cannot view stream.")
            self.status_update_signal.emit("Lỗi: Dịch vụ Livestream chưa sẵn sàng.")
            return
        if self.livestream_service.is_hosting:
            log_event("[WARN][CTRL][LIVESTREAM] Cannot view stream while hosting.")
            self.status_update_signal.emit("Không thể xem stream khi đang host.")
            return
        if self.livestream_service.is_viewing and self.livestream_service.active_streamer_id == streamer_id:
            if self.livestream_viewer_window and not self.livestream_viewer_window.isHidden():
                self.livestream_viewer_window.raise_()
                self.livestream_viewer_window.activateWindow()
                log_event(f"[CTRL][LIVESTREAM] Already viewing stream from {streamer_name}. Window raised.")
            return

        log_event(f"[CTRL][LIVESTREAM] User {self.current_user.id if self.current_user else 'Unknown'} requests to view livestream from {streamer_name} ({streamer_id})")
        if self.livestream_service.start_viewing_livestream(streamer_id, streamer_name):
            if self.livestream_viewer_window and self.livestream_viewer_window.isVisible():
                log_event("[WARN][CTRL][LIVESTREAM] Cửa sổ viewer cũ đang hiển thị, sẽ đóng lại.")
                self.livestream_viewer_window.close()
            
            self.livestream_viewer_window = LivestreamViewerWindow(streamer_name, self.main_window)
            
            try:
                self.livestream_service.viewer_new_frame.disconnect(self.livestream_viewer_window.update_viewer_frame)
            except RuntimeError:
                pass
            self.livestream_service.viewer_new_frame.connect(self.livestream_viewer_window.update_viewer_frame)
            
            try:
                self.livestream_viewer_window.stop_viewing_requested.disconnect(self.livestream_service.stop_viewing_livestream)
            except RuntimeError:
                pass
            self.livestream_viewer_window.stop_viewing_requested.connect(self.livestream_service.stop_viewing_livestream)
            
            self.livestream_viewer_window.exec()
            log_event(f"[CTRL][LIVESTREAM] LivestreamViewerWindow for {streamer_name} closed.")
            if self.livestream_service.is_viewing and self.livestream_service.active_streamer_id == streamer_id:
                 log_event(f"[CTRL][LIVESTREAM] Still in viewing state for {streamer_name} after window closed. Stopping explicitly.")
                 self.livestream_service.stop_viewing_livestream()
            self.livestream_viewer_window = None
        else:
            log_event(f"[WARN][CTRL][LIVESTREAM] start_viewing_livestream for {streamer_name} returned False.")
            self.status_update_signal.emit(f"Không thể xem stream của {streamer_name}.")

    @Slot(str, str)
    def _on_livestream_started_globally(self, streamer_id: str, streamer_name: str):
        log_event(f"[CTRL][LIVESTREAM] Livestream started globally by {streamer_name} ({streamer_id}). Updating ChatPage UI.")
        self.livestream_status_changed.emit(True, streamer_id, streamer_name)

    @Slot(str)
    def _on_livestream_ended_globally(self, streamer_id: str):
        log_event(f"[CTRL][LIVESTREAM] Livestream ended globally by streamer {streamer_id}. Updating ChatPage UI.")
        self.livestream_status_changed.emit(False, streamer_id, "")
        if self.livestream_viewer_window and self.livestream_service and self.livestream_service.active_streamer_id == streamer_id:
            log_event(f"[CTRL][LIVESTREAM] Closing viewer window as stream {streamer_id} ended.")
            self.livestream_viewer_window.close()
            self.livestream_viewer_window = None