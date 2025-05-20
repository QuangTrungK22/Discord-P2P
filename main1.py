# main.py (Phiên bản tái cấu trúc với qasync.run)
import sys
import asyncio
import qasync  # Đảm bảo đã import qasync
from PySide6.QtWidgets import QApplication

# --- Import các thành phần ứng dụng ---
try:
    from src.ui.main_window import ChatMainWindow
    from src.core.app_controller import AppController
    from src.api.client import init_supabase_client, get_supabase_client
    from src.utils.logger import log_event
except ImportError as e:
    # Ghi log lỗi import ban đầu nếu có thể
    try: log_event(f"CRITICAL: Lỗi import ban đầu: {e}", exc_info=True)
    except NameError: pass # Bỏ qua nếu log_event chưa sẵn sàng
    print(f"CRITICAL: Lỗi import ban đầu: {e}. Đảm bảo cấu trúc thư mục dự án và PYTHONPATH đúng.", file=sys.stderr)
    sys.exit(1)
except Exception as e:
    try: log_event(f"CRITICAL: Lỗi không xác định khi import: {e}", exc_info=True)
    except NameError: pass
    print(f"CRITICAL: Lỗi không xác định khi import: {e}", file=sys.stderr)
    sys.exit(1)


async def main():
    """Hàm bất đồng bộ chính điều khiển luồng khởi tạo và chạy ứng dụng."""
    log_event("--- [MAIN ASYNC START] ---")
    app_controller = None # Khởi tạo để dùng trong finally
    try:
        # Lấy hoặc tạo QApplication (phải có trước khi tạo widget)
        app = QApplication.instance()
        if app is None:
            log_event("[MAIN ASYNC] Tạo QApplication (PySide6) instance mới.")
            app = QApplication(sys.argv)
        else:
            log_event("[MAIN ASYNC] Sử dụng QApplication (PySide6) instance đã tồn tại.")

        # Khởi tạo Supabase Client
        log_event("[MAIN ASYNC] Initializing Supabase client...")
        init_supabase_client()
        supabase_instance = get_supabase_client()
        if not supabase_instance:
            log_event("[CRITICAL][MAIN ASYNC] Supabase client không được khởi tạo thành công.", exc_info=False)
            raise RuntimeError("Khởi tạo Supabase Client thất bại.")
        log_event("[MAIN ASYNC] Supabase client đã sẵn sàng.")

        # Khởi tạo UI và Controller (vẫn là đồng bộ)
        log_event("[MAIN ASYNC] Initializing UI and Controller...")
        main_window = ChatMainWindow()
        app_controller = AppController(main_window=main_window) # Tạo controller
        main_window.set_controller(app_controller) # Gán controller cho main window
        log_event("[MAIN ASYNC] UI and Controller initialized.")

        # Khởi động P2P Service (chạy nền, không block)
        # Đảm bảo p2p_service và start_server tồn tại và là async
        if hasattr(app_controller, 'p2p_service') and \
           hasattr(app_controller.p2p_service, 'start_server') and \
           asyncio.iscoroutinefunction(app_controller.p2p_service.start_server):
            log_event("[MAIN ASYNC] Scheduling P2P service start...")
            # Lên lịch chạy start_server, dùng port 0 để tự chọn
            asyncio.create_task(app_controller.p2p_service.start_server(port=0), name="P2P_Startup_Task")
        else:
            log_event("[WARN][MAIN ASYNC] P2P service not found or missing async start_server method.")

        # Hiển thị cửa sổ chính
        main_window.show()
        log_event("[MAIN ASYNC] Main window shown.")

        # Kiểm tra session hiện có (await vì nó là async)
        if hasattr(app_controller, 'check_existing_session') and \
           asyncio.iscoroutinefunction(app_controller.check_existing_session):
            log_event("[MAIN ASYNC] Checking existing session...")
            await app_controller.check_existing_session()
            log_event("[MAIN ASYNC] Session check complete.")
        else:
            log_event("[WARN][MAIN ASYNC] check_existing_session async method not found in controller.")

        # --- Chạy vòng lặp sự kiện Qt tích hợp asyncio ---
        # Cách 1: Sử dụng một event để đợi tín hiệu thoát từ Qt
        quit_event = asyncio.Event()
        def on_quit():
            log_event("[MAIN ASYNC] Quit signal received from Qt. Setting asyncio event.")
            quit_event.set()
        app.aboutToQuit.connect(on_quit)

        log_event("[MAIN ASYNC] Application running, waiting for quit signal...")
        await quit_event.wait() # Giữ coroutine main() chạy cho đến khi Qt thoát

        # Cách 2: Kiểm tra xem qasync có cung cấp hàm nào như loop.run_forever() không
        # Nếu có thì dùng cách đó có thể đơn giản hơn.

    except Exception as e:
        log_event(f"[CRITICAL][MAIN ASYNC] Error during async main execution: {e}", exc_info=True)
        # Có thể hiển thị dialog báo lỗi ở đây nếu cần
    finally:
        log_event("[MAIN ASYNC] Cleaning up...")
        # Dọn dẹp tài nguyên nếu cần, ví dụ đóng controller
        if app_controller and hasattr(app_controller, 'close'):
            log_event("[MAIN ASYNC] Calling AppController close method...")
            try:
                 # Giả định close là đồng bộ hoặc tự quản lý async cleanup
                 app_controller.close()
            except Exception as close_err:
                 log_event(f"[ERROR][MAIN ASYNC] Error during controller cleanup: {close_err}", exc_info=True)
        log_event("--- [MAIN ASYNC END] ---")


if __name__ == "__main__":
    # Chỉ nên có QApplication được tạo ở đây nếu nó thực sự cần trước khi vào qasync.run
    # Thường thì tạo bên trong async def main() sẽ an toàn hơn.
    # qt_app = QApplication.instance() or QApplication(sys.argv) # Có thể bỏ dòng này

    log_event(f"[MAIN_ENTRY] Application starting with args: {sys.argv}")
    exit_code = 1
    try:
        # Sử dụng qasync.run() để chạy hàm async main()
        # qasync.run() sẽ tự động tạo và quản lý event loop tích hợp
        log_event("[MAIN_ENTRY] Calling qasync.run(main())...")
        exit_code = qasync.run(main())
        log_event(f"[MAIN_ENTRY] qasync.run() finished.")

    except KeyboardInterrupt:
        log_event("[MAIN_ENTRY] Application interrupted by user (KeyboardInterrupt).")
        exit_code = 0
    except Exception as e:
        log_event(f"[CRITICAL][MAIN_ENTRY] Top-level unhandled exception: {e}", exc_info=True)
    finally:
        log_event(f"[MAIN_ENTRY] Application exiting with code: {exit_code}")
        sys.exit(exit_code)