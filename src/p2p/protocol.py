# src/p2p/protocol.py
import json
from typing import Dict, Any, Optional, List

# Giả sử logger đã được cấu hình và import đúng cách
try:
    from src.utils.logger import log_event
except ImportError:
    # Fallback nếu logger chưa sẵn sàng hoặc khi chạy file riêng lẻ
    def log_event(msg, exc_info=False):
        print(msg)
        if exc_info:
            import traceback
            traceback.print_exc()

# --- Định nghĩa các loại message type ---
MSG_TYPE_GREETING = "greeting"         # Gửi khi mới kết nối
MSG_TYPE_CHAT_MESSAGE = "chat_message" # Tin nhắn chat thông thường
MSG_TYPE_PEER_LIST_REQUEST = "req_peers"   # Yêu cầu danh sách peer từ peer khác (nâng cao)
MSG_TYPE_PEER_LIST_RESPONSE = "res_peers" # Phản hồi danh sách peer
MSG_TYPE_REQUEST_HISTORY = "req_history" # Yêu cầu lịch sử chat từ host
MSG_TYPE_HISTORY_CHUNK = "res_history"   # Phản hồi một phần lịch sử chat
MSG_TYPE_ERROR = "error"             # Thông báo lỗi P2P
MSG_TYPE_ACK = "ack"                 # Xác nhận đã nhận (generic)
MSG_TYPE_STATUS_UPDATE = "status"    # Cập nhật trạng thái user (tùy chọn)
MSG_TYPE_LIVESTREAM_START = "livestream_start"     # Host báo bắt đầu stream
MSG_TYPE_LIVESTREAM_END = "livestream_end"       # Host báo kết thúc stream
MSG_TYPE_VIDEO_FRAME = "video_frame"           # Gói tin chứa dữ liệu frame video

# --- Ví dụ cấu trúc Payload ---
# greeting: {"user_id": "...", "display_name": "..."}
# chat_message: {"sender_id": "...", "channel_id": "...", "content": "...", "timestamp_iso": "..."}
# req_history: {"channel_id": "...", "since_timestamp_iso": "..." | None}
# res_history: {"channel_id": "...", "messages": [ {message_dict}, ... ], "is_last_chunk": True/False}
# status_update: {"user_id": "...", "status": "online|offline|invisible"}
# video_frame: {"streamer_id": "...", "frame_id": int, "frame_data": "base64_encoded_jpeg"} # Cập nhật cấu trúc

def create_message(msg_type: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Tạo một dictionary message chuẩn với type và payload."""
    if payload is None:
        payload = {} # Đảm bảo payload luôn là dict nếu không được cung cấp
    return {"type": msg_type, "payload": payload}

# --- Hàm encode/decode (Giữ nguyên) ---

def encode_message(message_dict: Dict[str, Any]) -> Optional[bytes]:
    """
    Chuyển đổi dictionary thành bytes JSON UTF-8, thêm ký tự xuống dòng.
    """
    try:
        json_string = json.dumps(message_dict, ensure_ascii=False)
        message_bytes = (json_string + '\n').encode('utf-8')
        return message_bytes
    except TypeError as e:
        log_event(f"[ERROR][P2P_PROTO] Failed to serialize message to JSON: {e}. Message: {message_dict}")
        return None
    except Exception as e:
        log_event(f"[ERROR][P2P_PROTO] Unexpected error encoding message: {e}")
        return None

def decode_message(data_bytes: bytes) -> Optional[Dict[str, Any]]:
    """
    Chuyển đổi bytes UTF-8 (đã loại bỏ ký tự xuống dòng) thành dictionary.
    """
    try:
        message_str = data_bytes.decode('utf-8').strip()
        if not message_str: # Bỏ qua message rỗng
             return None
        payload = json.loads(message_str)
        # Kiểm tra xem có phải là dictionary và có 'type' không
        if isinstance(payload, dict) and "type" in payload:
            return payload
        else:
            log_event(f"[ERROR][P2P_PROTO] Decoded JSON is not a valid message structure (missing 'type'): {payload}")
            return None
    except json.JSONDecodeError:
        log_event(f"[ERROR][P2P_PROTO] Failed to decode JSON message. Raw bytes: {data_bytes[:100]}...") # Log một phần dữ liệu lỗi
        return None
    except UnicodeDecodeError:
        log_event(f"[ERROR][P2P_PROTO] Failed to decode UTF-8 message. Raw bytes: {data_bytes[:100]}...")
        return None
    except Exception as e:
        log_event(f"[ERROR][P2P_PROTO] Failed to parse message: {e}")
        return None

# --- Hàm tạo payload cho Livestream ---
def create_livestream_start_payload(streamer_id: str, streamer_name: str) -> Dict[str, Any]:
    """Tạo payload cho message bắt đầu livestream."""
    return {"streamer_id": streamer_id, "streamer_name": streamer_name}

def create_livestream_end_payload(streamer_id: str) -> Dict[str, Any]:
    """Tạo payload cho message kết thúc livestream."""
    return {"streamer_id": streamer_id}

# **** HÀM ĐÃ ĐƯỢC CẬP NHẬT ****
def create_video_frame_payload(streamer_id: str, frame_data_base64: str, frame_id: Optional[int] = None) -> Dict[str, Any]:
    """
    Tạo payload cho gói tin video frame, bao gồm ID của người stream.

    Args:
        streamer_id (str): ID của người dùng đang stream.
        frame_data_base64 (str): Dữ liệu frame đã được encode base64.
        frame_id (Optional[int]): ID tuần tự của frame (tùy chọn).

    Returns:
        Dict[str, Any]: Payload cho message video frame.
    """
    payload = {
        "streamer_id": streamer_id, # **** Thêm trường streamer_id ****
        "frame_data": frame_data_base64
    }
    if frame_id is not None:
        payload["frame_id"] = frame_id
    # log_event(f"[P2P_PROTO] Created video frame payload for streamer {streamer_id}, frame {frame_id}") # Log nếu cần
    return payload

# --- Các hàm trợ giúp tạo message cụ thể khác (Giữ nguyên) ---
def create_chat_payload(sender_id: str, channel_id: str, content: str, timestamp_iso: str) -> Dict[str, Any]:
     return {"sender_id": sender_id, "channel_id": channel_id, "content": content, "timestamp_iso": timestamp_iso}

def create_greeting_payload(user_id: str, display_name: str) -> Dict[str, Any]:
     return {"user_id": user_id, "display_name": display_name}

# ... (Thêm các hàm create_payload khác nếu cần) ...

# Log khi module được load (có thể giúp xác nhận phiên bản đúng đang chạy)
log_event("--- [P2P_PROTO] Protocol definitions loaded (Includes streamer_id in video frame) ---")