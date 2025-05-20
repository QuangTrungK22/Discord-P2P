# src/core/livestream_service.py
import asyncio
import cv2 # Thư viện OpenCV cho camera và xử lý ảnh
import base64
import numpy as np # Thư viện NumPy để xử lý mảng
from typing import Optional, Callable
from PySide6.QtCore import Slot
# Đảm bảo import đúng đường dẫn
try:
    from src.p2p.p2p_service import P2PService
    from src.p2p import protocol as p2p_proto
    from src.utils.logger import log_event
except ImportError: # Fallback cho trường hợp chạy trực tiếp hoặc cấu trúc khác
    print("Attempting relative imports for P2P/Utils in livestream_service...")
    from ..p2p.p2p_service import P2PService
    from ..p2p import protocol as p2p_proto
    from ..utils.logger import log_event

from PySide6.QtCore import QObject, Signal, QThread, QTimer
from PySide6.QtGui import QImage, QPixmap, Qt # Thêm Qt

class VideoCaptureThread(QThread):
    new_cv_frame = Signal(object) # Gửi frame OpenCV gốc
    finished_capturing = Signal()
    error_signal = Signal(str) # Thêm signal báo lỗi

    def __init__(self, camera_index=0, parent=None):
        super().__init__(parent)
        self.camera_index = camera_index
        self.cap = None
        self.running = False
        self.fps = 15 # Giới hạn FPS để giảm tải

    def run(self):
        try:
            self.cap = cv2.VideoCapture(self.camera_index)
            if not self.cap.isOpened():
                error_msg = f"Cannot open camera {self.camera_index}"
                log_event(f"[VideoCaptureThread] {error_msg}")
                self.error_signal.emit(error_msg)
                self.finished_capturing.emit()
                return

            self.running = True
            log_event(f"[VideoCaptureThread] Camera {self.camera_index} opened. Capturing at {self.fps} FPS.")

            time_per_frame = 1.0 / self.fps

            while self.running and self.cap.isOpened():
                loop_start_time = cv2.getTickCount()

                ret, frame = self.cap.read()
                if not ret:
                    log_event("[VideoCaptureThread] Failed to grab frame or stream ended.")
                    break # Kết thúc vòng lặp nếu không đọc được frame

                # Chỉ emit nếu frame hợp lệ
                if frame is not None:
                    self.new_cv_frame.emit(frame)
                else:
                    log_event("[VideoCaptureThread] Warning: Grabbed None frame.")
                    # Có thể thêm logic thử lại hoặc dừng hẳn

                # Đảm bảo FPS
                processing_time = (cv2.getTickCount() - loop_start_time) / cv2.getTickFrequency()
                sleep_time = time_per_frame - processing_time
                if sleep_time > 0:
                    self.msleep(int(sleep_time * 1000))

        except Exception as e:
            error_msg = f"Error in VideoCaptureThread: {e}"
            log_event(f"[VideoCaptureThread] {error_msg}", exc_info=True)
            self.error_signal.emit(error_msg) # Gửi lỗi ra ngoài
        finally:
            if self.cap and self.cap.isOpened(): # Chỉ release nếu đã mở
                self.cap.release()
                log_event("[VideoCaptureThread] Camera released.")
            self.finished_capturing.emit()
            log_event("[VideoCaptureThread] Capture thread finished.")

    def stop(self):
        log_event("[VideoCaptureThread] Stop requested.")
        self.running = False

class LivestreamService(QObject):
    host_preview_frame = Signal(QPixmap)
    viewer_new_frame = Signal(QPixmap)
    livestream_started_signal = Signal(str, str) # streamer_id, streamer_name
    livestream_ended_signal = Signal(str)   # streamer_id
    livestream_error_signal = Signal(str) # Signal mới để báo lỗi chung

    def __init__(self, p2p_service: P2PService, current_user_id: str, current_display_name: str, parent=None):
        super().__init__(parent)
        self.p2p_service = p2p_service
        self.current_user_id = current_user_id
        self.current_display_name = current_display_name

        self.is_hosting = False
        self.is_viewing = False
        self.active_streamer_id: Optional[str] = None
        self.active_streamer_name: Optional[str] = None

        self.capture_thread: Optional[VideoCaptureThread] = None
        self.frame_id_counter = 0
        self.jpeg_quality = 75

    def start_hosting_livestream(self, camera_index=0):
        log_event(f"[LivestreamService] Attempting start_hosting_livestream (is_hosting={self.is_hosting})") # Log mới
        if self.is_hosting:
            log_event("[LivestreamService] Already hosting.")
            return
        if self.is_viewing: # Ngăn host khi đang xem
            log_event("[LivestreamService] Cannot host while viewing another stream.")
            self.livestream_error_signal.emit("Không thể host khi đang xem stream khác.")
            return

        self.is_hosting = True
        self.active_streamer_id = self.current_user_id
        self.active_streamer_name = self.current_display_name
        self.frame_id_counter = 0
        log_event(f"[LivestreamService] User {self.current_user_id} starting livestream.")

        # Thông báo cho các peer khác biết stream bắt đầu
        log_event("[LivestreamService] Creating LIVESTREAM_START payload...") # Log mới
        start_payload = p2p_proto.create_livestream_start_payload(self.current_user_id, self.current_display_name)
        start_message = p2p_proto.create_message(p2p_proto.MSG_TYPE_LIVESTREAM_START, start_payload)
        log_event("[LivestreamService] Broadcasting LIVESTREAM_START message...") # Log mới
        asyncio.create_task(self.p2p_service.broadcast_message(start_message))

        # Khởi tạo và chạy thread camera
        log_event("[LivestreamService] Creating VideoCaptureThread...") # Log mới
        self.capture_thread = VideoCaptureThread(camera_index)
        self.capture_thread.new_cv_frame.connect(self._process_and_send_frame)
        self.capture_thread.finished_capturing.connect(self._on_capture_finished)
        self.capture_thread.error_signal.connect(self._on_capture_error) # Kết nối signal lỗi
        log_event("[LivestreamService] Starting VideoCaptureThread...") # Log mới
        self.capture_thread.start()

        # Emit signal báo cho controller/UI biết stream đã bắt đầu (cục bộ)
        log_event("[LivestreamService] Emitting livestream_started_signal...") # Log mới
        self.livestream_started_signal.emit(self.current_user_id, self.current_display_name)

    # **** THAY ĐỔI HÀM NÀY ĐỂ GỬI streamer_id ****
    def _process_and_send_frame(self, cv_frame):
        if not self.is_hosting or cv_frame is None:
            return

        # 1. Hiển thị preview cho host
        try:
            rgb_image = cv2.cvtColor(cv_frame, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb_image.shape
            bytes_per_line = ch * w
            qt_image = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format_RGB888)
            pixmap = QPixmap.fromImage(qt_image)
            self.host_preview_frame.emit(pixmap)
        except Exception as e:
            log_event(f"[LivestreamService][HOST] Error converting frame for host preview: {e}")

        # 2. Nén frame thành JPEG
        try:
            encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), self.jpeg_quality]
            result, encoded_jpeg = cv2.imencode('.jpg', cv_frame, encode_param)
            if not result:
                log_event("[LivestreamService][HOST] Failed to encode frame to JPEG.")
                return

            # 3. Chuyển thành base64
            frame_data_base64 = base64.b64encode(encoded_jpeg).decode('utf-8')

            # 4. Tạo payload và gửi (THÊM streamer_id VÀO ĐÂY)
            self.frame_id_counter += 1
            frame_payload = p2p_proto.create_video_frame_payload(
                streamer_id=self.current_user_id, # **** Thêm streamer_id ****
                frame_data_base64=frame_data_base64,
                frame_id=self.frame_id_counter
            )
            frame_message = p2p_proto.create_message(p2p_proto.MSG_TYPE_VIDEO_FRAME, frame_payload)

            # Gửi bất đồng bộ
            asyncio.create_task(self.p2p_service.broadcast_message(frame_message),
                                name=f"SendVideoFrame_{self.frame_id_counter}")
            # log_event(f"[LivestreamService][HOST] Sent video frame {self.frame_id_counter}") # Log nhiều quá
        except Exception as e:
            log_event(f"[LivestreamService][HOST] Error processing or sending frame: {e}", exc_info=True)

    @Slot(str)
    def _on_capture_error(self, error_message: str):
        """Xử lý khi VideoCaptureThread báo lỗi."""
        log_event(f"[LivestreamService] Capture error received: {error_message}")
        self.livestream_error_signal.emit(f"Lỗi camera: {error_message}")
        if self.is_hosting:
            self.stop_hosting_livestream(notify_peers=True) # Dừng stream nếu có lỗi camera

    def _on_capture_finished(self):
        log_event("[LivestreamService] Video capture thread signaled finished.")
        # Chỉ dừng stream nếu nó đang chạy và do lỗi (không phải do người dùng chủ động dừng)
        # Việc dừng chủ động sẽ gọi stop_hosting_livestream trước, đặt capture_thread=None
        if self.is_hosting and self.capture_thread is not None:
             log_event("[LivestreamService] Capture finished unexpectedly while hosting. Stopping stream.")
             self.stop_hosting_livestream(notify_peers=True)

    def stop_hosting_livestream(self, notify_peers=True):
        log_event(f"[LivestreamService] Attempting stop_hosting_livestream (is_hosting={self.is_hosting})") # Log mới
        if not self.is_hosting:
            return

        log_event(f"[LivestreamService] User {self.current_user_id} stopping livestream.")
        self.is_hosting = False # Đặt cờ trước

        # Dừng thread camera
        if self.capture_thread:
            log_event("[LivestreamService] Stopping capture thread...") # Log mới
            self.capture_thread.stop()
            # Có thể không cần đợi thread kết thúc hoàn toàn
            self.capture_thread = None # Quan trọng: đặt về None sau khi stop
        else:
            log_event("[LivestreamService] Capture thread was already None on stop.") # Log mới

        # Thông báo cho các peer khác
        if notify_peers:
            log_event("[LivestreamService] Broadcasting LIVESTREAM_END message...") # Log mới
            end_payload = p2p_proto.create_livestream_end_payload(self.current_user_id)
            end_message = p2p_proto.create_message(p2p_proto.MSG_TYPE_LIVESTREAM_END, end_payload)
            asyncio.create_task(self.p2p_service.broadcast_message(end_message))

        # Emit signal báo cho controller/UI biết stream đã kết thúc (cục bộ)
        log_event("[LivestreamService] Emitting livestream_ended_signal...") # Log mới
        self.livestream_ended_signal.emit(self.current_user_id)
        # Reset trạng thái streamer
        self.active_streamer_id = None
        self.active_streamer_name = None
        log_event("[LivestreamService] Hosting stopped.") # Log mới

    # **** THAY ĐỔI HÀM NÀY ĐỂ KIỂM TRA ID VÀ THÊM LOGGING ****
    def handle_incoming_p2p_livestream_message(self, peer_addr: tuple, message_dict: dict):
        msg_type = message_dict.get("type")
        payload = message_dict.get("payload", {})
        log_event(f"[LivestreamService][P2P_RECV] Handling msg type '{msg_type}' from {peer_addr}. Payload: {str(payload)[:200]}...") # Log mới

        if msg_type == p2p_proto.MSG_TYPE_LIVESTREAM_START:
            streamer_id = payload.get("streamer_id")
            streamer_name = payload.get("streamer_name", f"User_{streamer_id[:6]}")
            log_event(f"[LivestreamService][P2P_RECV] LIVESTREAM_START processing: streamer_id={streamer_id}, streamer_name={streamer_name}") # Log mới
            if streamer_id and streamer_id != self.current_user_id: # Bỏ qua message của chính mình
                log_event(f"[LivestreamService] Received LIVESTREAM_START from {streamer_name} ({streamer_id})")
                self.active_streamer_id = streamer_id
                self.active_streamer_name = streamer_name
                # Không tự động đặt is_viewing = True ở đây, đợi người dùng chọn xem
                # self.is_viewing = True
                log_event(f"[LivestreamService][P2P_RECV] Emitting livestream_started_signal for {streamer_id}") # Log mới
                self.livestream_started_signal.emit(streamer_id, streamer_name)
            elif streamer_id == self.current_user_id:
                log_event("[LivestreamService][P2P_RECV] Ignored own LIVESTREAM_START message.") # Log mới
            else:
                 log_event("[LivestreamService][P2P_RECV] Invalid LIVESTREAM_START payload (missing streamer_id?).")

        elif msg_type == p2p_proto.MSG_TYPE_LIVESTREAM_END:
            streamer_id = payload.get("streamer_id")
            log_event(f"[LivestreamService][P2P_RECV] LIVESTREAM_END processing: streamer_id={streamer_id}") # Log mới
            if streamer_id and streamer_id == self.active_streamer_id: # Chỉ xử lý nếu đang xem stream này
                log_event(f"[LivestreamService] Received LIVESTREAM_END from {self.active_streamer_name} ({streamer_id})")
                if self.is_viewing: # Chỉ dừng xem nếu đang trong trạng thái xem
                    self.stop_viewing_livestream() # Dùng hàm stop_viewing để reset trạng thái
                else:
                    # Trường hợp chỉ nhận END mà không đang xem (vẫn cần báo UI)
                    self.livestream_ended_signal.emit(streamer_id)
                    self.active_streamer_id = None # Vẫn reset thông tin streamer
                    self.active_streamer_name = None
            elif streamer_id == self.current_user_id:
                 log_event("[LivestreamService][P2P_RECV] Ignored own LIVESTREAM_END message.")
            else:
                 log_event(f"[LivestreamService][P2P_RECV] Received LIVESTREAM_END for inactive/different streamer {streamer_id}. Ignoring.")

        elif msg_type == p2p_proto.MSG_TYPE_VIDEO_FRAME:
            # Lấy streamer_id từ payload (quan trọng)
            streamer_id = payload.get("streamer_id")

            # *** Bỏ qua frame của chính mình ***
            if streamer_id and streamer_id == self.current_user_id:
                # log_event("[LivestreamService][P2P_RECV] Ignored own video frame.") # Có thể log nếu cần debug loopback
                return

            # Log chi tiết hơn
            log_event(f"[LivestreamService][P2P_RECV] Received VIDEO_FRAME from alleged streamer {streamer_id}. is_viewing={self.is_viewing}, viewing_streamer_id={self.active_streamer_id}")

            # Chỉ xử lý nếu đang trong trạng thái xem ĐÚNG stream này
            if self.is_viewing and self.active_streamer_id == streamer_id and payload.get("frame_data"):
                frame_id = payload.get("frame_id", "N/A")
                # log_event(f"[LivestreamService][VIEWER] Processing VIDEO_FRAME (ID: {frame_id}) from {self.active_streamer_id}. Data length: {len(payload.get('frame_data'))}") # Log nhiều quá, bỏ bớt
                try:
                    frame_data_base64 = payload.get("frame_data")
                    # log_event(f"[LivestreamService][VIEWER] Received frame_data (base64) length: {len(frame_data_base64)}") # Log kích thước nếu cần
                    jpg_as_np = base64.b64decode(frame_data_base64)
                    # log_event(f"[LivestreamService][VIEWER] Decoded base64 to JPEG bytes length: {len(jpg_as_np)}") # Log kích thước nếu cần
                    frame = cv2.imdecode(np.frombuffer(jpg_as_np, dtype=np.uint8), cv2.IMREAD_COLOR)
                    if frame is not None:
                        # log_event(f"[LivestreamService][VIEWER] Frame decoded by OpenCV. Shape: {frame.shape}") # Log nếu cần
                        # Chuyển sang QPixmap để hiển thị trên UI của viewer
                        rgb_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                        h, w, ch = rgb_image.shape
                        bytes_per_line = ch * w
                        qt_image = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format_RGB888)
                        pixmap = QPixmap.fromImage(qt_image)
                        if not pixmap.isNull():
                            # log_event(f"[LivestreamService][VIEWER] QPixmap created, emitting viewer_new_frame. Size: {pixmap.size()}") # Log nếu cần
                            self.viewer_new_frame.emit(pixmap)
                            # log_event(f"[LivestreamService][VIEWER] Emitted viewer_new_frame for frame_id {frame_id}") # Log nếu cần
                        else:
                            log_event("[LivestreamService][VIEWER] ERROR: Created QPixmap is Null.")
                    else:
                        log_event("[LivestreamService][VIEWER] ERROR: Failed to decode frame (cv2.imdecode returned None).")
                except base64.binascii.Error as b64e: # Bắt lỗi decode base64 cụ thể
                     log_event(f"[LivestreamService][VIEWER] ERROR decoding base64 for frame {frame_id}: {b64e}")
                except Exception as e:
                    log_event(f"[LivestreamService][VIEWER] ERROR processing received video frame {frame_id}: {e}", exc_info=True)
            elif not self.is_viewing:
                log_event("[LivestreamService][P2P_RECV] Received video frame but not in viewing state. Ignoring.")
            elif self.active_streamer_id != streamer_id:
                log_event(f"[LivestreamService][P2P_RECV] Received video frame from {streamer_id} but currently expecting frames from {self.active_streamer_id}. Ignoring.")
            elif not payload.get("frame_data"):
                log_event("[LivestreamService][P2P_RECV] Received video frame with empty 'frame_data'. Ignoring.")


    # **** THÊM LOGGING VÀO HÀM NÀY ****
    def start_viewing_livestream(self, streamer_id: str, streamer_name: str):
        log_event(f"[LivestreamService][VIEW] Attempting to start viewing stream from {streamer_name} ({streamer_id})") # Log mới
        if self.is_hosting:
            log_event("[LivestreamService][VIEW] Cannot view stream while hosting.")
            self.livestream_error_signal.emit("Không thể xem stream khi đang host.")
            return False
        if self.is_viewing and self.active_streamer_id == streamer_id:
            log_event(f"[LivestreamService][VIEW] Already viewing stream from {streamer_name}.")
            return True
        # Nếu đang xem stream khác, dừng xem stream đó trước
        if self.is_viewing and self.active_streamer_id != streamer_id:
             log_event(f"[LivestreamService][VIEW] Stopping view of previous stream ({self.active_streamer_id}) before starting new one.")
             self.stop_viewing_livestream()

        log_event(f"[LivestreamService][VIEW] Starting to view livestream from {streamer_name} ({streamer_id}).")
        self.is_viewing = True
        self.active_streamer_id = streamer_id
        self.active_streamer_name = streamer_name
        log_event(f"[LivestreamService][VIEW] Now viewing: {self.active_streamer_name}. is_viewing={self.is_viewing}") # Log mới
        # UI sẽ mở cửa sổ viewer và lắng nghe signal viewer_new_frame
        return True

    # **** THÊM LOGGING VÀO HÀM NÀY ****
    def stop_viewing_livestream(self):
        log_event(f"[LivestreamService][VIEW] Attempting stop_viewing_livestream (is_viewing={self.is_viewing})") # Log mới
        if not self.is_viewing:
            return
        log_event(f"[LivestreamService] Stopping view of livestream from {self.active_streamer_name}.")
        streamer_id_being_stopped = self.active_streamer_id # Lưu lại để emit signal
        self.is_viewing = False
        self.active_streamer_id = None
        self.active_streamer_name = None
        # Emit signal để báo cho UI biết đã dừng xem (ví dụ: đóng cửa sổ viewer)
        if streamer_id_being_stopped: # Chỉ emit nếu có ID hợp lệ
             self.livestream_ended_signal.emit(streamer_id_being_stopped)
             log_event(f"[LivestreamService][VIEW] Emitted livestream_ended_signal for {streamer_id_being_stopped}") # Log mới
        log_event("[LivestreamService][VIEW] Viewing stopped.") # Log mới