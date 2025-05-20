import sys
from PySide6.QtWidgets import QApplication, QPushButton, QWidget, QVBoxLayout, QHBoxLayout, QMessageBox
from PySide6.QtGui import QPixmap, QColor, QImage # Thêm QImage
import numpy as np # Cần cho việc tạo frame giả

# Giả sử các file window của bạn nằm trong cùng thư mục 'ui' hoặc bạn đã cấu hình sys.path đúng
try:
    from livestream_host_window import LivestreamHostWindow
    from livestream_viewer_window import LivestreamViewerWindow
except ImportError:
    # Nếu chạy file này trực tiếp từ thư mục 'ui', import sẽ khác
    print("Trying relative import for preview...")
    from .livestream_host_window import LivestreamHostWindow
    from .livestream_viewer_window import LivestreamViewerWindow


# Hàm tạo frame ảnh giả để test (thay vì dùng camera thật)
def create_dummy_frame(width, height, frame_count) -> QPixmap:
    """Tạo một QPixmap giả với màu thay đổi theo frame_count."""
    image = QImage(width, height, QImage.Format_RGB888)
    
    # Tạo màu dựa trên frame_count để thấy sự thay đổi
    # Điều chỉnh các giá trị màu (0-255)
    r = (frame_count * 10) % 256
    g = (frame_count * 5 + 50) % 256
    b = (frame_count * 2 + 100) % 256
    color = QColor(r, g, b)
    image.fill(color)
    
    # (Tùy chọn) Vẽ thêm text để biết là frame nào
    # from PySide6.QtGui import QPainter, QPen
    # painter = QPainter(image)
    # painter.setPen(QPen(Qt.white))
    # painter.setFont(QFont("Arial", 20))
    # painter.drawText(image.rect(), Qt.AlignCenter, f"Frame {frame_count}")
    # painter.end()
    
    return QPixmap.fromImage(image)

class PreviewApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Livestream Windows Preview")
        self.layout = QHBoxLayout(self)

        self.host_window: LivestreamHostWindow | None = None
        self.viewer_window: LivestreamViewerWindow | None = None
        
        # Biến để mô phỏng việc gửi frame
        self.frame_counter = 0
        self.timer_send_frame = None


        # Nút để mở cửa sổ Host
        self.btn_show_host = QPushButton("Mở Host Window")
        self.btn_show_host.clicked.connect(self.show_host_window)
        self.layout.addWidget(self.btn_show_host)

        # Nút để mở cửa sổ Viewer
        self.btn_show_viewer = QPushButton("Mở Viewer Window")
        self.btn_show_viewer.clicked.connect(self.show_viewer_window)
        self.layout.addWidget(self.btn_show_viewer)

        self.resize(400, 100)

    def show_host_window(self):
        if self.host_window and self.host_window.isVisible():
            self.host_window.raise_()
            self.host_window.activateWindow()
            return

        streamer_name = "Host Preview User" # Tên host giả
        self.host_window = LivestreamHostWindow(streamer_name, self) # self ở đây là parent
        
        # Kết nối signal stop của host window (nếu cần xử lý gì đó ở preview)
        self.host_window.stop_livestream_requested.connect(self.on_host_stop_requested)
        
        # Bắt đầu gửi frame giả lập cho host preview
        self.start_sending_dummy_frames_to_host()

        # self.host_window.show() # show() là non-blocking
        self.host_window.exec() # exec() là blocking, tốt hơn cho dialog
        
        # Khi dialog host đóng (sau exec), dừng gửi frame
        self.stop_sending_dummy_frames()


    def show_viewer_window(self):
        if self.viewer_window and self.viewer_window.isVisible():
            self.viewer_window.raise_()
            self.viewer_window.activateWindow()
            return

        streamer_name = "Streamer Name Example" # Tên người đang stream giả
        self.viewer_window = LivestreamViewerWindow(streamer_name, self)
        
        # Kết nối signal stop của viewer window
        self.viewer_window.stop_viewing_requested.connect(self.on_viewer_stop_requested)

        # Bắt đầu gửi frame giả lập cho viewer
        self.start_sending_dummy_frames_to_viewer()
        
        # self.viewer_window.show()
        self.viewer_window.exec()

        self.stop_sending_dummy_frames()


    def start_sending_dummy_frames_to_host(self):
        self.stop_sending_dummy_frames() # Dừng timer cũ nếu có
        if not self.host_window: return

        self.frame_counter = 0
        # Sử dụng QTimer để gửi frame đều đặn
        self.timer_send_frame = self.startTimer(1000 // 15) # Gửi 15 FPS (1000ms / 15)

    def start_sending_dummy_frames_to_viewer(self):
        self.stop_sending_dummy_frames()
        if not self.viewer_window: return

        self.frame_counter = 0
        self.timer_send_frame = self.startTimer(1000 // 15)


    def timerEvent(self, event):
        # Hàm này sẽ được gọi bởi QTimer
        if self.timer_send_frame is None or event.timerId() != self.timer_send_frame:
            return

        dummy_pixmap = create_dummy_frame(640, 480, self.frame_counter)
        self.frame_counter += 1

        if self.host_window and self.host_window.isVisible():
            self.host_window.update_preview_frame(dummy_pixmap)
        
        if self.viewer_window and self.viewer_window.isVisible():
            self.viewer_window.update_viewer_frame(dummy_pixmap)
        
        if not (self.host_window and self.host_window.isVisible()) and \
           not (self.viewer_window and self.viewer_window.isVisible()):
            self.stop_sending_dummy_frames() # Dừng nếu cả 2 cửa sổ đều đóng


    def stop_sending_dummy_frames(self):
        if self.timer_send_frame is not None:
            self.killTimer(self.timer_send_frame)
            self.timer_send_frame = None
            print("Stopped sending dummy frames.")

    def on_host_stop_requested(self):
        print("Host window requested to stop livestream.")
        self.stop_sending_dummy_frames()
        if self.host_window:
            # self.host_window.close() # Dialog sẽ tự đóng khi accept/reject hoặc nhấn nút stop đã gọi accept()
            self.host_window = None 

    def on_viewer_stop_requested(self):
        print("Viewer window requested to stop viewing / or closed.")
        self.stop_sending_dummy_frames()
        if self.viewer_window:
            # self.viewer_window.close()
            self.viewer_window = None

    def closeEvent(self, event):
        # Đảm bảo dừng timer khi cửa sổ preview chính đóng
        self.stop_sending_dummy_frames()
        if self.host_window: self.host_window.close()
        if self.viewer_window: self.viewer_window.close()
        super().closeEvent(event)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    # Thêm try-except cho numpy import nếu cần
    try:
        import numpy as np
    except ImportError:
        QMessageBox.critical(None, "Lỗi Import", "Vui lòng cài đặt thư viện numpy: pip install numpy")
        sys.exit(1)
        
    preview_win = PreviewApp()
    preview_win.show()
    sys.exit(app.exec())