import sys
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QLabel
from chat_page import ChatPage  # Import lớp ChatPage

if __name__ == "__main__":
    app = QApplication(sys.argv)

    main_window = QMainWindow()
    main_window.setWindowTitle("Chat Page Preview")
    main_window.setGeometry(100, 100, 1080, 720)

    chat_page_widget = ChatPage()

    # --- Dữ liệu người dùng mẫu ---
    sample_members = [
        ("User Minh An", True),      # Online
        ("User Bao Khanh", False),     # Offline/Invisible
        ("User Chau Anh", True),     # Online
        ("User Dac Thang", True),    # Online
        ("User Ngoc Ha", False),      # Offline/Invisible
        ("User Phi Hung", True),     # Online
        ("User Quoc Bao", False),     # Offline/Invisible
        ("User Thanh Trung", True),   # Online
        ("User Tuan Kiet", True),    # Online
        ("User Viet Anh", False),     # Offline/Invisible
    ]
    # ------------------------------

    # Đặt ChatPage làm widget trung tâm của cửa sổ chính TRƯỚC khi cập nhật dữ liệu
    main_window.setCentralWidget(chat_page_widget)

    # --- Cập nhật danh sách thành viên trên giao diện với dữ liệu mẫu SAU khi đặt widget trung tâm ---
    chat_page_widget.update_channel_members(sample_members)
    # -----------------------------------------------------------------------------------------------

    # Hiển thị cửa sổ chính (chứa trang chat)
    main_window.show()

    # Bắt đầu vòng lặp sự kiện của ứng dụng
    sys.exit(app.exec())