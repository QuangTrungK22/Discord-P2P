# src/p2p/p2p_service.py
import asyncio
from typing import Dict, Callable, Optional, Tuple, Set, Any, List # Thêm List
from . import protocol # Import protocol đã sửa
from src.core.peer_manager import PeerManager # <<< Import PeerManager
from src.utils.logger import log_event # <<< Sử dụng log_event
from src.p2p import protocol as p2p_proto
# ...existing code...
class P2PService:
    """
    Quản lý toàn bộ hoạt động P2P: lắng nghe kết nối đến,
    kết nối đi đến các peer, gửi và nhận dữ liệu.
    """
    # >>> SỬA ĐỔI __INIT__ ĐỂ NHẬN PEER_MANAGER <<<
    def __init__(self, peer_manager: PeerManager, message_callback: Callable[[Tuple[str, int], Dict[str, Any]], None]):
        """
        Khởi tạo P2P Service.
        Args:
            peer_manager: Instance của PeerManager để tương tác.
            message_callback: Hàm sẽ được gọi khi nhận được message P2P hợp lệ.
                              Callback nhận (peer_address_tuple, message_dict).
        """
        self.peer_manager = peer_manager # <<< Lưu trữ peer_manager
        self._message_callback = message_callback
        self._server: Optional[asyncio.AbstractServer] = None
        self._listen_host: Optional[str] = None
        self._listen_port: Optional[int] = None
        # Lưu các kết nối đang hoạt động: key=peer_address_tuple (ip, port), value=StreamWriter
        self._active_writers: Dict[Tuple[str, int], asyncio.StreamWriter] = {}
        self._active_listeners: Set[asyncio.Task] = set() # Lưu các task lắng nghe
        self._lock = asyncio.Lock() # Dùng lock của asyncio vì môi trường là async
        self.host = '0.0.0.0' # <<< Thêm thuộc tính host mặc định
        self.port = 65432   # <<< Thêm thuộc tính port mặc định
        log_event("[P2P_SERVICE] Initialized.")

    def is_listening(self) -> bool:
         """Kiểm tra xem server có đang lắng nghe không."""
         return self._server is not None and self._server.is_serving()

    def get_listening_port(self) -> Optional[int]:
         """Trả về cổng đang lắng nghe."""
         return self._listen_port

    def get_connected_peers_addresses(self) -> Set[Tuple[str, int]]:
        """Trả về tập hợp các địa chỉ (ip, port) đang có kết nối P2P."""
        # Cần lock để đảm bảo an toàn khi đọc từ nhiều coroutine
        # Tuy nhiên, tạo set từ keys thường là atomic, nên có thể bỏ lock nếu chỉ đọc keys
        # async with self._lock: # Cẩn thận hơn thì dùng lock
        return set(self._active_writers.keys())

    async def start_server(self, host: Optional[str] = None, port: Optional[int] = None) -> Tuple[Optional[str], Optional[int]]:
        """
        Bắt đầu lắng nghe kết nối P2P đến.
        Sử dụng host/port được cung cấp hoặc giá trị mặc định của instance.
        Args:
            host: Địa chỉ IP để lắng nghe (ghi đè giá trị mặc định).
            port: Cổng để lắng nghe (0 để tự chọn, ghi đè giá trị mặc định).
        Returns:
            Tuple (host, port) thực tế đang lắng nghe, hoặc (None, None) nếu lỗi.
        """
        # Sử dụng giá trị mặc định nếu không được cung cấp
        listen_host = host if host is not None else self.host
        listen_port = port if port is not None else self.port

        if self.is_listening():
            log_event(f"[P2P_SERVICE] Server already listening on {self._listen_host}:{self._listen_port}")
            return self._listen_host, self._listen_port

        try:
            log_event(f"[P2P_SERVICE] Attempting to start server on {listen_host}:{listen_port}...")
            self._server = await asyncio.start_server(
                self._handle_incoming_connection, # Hàm xử lý kết nối đến
                listen_host,
                listen_port
            )
            # Lấy địa chỉ và cổng thực tế đang lắng nghe
            actual_addr = self._server.sockets[0].getsockname()
            self._listen_host, self._listen_port = actual_addr[0], actual_addr[1]
            # Cập nhật lại host/port của instance nếu dùng port 0
            self.host = self._listen_host
            self.port = self._listen_port
            log_event(f"[P2P_SERVICE] Server started successfully! Listening on {self._listen_host}:{self._listen_port}")
            return self._listen_host, self._listen_port
        except OSError as e:
            log_event(f"[ERROR][P2P_SERVICE] Failed to start server on {listen_host}:{listen_port}. OSError: {e}", exc_info=True)
            self._server = None
            return None, None
        except Exception as e:
            log_event(f"[ERROR][P2P_SERVICE] Unexpected error starting server: {e}", exc_info=True)
            self._server = None
            return None, None

    async def stop_server(self):
        """Dừng server lắng nghe và đóng tất cả kết nối P2P."""
        log_event("[P2P_SERVICE] Stopping P2P service...")
        # Đóng server lắng nghe
        if self.is_listening() and self._server: # Kiểm tra self._server không phải None
            try:
                self._server.close()
                await self._server.wait_closed()
                log_event("[P2P_SERVICE] Listening server stopped.")
            except Exception as e:
                log_event(f"[ERROR][P2P_SERVICE] Error closing server: {e}", exc_info=True)
        self._server = None
        self._listen_host = None
        self._listen_port = None

        # Hủy các task lắng nghe đang chạy
        cancelled_listeners = []
        for task in list(self._active_listeners): # Duyệt trên bản sao
             if not task.done():
                 task.cancel()
                 cancelled_listeners.append(task)
        if cancelled_listeners:
             log_event(f"[P2P_SERVICE] Cancelling {len(cancelled_listeners)} active listener tasks...")
             await asyncio.gather(*cancelled_listeners, return_exceptions=True) # Đợi các task kết thúc (hoặc bị hủy)
             log_event("[P2P_SERVICE] Listener tasks cancelled.")
        self._active_listeners.clear()

        # Đóng các writer đang hoạt động
        writers_to_close: List[asyncio.StreamWriter] = []
        async with self._lock:
             if self._active_writers:
                 log_event(f"[P2P_SERVICE] Closing {len(self._active_writers)} active connections...")
                 writers_to_close = list(self._active_writers.values()) # Tạo bản sao list writer
                 self._active_writers.clear() # Xóa dict gốc

        closed_count = 0
        close_tasks = []
        for writer in writers_to_close:
             if not writer.is_closing():
                 close_tasks.append(asyncio.create_task(self._close_writer_safe(writer)))

        if close_tasks:
             results = await asyncio.gather(*close_tasks, return_exceptions=True)
             for result in results:
                  if result is True: # _close_writer_safe trả về True nếu thành công
                       closed_count += 1
                  elif isinstance(result, Exception):
                       log_event(f"[ERROR][P2P_SERVICE] Error closing writer during shutdown: {result}", exc_info=True)
             log_event(f"[P2P_SERVICE] Closed {closed_count}/{len(writers_to_close)} connections.")

        log_event("[P2P_SERVICE] P2P service stopped.")

    async def _close_writer_safe(self, writer: asyncio.StreamWriter) -> bool:
        """Đóng một StreamWriter một cách an toàn."""
        peer_addr_str = "unknown peer"
        try:
            peer_addr = writer.get_extra_info('peername')
            peer_addr_str = f"{peer_addr[0]}:{peer_addr[1]}" if peer_addr else "unknown peer"
            if not writer.is_closing():
                writer.close()
                await writer.wait_closed()
                # log_event(f"[P2P_SERVICE] Closed connection to {peer_addr_str}") # Log nhiều quá
                return True
            else:
                # log_event(f"[P2P_SERVICE] Writer for {peer_addr_str} was already closing.")
                return True # Vẫn coi là thành công nếu đã đóng
        except ConnectionResetError:
             log_event(f"[WARN][P2P_SERVICE] Connection reset while closing writer for {peer_addr_str}.")
             return True # Vẫn coi là đã xử lý xong
        except Exception as e:
            log_event(f"[ERROR][P2P_SERVICE] Error closing writer for {peer_addr_str}: {e}", exc_info=True)
            return False


    async def connect_to_peer(self, host: str, port: int) -> bool:
        """Kết nối chủ động đến một peer."""
        peer_addr = (host, port)
        # Không kết nối đến chính mình
        if host == self.host and port == self.port:
             log_event(f"[P2P_SERVICE] Attempted to connect to self ({peer_addr}). Skipping.")
             return False

        async with self._lock:
            if peer_addr in self._active_writers:
                 writer = self._active_writers[peer_addr]
                 if not writer.is_closing():
                      # log_event(f"[P2P_SERVICE] Already connected to {peer_addr}. Skipping.")
                      return True # Đã kết nối, trả về True
                 else:
                      # Writer đang đóng, loại bỏ nó để thử kết nối lại
                      log_event(f"[P2P_SERVICE] Found closing writer for {peer_addr}. Removing before reconnect.")
                      self._active_writers.pop(peer_addr, None)

        log_event(f"[P2P_SERVICE] Attempting to connect to {peer_addr}...")
        reader = None
        writer = None
        try:
            # Đặt timeout cho việc kết nối
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port), timeout=5.0 # Giảm timeout xuống 5s
            )
            log_event(f"[P2P_SERVICE] Connection established to {peer_addr}.")
            # Đăng ký kết nối và bắt đầu lắng nghe
            await self._register_connection(reader, writer, peer_addr)

            # Gửi message GREETING ngay sau khi kết nối thành công
            # Cần lấy thông tin user hiện tại từ PeerManager hoặc AppController
            # Tạm thời dùng ID giả định
            my_user_id = self.peer_manager._get_current_user_id() # Sử dụng callback đã có # Cần hàm này trong PeerManager
            my_display_name = "Unknown User" # Cần lấy tên hiển thị
            if my_user_id:
                 greeting_payload = p2p_proto.create_greeting_payload(my_user_id, my_display_name)
                 greeting_msg = p2p_proto.create_message(p2p_proto.MSG_TYPE_GREETING, greeting_payload)
                 await self._send_message_to_writer(writer, greeting_msg, peer_addr) # Gửi qua writer mới
            else:
                 log_event("[WARN][P2P_SERVICE] Cannot send greeting: My user ID not available.")

            return True
        except asyncio.TimeoutError:
             log_event(f"[ERROR][P2P_SERVICE] Connection attempt to {peer_addr} timed out.")
             return False
        except ConnectionRefusedError:
            log_event(f"[ERROR][P2P_SERVICE] Connection refused by {peer_addr}.")
            return False
        except OSError as e:
             # Bắt các lỗi OS khác như "Network is unreachable"
             log_event(f"[ERROR][P2P_SERVICE] OS Error connecting to {peer_addr}: {e}")
             return False
        except Exception as e:
            log_event(f"[ERROR][P2P_SERVICE] Unexpected error connecting to {peer_addr}: {e}", exc_info=True)
            return False
        finally:
             # Đảm bảo đóng writer nếu kết nối thành công nhưng đăng ký thất bại
             # Hoặc nếu có lỗi sau khi kết nối nhưng trước khi đăng ký xong
             if writer and peer_addr not in self._active_writers:
                  log_event(f"[P2P_SERVICE] Closing writer for {peer_addr} due to registration failure or early error.")
                  await self._close_writer_safe(writer)


    async def disconnect_from_peer(self, host: str, port: int):
        """Ngắt kết nối chủ động đến một peer."""
        peer_addr = (host, port)
        writer = None
        async with self._lock:
             if peer_addr in self._active_writers:
                 writer = self._active_writers.pop(peer_addr) # Lấy và xóa khỏi dict
                 log_event(f"[P2P_SERVICE] Removing connection entry for {peer_addr}.")
             # else: Không có kết nối để ngắt

        if writer:
            log_event(f"[P2P_SERVICE] Closing connection to {peer_addr}...")
            await self._close_writer_safe(writer)
            log_event(f"[P2P_SERVICE] Connection to {peer_addr} closed.")


    async def send_message(self, target_host: str, target_port: int, message_dict: Dict[str, Any]) -> bool:
        """Gửi message đến một peer cụ thể. Sẽ thử kết nối nếu chưa có."""
        peer_addr = (target_host, target_port)
        writer = None
        async with self._lock:
             writer = self._active_writers.get(peer_addr)
             if writer and writer.is_closing():
                  log_event(f"[WARN][P2P_SERVICE] Attempted to get writer for {peer_addr}, but it's closing. Removing.")
                  self._active_writers.pop(peer_addr, None)
                  writer = None # Đặt lại là None để thử kết nối lại

        if writer:
            # Đã có kết nối, gửi trực tiếp
            return await self._send_message_to_writer(writer, message_dict, peer_addr)
        else:
            # Chưa có kết nối, thử kết nối lại
            log_event(f"[P2P_SERVICE] No active connection to {peer_addr}. Attempting to connect before sending...")
            if await self.connect_to_peer(target_host, target_port):
                 # Đợi một chút để đảm bảo kết nối ổn định và writer được đăng ký
                 await asyncio.sleep(0.1)
                 async with self._lock:
                      writer = self._active_writers.get(peer_addr) # Thử lấy lại writer
                 if writer and not writer.is_closing():
                      log_event(f"[P2P_SERVICE] Reconnected to {peer_addr}. Retrying send.")
                      return await self._send_message_to_writer(writer, message_dict, peer_addr)
                 else:
                      log_event(f"[ERROR][P2P_SERVICE] Failed to get writer after successful reconnect to {peer_addr}.")
                      return False
            else:
                 log_event(f"[ERROR][P2P_SERVICE] Failed to reconnect to {peer_addr} for sending.")
                 return False

    async def broadcast_message(self, message_dict: Dict[str, Any], exclude_addr: Optional[Tuple[str, int]] = None):
        """Gửi message đến tất cả các peer đang kết nối (trừ exclude_addr nếu có)."""
        current_writers_map: Dict[Tuple[str, int], asyncio.StreamWriter] = {}
        async with self._lock:
             # Lấy bản sao của dict writers để tránh lỗi thay đổi khi đang duyệt
             current_writers_map = self._active_writers.copy()

        if not current_writers_map:
             # log_event("[P2P_SERVICE] No active peers to broadcast to.") # Log này hơi thừa
             return

        target_peers = list(current_writers_map.items())
        if exclude_addr:
             target_peers = [(addr, writer) for addr, writer in target_peers if addr != exclude_addr]

        if not target_peers:
             # log_event(f"[P2P_SERVICE] No peers to broadcast to after excluding {exclude_addr}.")
             return

        msg_type = message_dict.get('type', 'unknown')
        log_event(f"[P2P_SERVICE] Broadcasting message type '{msg_type}' to {len(target_peers)} peers...")
        tasks = []
        for addr, writer in target_peers:
             # Tạo task gửi cho mỗi peer, truyền cả addr để log lỗi nếu cần
             tasks.append(asyncio.create_task(self._send_message_to_writer(writer, message_dict, addr), name=f"Send_{msg_type}_To_{addr[0]}:{addr[1]}"))

        # Đợi tất cả các task gửi hoàn thành
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Kiểm tra lỗi và log
        failed_sends = 0
        for i, result in enumerate(results):
              addr, _ = target_peers[i] # Lấy địa chỉ tương ứng
              if isinstance(result, Exception):
                   log_event(f"[ERROR][P2P_SERVICE] Broadcast to {addr[0]}:{addr[1]} failed with exception: {result}", exc_info=True)
                   failed_sends += 1
              elif result is False: # _send_message_to_writer trả về bool
                   log_event(f"[WARN][P2P_SERVICE] Broadcast to {addr[0]}:{addr[1]} possibly failed (send returned False).")
                   failed_sends += 1
        if failed_sends > 0:
             log_event(f"[WARN][P2P_SERVICE] Broadcast completed with {failed_sends} potential failures.")
        # else: log_event("[P2P_SERVICE] Broadcast completed successfully.") # Log này hơi thừa


    # --- Các hàm xử lý nội bộ ---

    async def _handle_incoming_connection(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """Xử lý khi có một peer mới kết nối đến server của chúng ta."""
        peer_addr = writer.get_extra_info('peername')
        if not peer_addr or not isinstance(peer_addr, tuple):
             log_event("[ERROR][P2P_SERVICE] Could not get valid peer address for incoming connection.")
             await self._close_writer_safe(writer)
             return

        log_event(f"[P2P_SERVICE] Incoming connection from {peer_addr[0]}:{peer_addr[1]}")
        await self._register_connection(reader, writer, peer_addr)

    async def _register_connection(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter, peer_addr: Tuple[str, int]):
        """Đăng ký một kết nối mới (đến hoặc đi) và bắt đầu lắng nghe."""
        log_event(f"[P2P_SERVICE] Registering connection for {peer_addr[0]}:{peer_addr[1]}")
        async with self._lock:
             # Đóng và xóa kết nối cũ nếu có từ cùng địa chỉ
             existing_writer = self._active_writers.pop(peer_addr, None)
             if existing_writer and not existing_writer.is_closing():
                  log_event(f"[WARN][P2P_SERVICE] Closing existing active writer for {peer_addr} before registering new one.")
                  # Không await ở đây để tránh deadlock nếu _close_writer_safe cần lock
                  asyncio.create_task(self._close_writer_safe(existing_writer))

             # Thêm writer mới vào danh sách
             self._active_writers[peer_addr] = writer

        # Tạo task riêng để lắng nghe dữ liệu từ kết nối này
        listener_task_name = f"Listener_From_{peer_addr[0]}:{peer_addr[1]}"
        listener_task = asyncio.create_task(self._listen_to_writer(reader, writer, peer_addr), name=listener_task_name)
        self._active_listeners.add(listener_task)
        # Xóa task khỏi set khi nó hoàn thành (bằng callback hoặc cách khác)
        listener_task.add_done_callback(lambda t: self._active_listeners.discard(t))
        log_event(f"[P2P_SERVICE] Started listener task: {listener_task_name}")


    async def _listen_to_writer(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter, peer_addr: Tuple[str, int]):
        """Vòng lặp lắng nghe và xử lý dữ liệu từ một kết nối cụ thể."""
        peer_addr_str = f"{peer_addr[0]}:{peer_addr[1]}"
        log_event(f"[P2P_LISTENER] Started listening to {peer_addr_str}")
        buffer = b"" # Buffer để xử lý dữ liệu nhận được không đầy đủ
        while True: # Lặp vô hạn cho đến khi có lỗi hoặc kết nối đóng
            try:
                # Đọc dữ liệu, read(n) sẽ đợi đến khi có đủ n bytes hoặc EOF
                # Sử dụng read(4096) để đọc một chunk lớn
                chunk = await reader.read(4096)
                if not chunk: # Kết nối đóng bởi peer (EOF)
                    log_event(f"[P2P_LISTENER] Connection closed by {peer_addr_str} (EOF).")
                    break

                buffer += chunk
                # Xử lý tất cả các message hoàn chỉnh trong buffer
                while b'\n' in buffer:
                    line, buffer = buffer.split(b'\n', 1) # Tách message đầu tiên
                    if line: # Bỏ qua dòng trống nếu có
                        message_dict = protocol.decode_message(line)
                        if message_dict:
                            # Gọi callback đã đăng ký để xử lý message
                            if self._message_callback:
                                try:
                                    # Gọi trực tiếp vì môi trường đã là async
                                    # (Hoặc dùng asyncio.create_task nếu callback có thể block lâu)
                                    self._message_callback(peer_addr, message_dict)
                                except Exception as cb_e:
                                    log_event(f"[ERROR][P2P_LISTENER] Error in message callback for {peer_addr_str}: {cb_e}", exc_info=True)
                            else:
                                 log_event(f"[WARN][P2P_LISTENER] No message callback set for message from {peer_addr_str}")
                        # else: Message không hợp lệ, decode_message đã log lỗi
                    # Tiếp tục vòng lặp while b'\n' in buffer để xử lý message tiếp theo nếu có

            except asyncio.IncompleteReadError:
                log_event(f"[P2P_LISTENER] Connection to {peer_addr_str} closed unexpectedly (IncompleteReadError).")
                break
            except ConnectionResetError:
                log_event(f"[P2P_LISTENER] Connection reset by {peer_addr_str}.")
                break
            except asyncio.CancelledError:
                log_event(f"[P2P_LISTENER] Listener task for {peer_addr_str} cancelled.")
                raise # Ném lại CancelledError để gather biết task bị hủy
            except Exception as e:
                log_event(f"[ERROR][P2P_LISTENER] Unexpected error listening to {peer_addr_str}: {e}", exc_info=True)
                break # Thoát vòng lặp nếu có lỗi nghiêm trọng

        # --- Dọn dẹp sau khi vòng lặp kết thúc ---
        log_event(f"[P2P_LISTENER] Stopping listener for {peer_addr_str}")
        # Xóa writer khỏi danh sách active nếu nó vẫn còn ở đó
        async with self._lock:
            if self._active_writers.get(peer_addr) is writer:
                 self._active_writers.pop(peer_addr, None)
                 log_event(f"[P2P_LISTENER] Removed writer for {peer_addr_str} from active list.")

        # Đóng writer nếu chưa đóng
        await self._close_writer_safe(writer)


    async def _send_message_to_writer(self, writer: asyncio.StreamWriter, message_dict: Dict[str, Any], peer_addr: Tuple[str, int]) -> bool:
        """Hàm nội bộ để gửi message qua một writer cụ thể, đảm bảo có '\n'."""
        peer_addr_str = f"{peer_addr[0]}:{peer_addr[1]}"
        message_bytes = protocol.encode_message(message_dict) # encode_message đã thêm '\n'
        if not message_bytes:
            log_event(f"[ERROR][P2P_SERVICE] Failed to encode message for {peer_addr_str}. Msg: {message_dict.get('type', 'unknown')}")
            return False

        if writer.is_closing():
             log_event(f"[WARN][P2P_SERVICE] Attempted to send message to closing writer for {peer_addr_str}.")
             # Xóa writer lỗi khỏi danh sách active
             async with self._lock:
                  if self._active_writers.get(peer_addr) is writer:
                       self._active_writers.pop(peer_addr, None)
             return False

        try:
            # log_event(f"[P2P_SERVICE] Sending {len(message_bytes)} bytes (type: {message_dict.get('type')}) to {peer_addr_str}") # Log chi tiết nếu cần debug
            writer.write(message_bytes)
            await writer.drain() # Đảm bảo dữ liệu được gửi đi hết khỏi buffer hệ thống
            return True
        except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError) as conn_err:
            log_event(f"[ERROR][P2P_SERVICE] Connection error while sending to {peer_addr_str}: {conn_err}. Closing connection.")
            # Đóng và xóa kết nối lỗi
            # Không gọi disconnect_from_peer ở đây để tránh gọi lại lock
            async with self._lock:
                 if self._active_writers.get(peer_addr) is writer:
                      self._active_writers.pop(peer_addr, None)
            # Đóng writer an toàn
            await self._close_writer_safe(writer)
            return False
        except Exception as e:
            log_event(f"[ERROR][P2P_SERVICE] Unexpected error sending message to {peer_addr_str}: {e}", exc_info=True)
            return False

    # Thêm phương thức listen() nếu chưa có (cần thiết cho main.py)
    async def listen(self):
        """Chạy server P2P và giữ nó hoạt động."""
        if not self.is_listening():
            host, port = await self.start_server()
            if not port:
                log_event("[ERROR][P2P_SERVICE] Failed to start listening in listen() method.")
                return # Không thể chạy nếu không start được server

        log_event("[P2P_SERVICE] Listener running. Waiting for connections or stop signal...")
        # Giữ cho coroutine này chạy mãi mãi hoặc cho đến khi server bị đóng
        if self._server:
            try:
                # server.serve_forever() không dùng được trực tiếp với asyncio server
                # Thay vào đó, đợi cho đến khi server bị đóng từ bên ngoài (ví dụ: stop_server)
                await self._server.wait_closed()
                log_event("[P2P_SERVICE] Server has been closed.")
            except asyncio.CancelledError:
                 log_event("[P2P_SERVICE] Listener task cancelled.")
            except Exception as e:
                 log_event(f"[ERROR][P2P_SERVICE] Error while waiting for server to close: {e}", exc_info=True)
        else:
             log_event("[WARN][P2P_SERVICE] Server object is None in listen() method after start attempt.")