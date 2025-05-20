# Ví dụ: src/ui/register_page.py (hoặc bạn có thể sửa đổi LoginPage)

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QPushButton, QLabel,
                               QLineEdit, QMessageBox, QFrame, QSpacerItem, QSizePolicy, QHBoxLayout)
from PySide6.QtCore import Signal, Qt

# Đổi tên lớp cho phù hợp nếu đây là trang Đăng ký
class SignupPage(QWidget):
    """
    Trang giao diện cho chức năng đăng ký, theo style image_a443eb.png.

    Signals:
        back_clicked: Được phát ra khi người dùng nhấn nút "Quay lại".
        register_requested: Được phát ra khi người dùng yêu cầu đăng ký.
                            (có thể mang theo tên hiển thị, email, password)
    """
    back_clicked = Signal()
    # Signal mới cho đăng ký, bạn có thể thêm các tham số cần thiết
    register_requested = Signal(str, str, str) # name, email, password

    def __init__(self, parent: QWidget | None = None):
        """Khởi tạo trang đăng ký."""
        super().__init__(parent)
        self._setup_ui()
        # Áp dụng nền tổng thể (giống style cũ)
        self.setStyleSheet("background-color: #1e1e1e;")

    def _setup_ui(self):
        """Thiết lập các thành phần giao diện người dùng với label ngang hàng input."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(50, 50, 50, 50)

        register_frame = QFrame()
        register_frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        # Layout chính bên trong Frame (vẫn là QVBoxLayout)
        frame_layout = QVBoxLayout(register_frame)
        frame_layout.setContentsMargins(40, 40, 40, 40)
        frame_layout.setSpacing(20) # Tăng nhẹ khoảng cách dọc giữa các hàng

        # --- StyleSheet ---
        register_frame.setStyleSheet("""
            QFrame {
                background-color: #2f3136;
                border-radius: 8px;
            }
            /* Style cho Label (tiêu đề) của input field */
            QLabel#inputLabel {
                color: #e0e0e0; /* Màu trắng hơn / sáng hơn */
                font-size: 11pt;
                font-weight: bold; /* IN ĐẬM */
                /* Căn giữa theo chiều dọc với input field */
                /* Có thể cần điều chỉnh padding-right để có khoảng cách với input */
                padding-right: 10px;
                /* Đặt chiều rộng tối thiểu hoặc cố định nếu cần căn chỉnh */
                min-width: 140px;
            }
            QLineEdit {
                background-color: #3a3d42;
                border: 1px solid #50535a;
                border-radius: 4px;
                padding: 12px;
                color: #ffffff;
                font-size: 11pt;
                min-height: 30px;
            }
             QLineEdit:focus {
                border: 1px solid #5865f2;
                background-color: #40444b;
             }
            QPushButton#registerButton {
                background-color: #5865f2; /* ... giữ nguyên style nút ... */
                color: #ffffff;
                border: none;
                border-radius: 4px;
                padding: 12px 30px;
                font-size: 12pt;
                font-weight: bold;
                margin-top: 25px;
                min-height: 35px;
            }
            QPushButton#registerButton:hover { background-color: #4752c4; }
            QPushButton#registerButton:pressed { background-color: #3c45a5; }
            QLabel#titleLabel {
                color: #ffffff; /* ... giữ nguyên style tiêu đề ... */
                font-size: 28pt;
                font-weight: bold;
                margin-bottom: 30px;
                qproperty-alignment: 'AlignCenter';
             }
             QPushButton#backButton {
                background-color: transparent; /* ... giữ nguyên style nút back ... */
                color: #b9bbbe;
                border: none;
                font-size: 11pt;
                font-weight: normal;
                padding: 5px;
                margin-top: 15px;
             }
             QPushButton#backButton:hover {
                color: #ffffff;
                text-decoration: underline;
             }
        """)

        # --- Tiêu đề ---
        title_label = QLabel("Đăng ký")
        title_label.setObjectName("titleLabel")
        # Thêm tiêu đề vào layout dọc chính
        frame_layout.addWidget(title_label)

        # --- Input fields (dùng QHBoxLayout cho mỗi hàng) ---

        # Hàm trợ giúp tạo một hàng label-input
        def create_input_row(label_text: str, placeholder: str, is_password: bool = False) -> tuple[QHBoxLayout, QLineEdit]:
            h_layout = QHBoxLayout()
            label = QLabel(label_text)
            label.setObjectName("inputLabel")
            # Căn lề trái và giữa theo chiều dọc
            label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

            line_edit = QLineEdit()
            line_edit.setPlaceholderText(placeholder)
            if is_password:
                line_edit.setEchoMode(QLineEdit.EchoMode.Password)

            h_layout.addWidget(label) # Thêm label vào layout ngang
            h_layout.addWidget(line_edit) # Thêm input vào layout ngang
            # Optional: Cho input giãn ra nhiều hơn label
            # h_layout.setStretchFactor(line_edit, 1)

            return h_layout, line_edit

        # Tên hiển thị
        name_h_layout, self.name_input = create_input_row(
            "Tên hiển thị", "Nhập tên hiển thị của bạn"
        )
        frame_layout.addLayout(name_h_layout) # Thêm layout ngang vào layout dọc chính

        # Email
        email_h_layout, self.email_input = create_input_row(
            "Email", "Nhập email của bạn"
        )
        frame_layout.addLayout(email_h_layout)

        # Mật khẩu
        password_h_layout, self.password_input = create_input_row(
            "Mật khẩu", "Nhập mật khẩu", is_password=True
        )
        frame_layout.addLayout(password_h_layout)

        # Xác nhận Mật khẩu
        confirm_h_layout, self.confirm_password_input = create_input_row(
            "Xác nhận mật khẩu", "Nhập lại mật khẩu", is_password=True
        )
        frame_layout.addLayout(confirm_h_layout)

        # --- Spacer ---
        # Vẫn giữ spacer để đẩy nút xuống dưới nếu cần
        frame_layout.addSpacerItem(QSpacerItem(20, 30, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding))

        # --- Các nút bấm ---
        # Các nút vẫn được thêm trực tiếp vào frame_layout (layout dọc) và căn giữa
        register_button = QPushButton("Đăng ký")
        register_button.setObjectName("registerButton")
        register_button.setCursor(Qt.CursorShape.PointingHandCursor)
        frame_layout.addWidget(register_button, alignment=Qt.AlignmentFlag.AlignCenter)

        back_button = QPushButton("Quay lại")
        back_button.setObjectName("backButton")
        back_button.setCursor(Qt.CursorShape.PointingHandCursor)
        frame_layout.addWidget(back_button, alignment=Qt.AlignmentFlag.AlignCenter)

        # --- Kết nối tín hiệu ---
        register_button.clicked.connect(self._handle_register)
        back_button.clicked.connect(self.back_clicked.emit)

        # --- Hoàn thiện layout ---
        main_layout.addWidget(register_frame)
        self.setLayout(main_layout)

    # --- Các hàm _handle_register, clear_inputs, show_error giữ nguyên như trước ---
    # ... (copy các hàm đó vào đây)
    def _handle_register(self):
        """Xử lý khi nút đăng ký được nhấn."""
        name = self.name_input.text().strip()
        email = self.email_input.text().strip()
        password = self.password_input.text()
        confirm_password = self.confirm_password_input.text()

        # --- Thêm các bước kiểm tra đầu vào ---
        if not name or not email or not password or not confirm_password:
            self.show_error("Vui lòng điền đầy đủ thông tin.")
            return
        if '@' not in email or '.' not in email:
             self.show_error("Định dạng email không hợp lệ.")
             return
        if password != confirm_password:
            self.show_error("Mật khẩu xác nhận không khớp.")
            return
        if len(password) < 6: # Ví dụ: kiểm tra độ dài mật khẩu
            self.show_error("Mật khẩu phải có ít nhất 6 ký tự.")
            return

        # Nếu mọi thứ ổn, phát tín hiệu
        print(f"Registering: {name}, {email}, {password}") # In ra console để test
        self.register_requested.emit(name, email, password)

    def clear_inputs(self):
        """Xóa nội dung các ô input."""
        self.name_input.clear()
        self.email_input.clear()
        self.password_input.clear()
        self.confirm_password_input.clear()

    def show_error(self, message: str):
        """Hiển thị thông báo lỗi."""
        msgBox = QMessageBox(self)
        msgBox.setIcon(QMessageBox.Icon.Warning)
        msgBox.setWindowTitle("Lỗi Đăng Ký") # Đổi tiêu đề lỗi
        msgBox.setText(message)
        msgBox.setStandardButtons(QMessageBox.StandardButton.Ok)
        # msgBox.setStyleSheet("background-color: #3a3d42; color: #ffffff;") # Tùy chỉnh style nếu muốn
        msgBox.exec()