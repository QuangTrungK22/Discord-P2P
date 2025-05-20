# SegmentChatClient/src/utils/logger.py
import datetime
import os
import traceback # Thêm import này
import config # Giả sử config.py ở thư mục gốc để lấy LOG_MAX_RECORDS

# Xác định đường dẫn tuyệt đối đến thư mục chứa file logger.py này
_log_dir = os.path.dirname(os.path.abspath(__file__))
# Tạo đường dẫn đầy đủ đến file log
log_file_path = os.path.join(_log_dir, "client.log") # Lưu log cùng thư mục utils

_max_log_lines = config.LOG_MAX_RECORDS # Lấy từ config
_log_lock = None # Sẽ dùng lock nếu chạy đa luồng

try:
    # Thử import threading để dùng lock nếu có thể (an toàn hơn khi đa luồng)
    import threading
    _log_lock = threading.Lock()
    print("[LOGGER] Using threading lock for logging.")
except ImportError:
    print("[LOGGER] Threading not available, logging without lock (may have issues in concurrent writes).")


def _check_log_size():
    """Kiểm tra và xóa bớt log nếu quá dài (cơ chế đơn giản)."""
    try:
        # Đếm số dòng hiện tại
        line_count = 0
        if os.path.exists(log_file_path):
            with open(log_file_path, "r", encoding="utf-8") as f:
                for line_count, _ in enumerate(f, 1):
                    pass # Chỉ cần đếm dòng

        if line_count > _max_log_lines:
            print(f"[LOGGER] Log file exceeds {_max_log_lines} lines. Trimming...")
            # Đọc N/2 dòng cuối cùng
            lines_to_keep = _max_log_lines // 2
            kept_lines = []
            with open(log_file_path, "r", encoding="utf-8") as f:
                 # Đọc hết các dòng
                 all_lines = f.readlines()
                 # Lấy phần cuối
                 kept_lines = all_lines[-lines_to_keep:]

            # Ghi đè file với các dòng đã giữ lại
            with open(log_file_path, "w", encoding="utf-8") as f:
                f.write(f"--- Log trimmed at {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---\n")
                f.writelines(kept_lines)
            print(f"[LOGGER] Log file trimmed to approximately {lines_to_keep} lines.")

    except Exception as e:
        print(f"[ERROR][LOGGER] Failed to check/trim log file size: {e}")

# === SỬA ĐỔI HÀM NÀY ===
def log_event(message: str, exc_info: bool = False):
    """
    Ghi một sự kiện vào file log cục bộ một cách an toàn (nếu có threading).
    Nếu exc_info=True, sẽ ghi thêm traceback của exception hiện tại (nếu có).
    """
    global _log_lock
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3] # Thêm millisecond
    log_entry = f"[{timestamp}] {message}\n"

    # Nếu yêu cầu ghi traceback và đang có exception xảy ra
    if exc_info:
        # Lấy traceback dưới dạng string
        # traceback.format_exc() trả về string traceback của exception đang được xử lý
        # sys.exc_info() cũng có thể dùng nhưng format_exc() tiện hơn
        tb_str = traceback.format_exc()
        # Chỉ thêm traceback nếu nó không rỗng (tức là có exception)
        if tb_str and tb_str != 'NoneType: None\n':
             log_entry += tb_str # Nối traceback vào sau message

    if _log_lock:
        # Dùng lock để tránh xung đột khi ghi file từ nhiều luồng
        with _log_lock:
            try:
                # Kiểm tra kích thước trước khi ghi (có thể làm định kỳ thay vì mỗi lần ghi)
                # _check_log_size() # Tạm thời tắt để không làm chậm mỗi lần log
                with open(log_file_path, "a", encoding="utf-8") as f:
                    f.write(log_entry)
            except Exception as e:
                # Ghi lỗi ra console nếu không ghi được log file
                print(f"[CRITICAL][LOGGER] Failed to write log (with lock): {e}")
                print(f"[CRITICAL][LOGGER] Original log entry was: {log_entry.strip()}")
    else:
        # Nếu không có lock (môi trường không hỗ trợ threading?)
        try:
            # _check_log_size()
            with open(log_file_path, "a", encoding="utf-8") as f:
                f.write(log_entry)
        except Exception as e:
            # Ghi lỗi ra console nếu không ghi được log file
            print(f"[CRITICAL][LOGGER] Failed to write log (without lock): {e}")
            print(f"[CRITICAL][LOGGER] Original log entry was: {log_entry.strip()}")

# Có thể gọi kiểm tra log size khi khởi động ứng dụng một lần
# _check_log_size()
# =======================
