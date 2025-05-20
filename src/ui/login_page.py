# src/ui/login_page.py

# Thêm QHBoxLayout vào danh sách import
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
                               QLineEdit, QMessageBox, QFrame, QSpacerItem, QSizePolicy)
from PySide6.QtCore import Signal, Qt

class LoginPage(QWidget):
    """
    Trang giao diện cho chức năng đăng nhập, với label ngang hàng input.

    Signals:
        back_clicked: Được phát ra khi người dùng nhấn nút "Quay lại".
        login_requested: Được phát ra khi người dùng yêu cầu đăng nhập,
                         mang theo email và password. (str, str)
    """
    back_clicked = Signal()
    login_requested = Signal(str, str)  # email, password

    def __init__(self, parent: QWidget | None = None):
        """Khởi tạo trang đăng nhập."""
        super().__init__(parent)
        self._setup_ui()
        self.setStyleSheet("background-color: #1e1e1e;")

    def _setup_ui(self):
        """Thiết lập giao diện với label căn lề trái, ngang hàng input."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(50, 50, 50, 50)

        login_frame = QFrame()
        login_frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        frame_layout = QVBoxLayout(login_frame)
        frame_layout.setContentsMargins(60, 60, 60, 60)
        frame_layout.setSpacing(15) # Giữ khoảng cách đã điều chỉnh

        # --- StyleSheet ---
        # Giữ nguyên StyleSheet, min-width cho label vẫn hữu ích để các input thẳng hàng
        login_frame.setStyleSheet("""
            QFrame {
                background-color: #2f3136;
                border-radius: 8px;
            }
            QLabel#inputLabel {
                color: #e0e0e0;
                font-size: 11pt;
                font-weight: bold;
                padding-right: 10px;
                min-width: 80px;  /* Giữ min-width để các ô input bắt đầu cùng vị trí */
            }
            QLineEdit {
                background-color: #3a3d42;
                border: 1px solid #50535a;
                border-radius: 4px;
                padding: 12px;
                color: #ffffff;
                font-size: 12pt;
                min-height: 30px;
            }
             QLineEdit:focus {
                border: 1px solid #5865f2;
                background-color: #40444b;
             }
            QPushButton#loginButton {
                background-color: #5865f2;
                color: #ffffff;
                border: none;
                border-radius: 4px;
                padding: 12px;
                font-size: 13pt;
                font-weight: bold;
                margin-top: 30px; /* Giữ margin đã điều chỉnh */
                min-height: 35px;
            }
            QPushButton#loginButton:hover { background-color: #4752c4; }
            QPushButton#loginButton:pressed { background-color: #3c45a5; }
            QLabel#titleLabel {
                color: #ffffff;
                font-size: 32pt;
                font-weight: bold;
                margin-bottom: 40px;
                qproperty-alignment: 'AlignCenter';
             }
             QPushButton#backButton {
                background-color: transparent;
                color: #b9bbbe;
                border: none;
                font-size: 11pt;
                font-weight: normal;
                padding: 5px;
                margin-top: 10px; /* Giữ margin đã điều chỉnh */
             }
             QPushButton#backButton:hover {
                color: #ffffff;
                text-decoration: underline;
             }
        """)

        # --- Tiêu đề ---
        title_label = QLabel("Đăng Nhập")
        title_label.setObjectName("titleLabel")
        frame_layout.addWidget(title_label)

        # --- Input fields dùng QHBoxLayout ---
        def create_input_row(label_text: str, placeholder: str, is_password: bool = False) -> tuple[QHBoxLayout, QLineEdit]:
            h_layout = QHBoxLayout()
            label = QLabel(label_text)
            label.setObjectName("inputLabel")
            # *** THAY ĐỔI Ở ĐÂY: Đổi AlignRight thành AlignLeft ***
            label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter) # Căn lề TRÁI

            line_edit = QLineEdit()
            line_edit.setPlaceholderText(placeholder)
            if is_password:
                line_edit.setEchoMode(QLineEdit.EchoMode.Password)

            h_layout.addWidget(label)
            h_layout.addWidget(line_edit)
            # Giữ stretch factor để ô input giãn ra
            h_layout.setStretchFactor(line_edit, 1)

            return h_layout, line_edit

        email_h_layout, self.email_input = create_input_row(
            "Email", "Nhập địa chỉ email của bạn"
        )
        frame_layout.addLayout(email_h_layout)

        password_h_layout, self.password_input = create_input_row(
            "Mật khẩu", "Nhập mật khẩu", is_password=True
        )
        frame_layout.addLayout(password_h_layout)

        # --- Sử dụng addSpacing thay cho Spacer ---
        frame_layout.addSpacing(30) # Giữ khoảng trống cố định đã điều chỉnh

        # --- Các nút bấm ---
        login_button = QPushButton("Đăng nhập")
        login_button.setObjectName("loginButton")
        login_button.setCursor(Qt.CursorShape.PointingHandCursor)
        frame_layout.addWidget(login_button, alignment=Qt.AlignmentFlag.AlignCenter)

        back_button = QPushButton("Quay lại")
        back_button.setObjectName("backButton")
        back_button.setCursor(Qt.CursorShape.PointingHandCursor)
        frame_layout.addWidget(back_button, alignment=Qt.AlignmentFlag.AlignCenter)

        # --- Kết nối tín hiệu ---
        login_button.clicked.connect(self._handle_login)
        back_button.clicked.connect(self.back_clicked.emit)

        # --- Hoàn thiện layout ---
        main_layout.addWidget(login_frame)
        self.setLayout(main_layout)

    def _handle_login(self):
        """Xử lý khi nút đăng nhập được nhấn."""
        email = self.email_input.text().strip()
        password = self.password_input.text()

        if not email or not password:
            self.show_error("Vui lòng nhập đầy đủ email và mật khẩu.")
            return
        if '@' not in email or '.' not in email:
             self.show_error("Định dạng email không hợp lệ.")
             return

        self.login_requested.emit(email, password)

    def clear_inputs(self):
        """Xóa nội dung các ô input."""
        self.email_input.clear()
        self.password_input.clear()

    def show_error(self, message: str):
        """Hiển thị thông báo lỗi."""
        msgBox = QMessageBox(self)
        msgBox.setIcon(QMessageBox.Icon.Warning)
        msgBox.setWindowTitle("Lỗi Đăng Nhập")
        msgBox.setText(message)
        msgBox.setStandardButtons(QMessageBox.StandardButton.Ok)
        msgBox.exec()