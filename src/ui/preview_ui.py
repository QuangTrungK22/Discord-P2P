import sys
from PySide6.QtWidgets import QApplication
from main_window import ChatMainWindow  # Import lớp cửa sổ chính từ package ui

if __name__ == "__main__":
    app = QApplication(sys.argv)
    # Tạo một instance của lớp cửa sổ chính
    main_window = ChatMainWindow()
    # Hiển thị cửa sổ
    main_window.show()
    # Bắt đầu vòng lặp sự kiện của ứng dụng
    sys.exit(app.exec())