# SegmentChatClient/src/storage/local_store.py
import sqlite3
import os
import datetime
from typing import List, Optional, Tuple
from src.models.message import Message # Import model Message
from typing import List, Any

# Xác định đường dẫn đến file database SQLite
_STORAGE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(_STORAGE_DIR, "local_chat_storage.db")
try:
    from src.utils.logger import log_event
    log_event(f"[STORAGE] Using DB file path: {DB_FILE}")
except ImportError:
    print(f"[STORAGE] Using DB file path: {DB_FILE}")

# Biến cờ để đảm bảo DB được khởi tạo chỉ một lần
_db_initialized = False
_db_lock = None # Lock cho môi trường đa luồng

try:
    import threading
    _db_lock = threading.Lock()
except ImportError:
    pass # Không dùng lock nếu không có threading

def _get_db_connection() -> sqlite3.Connection:
    """Mở kết nối đến database SQLite."""
    try:
        # isolation_level=None để tự quản lý transaction hoặc bật autocommit (tuỳ nhu cầu)
        # Hoặc để mặc định và dùng conn.commit() / conn.rollback()
        # timeout để tránh lỗi database is locked nếu nhiều thread truy cập
        conn = sqlite3.connect(DB_FILE, timeout=10, check_same_thread=False) # check_same_thread=False nếu dùng đa luồng
        # Đặt row_factory để trả về dict thay vì tuple (tùy chọn)
        # conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.Error as e:
        log_event(f"[ERROR][STORAGE] Could not connect to SQLite database '{DB_FILE}': {e}")
        raise # Raise lỗi lên để nơi gọi xử lý

def init_storage():
    """
    Khởi tạo database và bảng nếu chưa tồn tại.
    Cần được gọi một lần khi ứng dụng khởi động.
    """
    global _db_initialized
    if _db_initialized:
        return

    log_event(f"[STORAGE] Initializing local storage at '{DB_FILE}'...")
    conn = None # Khởi tạo conn là None
    acquired_lock = False
    try:
        # Dùng lock nếu có thể
        if _db_lock:
            _db_lock.acquire()
            acquired_lock = True

        # Kiểm tra lại _db_initialized bên trong lock
        if _db_initialized:
             if acquired_lock: _db_lock.release()
             return

        conn = _get_db_connection()
        cursor = conn.cursor()

        # Bật foreign keys (nếu có kế hoạch dùng)
        cursor.execute("PRAGMA foreign_keys = ON;")
        # Chế độ WAL thường tốt hơn cho ghi đồng thời (dù đây là client)
        cursor.execute("PRAGMA journal_mode=WAL;")

        # Tạo bảng messages nếu chưa tồn tại
        # Lưu timestamp dưới dạng TEXT theo chuẩn ISO 8601 (dễ đọc và chuẩn)
        # Hoặc dùng INTEGER lưu Unix timestamp (số giây từ epoch)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,                  -- UUID dạng TEXT làm khóa chính
                channel_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                content TEXT,
                timestamp TEXT NOT NULL,              -- Lưu dạng ISO 8601 UTC: 'YYYY-MM-DDTHH:MM:SS.ffffff+00:00'
                sender_display_name TEXT
            );
        """)

        # Tạo index để tăng tốc độ truy vấn theo kênh và thời gian
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_channel_timestamp ON messages (channel_id, timestamp);")

        # TODO: Tạo các bảng khác nếu cần (ví dụ: channels, users_info...)

        conn.commit()
        log_event("[STORAGE] Database tables checked/created successfully.")
        _db_initialized = True

    except sqlite3.Error as e:
        log_event(f"[ERROR][STORAGE] Failed to initialize database tables: {e}")
        if conn:
            conn.rollback() # Hoàn tác nếu có lỗi
    finally:
        if conn:
            conn.close()
        if acquired_lock: # Chỉ release nếu đã acquire
            _db_lock.release()


def add_message(message: Message) -> bool:
    """
    Thêm một tin nhắn mới vào CSDL cục bộ.
    Tự động tạo ID nếu message.id là None.
    """
    if not _db_initialized:
        log_event("[ERROR][STORAGE] Storage not initialized. Cannot add message.")
        # Hoặc thử gọi init_storage() ở đây? Cần cẩn thận.
        return False

    # Tạo ID nếu chưa có (nên tạo UUID chuẩn)
    if message.id is None:
        import uuid
        message.id = str(uuid.uuid4())

    # Chuyển timestamp sang string ISO 8601 UTC
    ts_iso = message.timestamp.astimezone(datetime.timezone.utc).isoformat()

    sql = """
        INSERT OR REPLACE INTO messages (id, channel_id, user_id, content, timestamp, sender_display_name)
        VALUES (?, ?, ?, ?, ?, ?);
    """
    params = (
        message.id,
        message.channel_id,
        message.user_id,
        message.content,
        ts_iso, # Lưu dạng string
        message.sender_display_name
    )

    conn = None
    acquired_lock = False
    success = False
    log_event(f"[STORAGE][ATTEMPT] Attempting to add/replace message ID: {message.id} for channel: {message.channel_id}")
    try:
        if _db_lock:
            _db_lock.acquire()
            acquired_lock = True

        conn = _get_db_connection()
        cursor = conn.cursor()
        cursor.execute(sql, params)
        conn.commit()
        log_event(f"[STORAGE] Message '{message.id}' added to local DB for channel {message.channel_id}.")
        success = True
    except sqlite3.IntegrityError:
         log_event(f"[WARN][STORAGE] Message with ID '{message.id}' likely already exists.")
         # Có thể coi là thành công nếu đã tồn tại hoặc thất bại tùy logic
         success = True # Giả sử trùng ID không phải lỗi nghiêm trọng
    except sqlite3.Error as e:
        log_event(f"[ERROR][STORAGE] Failed to add message '{message.id}': {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()
        if acquired_lock:
             _db_lock.release()
    return success


def get_messages_for_channel(channel_id: str, limit: int = 100, before_timestamp: Optional[datetime.datetime] = None) -> List[Message]:
    """
    Lấy danh sách tin nhắn cho một kênh từ CSDL cục bộ.
    Sắp xếp theo thời gian tăng dần (cũ nhất trước).
    Có thể lấy các tin nhắn trước một thời điểm cụ thể (để phân trang).
    """
    if not _db_initialized:
        log_event("[ERROR][STORAGE] Storage not initialized. Cannot get messages.")
        return []

    messages: List[Message] = []
    sql = """
        SELECT id, channel_id, user_id, content, timestamp, sender_display_name
        FROM messages
        WHERE channel_id = ?
    """
    params: List[Any] = [channel_id]

    if before_timestamp:
        # Lấy các tin nhắn CŨ HƠN thời điểm cung cấp
        ts_iso = before_timestamp.astimezone(datetime.timezone.utc).isoformat()
        sql += " AND timestamp < ? "
        params.append(ts_iso)

    sql += " ORDER BY timestamp DESC LIMIT ?;" # Lấy mới nhất trước, sau đó đảo ngược
    params.append(limit)

    conn = None
    acquired_lock = False
    try:
        if _db_lock:
            _db_lock.acquire()
            acquired_lock = True

        conn = _get_db_connection()
        cursor = conn.cursor()
        cursor.execute(sql, params)
        rows = cursor.fetchall()

        log_event(f"[STORAGE] Fetched {len(rows)} messages locally for channel {channel_id}.")

        for row in rows:
            msg_id, chan_id, user_id, content, ts_str, sender_name = row
            # Chuyển đổi timestamp từ string ISO format sang datetime object
            timestamp = datetime.datetime.now(datetime.timezone.utc) # Default nếu lỗi
            try:
                 timestamp = datetime.datetime.fromisoformat(ts_str)
                 # Đảm bảo có timezone (sqlite không lưu tz, nhưng isoformat() cần nó)
                 if timestamp.tzinfo is None:
                      timestamp = timestamp.replace(tzinfo=datetime.timezone.utc) # Giả định là UTC
            except ValueError:
                 log_event(f"[WARN][STORAGE] Could not parse timestamp string from DB: {ts_str}")

            messages.append(Message(
                id=msg_id,
                channel_id=chan_id,
                user_id=user_id,
                content=content,
                timestamp=timestamp,
                sender_display_name=sender_name
            ))

    except sqlite3.Error as e:
        log_event(f"[ERROR][STORAGE] Failed to get messages for channel {channel_id}: {e}")
    finally:
        if conn:
            conn.close()
        if acquired_lock:
             _db_lock.release()

    # Đảo ngược danh sách để có thứ tự thời gian tăng dần (cũ trước, mới sau)
    messages.reverse()
    return messages

# --- Có thể thêm các hàm khác ---
# def get_latest_timestamp(channel_id: str) -> Optional[datetime.datetime]: ...
# def delete_channel_messages(channel_id: str): ...
# def get_message_by_id(message_id: str) -> Optional[Message]: ...