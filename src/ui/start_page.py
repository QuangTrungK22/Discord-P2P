# src/ui/start_page.py (Đã cập nhật)

from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QLabel, QSizePolicy
from PySide6.QtCore import Signal, Qt

class StartPage(QWidget):
    # Signals để giao tiếp với bên ngoài (MainWindow hoặc Controller)
    login_clicked = Signal()
    signup_clicked = Signal()
    guest_clicked = Signal() # Thêm signal cho nút Khách

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._setup_ui()
        # Áp dụng màu nền cho toàn bộ trang StartPage
        self.setStyleSheet("background-color: #36393f;")

    def _setup_ui(self):
        """Thiết lập các thành phần giao diện người dùng."""
        layout = QVBoxLayout(self)
        # Căn chỉnh các widget con vào giữa layout theo chiều dọc và ngang
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # --- Tiêu đề ---
        title_label = QLabel("Địa Thư") # Giữ lại tên từ thiết kế mới
        # Áp dụng style cho tiêu đề (màu trắng, kích thước lớn, đậm)
        title_label.setStyleSheet("""
            QLabel {
                color: #ffffff;
                font-size: 36pt;
                font-weight: bold;
                margin-bottom: 50px; /* Khoảng cách dưới tiêu đề */
            }
        """)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # Đảm bảo label chỉ chiếm không gian cần thiết theo chiều cao
        title_label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        layout.addWidget(title_label) # Thêm tiêu đề vào layout

        # --- Định nghĩa Style chung cho các nút ---
        button_width = 200
        button_height = 50
        # Sử dụng f-string hoặc % formatting để nhúng kích thước vào style
        button_style = f"""
            QPushButton {{
                background-color: #5865f2; /* Màu nền xanh dương */
                color: #ffffff; /* Màu chữ trắng */
                border-radius: 8px; /* Bo góc */
                padding: 10px;
                font-size: 14pt;
                font-weight: bold;
                min-width: {button_width}px;
                min-height: {button_height}px;
                max-width: {button_width}px;
                max-height: {button_height}px;
            }}
            QPushButton:hover {{
                background-color: #4752c4; /* Màu nền khi di chuột qua */
            }}
             QPushButton:pressed {{
                background-color: #3c45a5; /* Màu nền khi nhấn */
            }}
        """

        # --- Nút Đăng nhập ---
        self.login_button = QPushButton("Đăng nhập")
        self.login_button.setStyleSheet(button_style)
        self.login_button.setCursor(Qt.CursorShape.PointingHandCursor)
        # Kết nối nút với signal của lớp
        self.login_button.clicked.connect(self.login_clicked.emit)
        layout.addWidget(self.login_button, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addSpacing(15) # Thêm khoảng cách dọc giữa các nút

        # --- Nút Đăng ký ---
        self.signup_button = QPushButton("Đăng ký")
        self.signup_button.setStyleSheet(button_style)
        self.signup_button.setCursor(Qt.CursorShape.PointingHandCursor)
        # Kết nối nút với signal của lớp
        self.signup_button.clicked.connect(self.signup_clicked.emit)
        layout.addWidget(self.signup_button, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addSpacing(15)

        # --- Nút Chế độ khách ---
        self.guest_button = QPushButton("Chế độ khách")
        self.guest_button.setStyleSheet(button_style)
        self.guest_button.setCursor(Qt.CursorShape.PointingHandCursor)
        # Kết nối nút với signal mới của lớp
        self.guest_button.clicked.connect(self.guest_clicked.emit)
        layout.addWidget(self.guest_button, alignment=Qt.AlignmentFlag.AlignCenter)

        # Thêm giãn cách (stretch) vào đầu và cuối layout để đẩy nội dung vào giữa theo chiều dọc
        layout.insertStretch(0, 1) # Thêm stretch ở trên cùng (index 0)
        layout.addStretch(1)      # Thêm stretch ở dưới cùng

        self.setLayout(layout)

# ----- Khối chạy thử nghiệm (nếu cần) -----
if __name__ == '__main__':
    import sys
    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    start_page = StartPage()

    # Kết nối thử signals
    start_page.login_clicked.connect(lambda: print("Login Clicked!"))
    start_page.signup_clicked.connect(lambda: print("Signup Clicked!"))
    start_page.guest_clicked.connect(lambda: print("Guest Mode Clicked!"))

    start_page.setWindowTitle("Start Page Test")
    start_page.resize(600, 500)
    start_page.show()
    sys.exit(app.exec())