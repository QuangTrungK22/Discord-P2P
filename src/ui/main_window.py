from PySide6.QtWidgets import QMainWindow, QStatusBar, QStackedWidget
from PySide6.QtCore import Slot, Qt, QMetaObject, Q_ARG
from src.models.user import User
from src.utils.logger import log_event
from .start_page import StartPage
from .login_page import LoginPage
from .signup_page import SignupPage
from .chat_page import ChatPage
from src.core.app_controller import AppController

class ChatMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Địa Thư - Secure P2P Chat")
        self.resize(1024, 768)
        
        # Initialize controller reference
        self.controller = None
        
        # Initialize pages
        self.start_page = StartPage()
        self.login_page = LoginPage()
        self.signup_page = SignupPage()
        self.chat_page = ChatPage()
        
        # Setup stacked widget
        self.stacked_widget = QStackedWidget()
        self.stacked_widget.addWidget(self.start_page)    # Index 0
        self.stacked_widget.addWidget(self.login_page)    # Index 1
        self.stacked_widget.addWidget(self.signup_page)   # Index 2
        self.stacked_widget.addWidget(self.chat_page)     # Index 3
        
        self.setCentralWidget(self.stacked_widget)
        self.setStatusBar(QStatusBar())

    def set_controller(self, controller):
        """Gán controller và thiết lập kết nối tín hiệu từ Controller -> MainWindow."""
        self.controller = controller
        log_event("[UI] MainWindow controller set.")

        # Gán controller cho các trang con
        if hasattr(self.chat_page, 'set_controller'):
            self.chat_page.set_controller(controller)
            log_event("[UI] ChatPage controller set.")

        # Setup các kết nối nội bộ
        self._setup_connections()
        log_event("[UI] Setting up connections in MainWindow...")

        # Kết nối signals từ controller tới MainWindow
        if self.controller:
            try:
                # Auth signals
                self.controller.login_successful.connect(self.on_login_success)
                self.controller.login_failed.connect(self.on_login_failed)
                self.controller.signup_successful.connect(self.on_signup_success)
                self.controller.signup_failed.connect(self.on_signup_failed)
                self.controller.logout_finished.connect(self.on_logout_finished)
                
                # Status updates
                self.controller.status_update_signal.connect(self.show_status_message)
                
                # Channel signals (nếu cần)
                if hasattr(self.chat_page, 'update_channel_lists'):
                    self.controller.channelsUpdated.connect(
                        self.chat_page.update_channel_lists
                    )
                
                log_event("[UI] MainWindow navigation connections setup complete.")
            except Exception as e:
                log_event(f"[ERROR][UI] Failed to connect controller signals: {e}", 
                         exc_info=True)
        else:
            log_event("[WARN][UI] No controller set, skipping signal connections.")

    def switch_to_page(self, page_name: str):
        """Switch to the specified page in stacked widget."""
        log_event(f"[UI] Attempting to switch to page: {page_name}")
        
        # Map page names to widgets
        widget_map = {
            "start": self.start_page,
            "login": self.login_page,
            "signup": self.signup_page,
            "chat": self.chat_page
        }
        
        widget_to_show = widget_map.get(page_name)
        if widget_to_show:
            index = self.stacked_widget.indexOf(widget_to_show)
            if index != -1:
                self.stacked_widget.setCurrentIndex(index)
                log_event(f"[UI] Switched to page: {page_name} (Index: {index})")
                
                # Clear inputs when leaving login/signup pages
                if page_name != "login" and hasattr(self.login_page, 'clear_inputs'):
                    self.login_page.clear_inputs()
                if page_name != "signup" and hasattr(self.signup_page, 'clear_inputs'):
                    self.signup_page.clear_inputs()
            else:
                log_event(f"[WARN][UI] Widget for page '{page_name}' not found in stacked widget.")
        else:
            log_event(f"[WARN][UI] Unknown page name requested for switch: {page_name}")

    @Slot(User)
    def on_login_success(self, user: User):
        """Xử lý khi đăng nhập thành công."""
        log_event(f"[UI] Login successful for user: {user.display_name}")
        
        # Cập nhật UI chat page
        if hasattr(self.chat_page, 'update_user_info_display'):
            self.chat_page.update_user_info_display(
                user.display_name or user.email
            )
            print(user.display_name, user.email)
        else:
            print("[WARN][UI] chat_page does not have update_user_info_display method.")
        
        # Chuyển sang trang chat
        self.switch_to_page("chat")
        self.statusBar().showMessage(
            f"Đăng nhập thành công! Chào {user.display_name}!", 
            5000
        )

    @Slot(str) 
    def on_login_failed(self, error_message: str):
        """Xử lý khi đăng nhập thất bại."""
        log_event(f"[UI] Login failed: {error_message}")
        if hasattr(self.login_page, 'show_error'):
            self.login_page.show_error(error_message)
        self.statusBar().showMessage(f"Lỗi đăng nhập: {error_message}", 5000)

    @Slot()
    def on_signup_success(self):
        """Xử lý khi đăng ký thành công."""
        log_event("[UI] Signup successful")
        if hasattr(self.signup_page, 'clear_inputs'):
            self.signup_page.clear_inputs()
        self.statusBar().showMessage("Đăng ký thành công! Vui lòng đăng nhập.", 5000)
        self.switch_to_page("login")

    @Slot(str)
    def on_signup_failed(self, error_message: str):
        """Xử lý khi đăng ký thất bại."""
        log_event(f"[UI] Signup failed: {error_message}")
        if hasattr(self.signup_page, 'show_error'):
            self.signup_page.show_error(error_message)
        self.statusBar().showMessage(f"Lỗi đăng ký: {error_message}", 5000)

    @Slot()
    def on_logout_finished(self):
        """Xử lý khi đăng xuất hoàn tất."""
        log_event("[UI] Logout completed")
        if hasattr(self.chat_page, 'clear_all'):
            self.chat_page.clear_all()
        self.switch_to_page("start")
        self.statusBar().showMessage("Đã đăng xuất.", 3000)

    @Slot(str)
    def show_status_message(self, message: str):
        """Hiển thị thông báo trạng thái."""
        self.statusBar().showMessage(message, 4000)

    def _setup_connections(self):
        """Thiết lập các kết nối nội bộ của MainWindow."""
        log_event("[UI] Setting up connections in MainWindow...")
        if not self.controller:
            log_event("[WARN][UI] Cannot setup connections: Controller not set.")
            return

        try:
            # Connect StartPage buttons
            self.start_page.login_clicked.connect(lambda: self.switch_to_page("login"))
            self.start_page.signup_clicked.connect(lambda: self.switch_to_page("signup"))
            
            # Connect back buttons
            self.login_page.back_clicked.connect(lambda: self.switch_to_page("start"))
            self.signup_page.back_clicked.connect(lambda: self.switch_to_page("start"))
            
            log_event("[UI] MainWindow navigation connections setup complete.")
            
        except Exception as e:
            log_event(f"[ERROR][UI] Failed to setup MainWindow connections: {e}", exc_info=True)