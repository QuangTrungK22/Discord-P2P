# src/ui/livestream_host_window.py
from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton
from PySide6.QtGui import QPixmap
from PySide6.QtCore import Slot, Qt, Signal

class LivestreamHostWindow(QDialog):
    stop_livestream_requested = Signal() # Signal để báo cho LivestreamService dừng

    def __init__(self, streamer_name: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Bạn đang Livestream - {streamer_name}")
        self.setMinimumSize(640, 480)

        self.layout = QVBoxLayout(self)
        self.video_label = QLabel("Đang chờ camera...")
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setStyleSheet("background-color: black; color: white;")
        self.layout.addWidget(self.video_label, 1)

        self.stop_button = QPushButton("Dừng Livestream")
        self.stop_button.clicked.connect(self._on_stop_clicked)
        self.layout.addWidget(self.stop_button)

    @Slot(QPixmap)
    def update_preview_frame(self, pixmap: QPixmap):
        self.video_label.setPixmap(pixmap.scaled(self.video_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def _on_stop_clicked(self):
        self.stop_livestream_requested.emit()
        self.accept() # Hoặc self.close()

    def closeEvent(self, event):
        # Đảm bảo phát signal khi cửa sổ bị đóng bằng nút X
        self.stop_livestream_requested.emit()
        super().closeEvent(event)