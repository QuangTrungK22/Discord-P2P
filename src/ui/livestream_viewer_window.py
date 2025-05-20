# src/ui/livestream_viewer_window.py
from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel
from PySide6.QtGui import QPixmap
from PySide6.QtCore import Slot, Qt, Signal

class LivestreamViewerWindow(QDialog):
    stop_viewing_requested = Signal() # Nếu viewer muốn chủ động đóng

    def __init__(self, streamer_name: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Đang xem Livestream của {streamer_name}")
        self.setMinimumSize(640, 480)
        
        self.layout = QVBoxLayout(self)
        self.video_label = QLabel("Đang kết nối đến stream...")
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setStyleSheet("background-color: black; color: white;")
        self.layout.addWidget(self.video_label, 1)
        
        # Có thể thêm nút "Dừng xem" nếu muốn
        # self.stop_button = QPushButton("Dừng xem")
        # self.stop_button.clicked.connect(self._on_stop_viewing)
        # self.layout.addWidget(self.stop_button)

    @Slot(QPixmap)
    def update_viewer_frame(self, pixmap: QPixmap):
        if not pixmap.isNull():
            self.video_label.setPixmap(pixmap.scaled(self.video_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            self.video_label.setText("Stream bị lỗi hoặc đã kết thúc.")

    # def _on_stop_viewing(self):
    #     self.stop_viewing_requested.emit()
    #     self.accept()

    def closeEvent(self, event):
        self.stop_viewing_requested.emit() # Báo cho service biết là đã đóng cửa sổ
        super().closeEvent(event)