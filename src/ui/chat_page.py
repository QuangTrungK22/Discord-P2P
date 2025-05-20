# src/ui/chat_page.py
import sys
import os
from typing import List, Dict, Any, Optional # Thêm Optional nếu cần
import html

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
                               QPushButton, QFrame, QListWidget, QTextEdit, QComboBox,
                               QSpacerItem, QSizePolicy, QListWidgetItem, QMessageBox, QInputDialog)
from PySide6.QtCore import Signal, Slot, Qt
from PySide6.QtGui import QColor

from src.models.message import Message
from src.models.channel import Channel
from src.utils.logger import log_event # Đảm bảo đã import


class ChatPage(QWidget):
    send_message_requested = Signal(str)
    channel_selected = Signal(str)
    create_channel_requested = Signal(str)
    join_channel_requested = Signal(str)
    logout_requested = Signal()
    status_changed = Signal(str)
    leave_channel_requested = Signal(str)
    request_start_livestream = Signal()
    request_view_livestream = Signal(str, str)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.controller = None
        self._setup_ui()
        self.online_text_color = QColor(60, 179, 113)
        self.offline_text_color = Qt.GlobalColor.yellow
        log_event("[UI][ChatPage] Initialized.")

    def set_controller(self, controller):
        self.controller = controller
        log_event("[UI][ChatPage] Controller set.")
        # Kết nối signal livestream_status_changed từ controller
        if self.controller and hasattr(self.controller, 'livestream_status_changed'):
            self.controller.livestream_status_changed.connect(self.on_livestream_status_changed)
            log_event("[UI][ChatPage] Đã kết nối controller.livestream_status_changed với ChatPage.on_livestream_status_changed.")


    def _setup_ui(self):
        main_chat_layout = QHBoxLayout(self)
        main_chat_layout.setContentsMargins(0, 0, 0, 0)
        main_chat_layout.setSpacing(0)

        sidebar_frame = QFrame()
        sidebar_frame.setObjectName("sidebarFrame")
        sidebar_frame.setMinimumWidth(200)
        sidebar_frame.setMaximumWidth(250)
        sidebar_layout = QVBoxLayout(sidebar_frame)
        sidebar_layout.setContentsMargins(5, 5, 5, 5)
        sidebar_frame.setStyleSheet("""
            QFrame#sidebarFrame { background-color: #2f3136; border-right: 1px solid #202225;}
            QLabel { color: #b9bbbe; font-size: 11pt; margin-bottom: 5px; margin-top: 10px; font-weight: bold; }
            QListWidget { background-color: #2f3136; color: #dcddde; border: none; font-size: 10pt; }
            QListWidget::item { padding: 6px 8px; border-radius: 4px; }
            QListWidget::item:selected { background-color: #4f545c; color: #ffffff; }
            QListWidget::item:hover { background-color: #393c43; }
            QPushButton#channelActionButton {
                 background-color: #4f545c; color: #ffffff; font-weight: bold;
                 text-align: center; margin-top: 5px; margin-bottom: 5px; border: none;
                 padding: 8px; border-radius: 4px; font-size: 10pt;
            }
            QPushButton#channelActionButton:hover { background-color: #5a5e66; }
            QPushButton#channelActionButton:pressed { background-color: #4a4e55; }
            QPushButton#createHostButton {
                background-color: #3ba55c; color: #ffffff; font-weight: bold;
                text-align: center; margin-top: 10px; margin-bottom: 10px; border: none;
                padding: 8px; border-radius: 4px; font-size: 10pt;
            }
            QPushButton#createHostButton:hover { background-color: #2d8a4c; }
            QPushButton#createHostButton:pressed { background-color: #257a3f; }
            QFrame#userInfoFrame {
                border-top: 1px solid #4f545c; padding-top: 8px; background-color: #292b2f;
            }
            QLabel#userInfoLabel {
                font-weight: bold; color: #ffffff; margin-bottom: 5px; margin-top: 0; font-size: 10pt;
            }
            QComboBox#statusComboBox {
                background-color: #40444b; color: #ffffff; border-radius: 4px;
                padding: 6px; min-width: 70px; border: 1px solid #202225; font-size: 9pt;
            }
            QComboBox#statusComboBox::drop-down { border: none; }
            QComboBox#statusComboBox QAbstractItemView {
                background-color: #2f3136; color: #ffffff; selection-background-color: #5865f2;
                border: 1px solid #202225; outline: 0px;
            }
            QComboBox#statusComboBox::down-arrow { image: none; }
            QPushButton#logoutButton {
                background-color: #ed4245; color: #ffffff; border-radius: 4px;
                padding: 6px 10px; font-size: 9pt; max-width: 90px; border: none;
                text-align: center;
            }
            QPushButton#logoutButton:hover { background-color: #c03737; }
            QPushButton#logoutButton:pressed { background-color: #b02a2d; }
            QPushButton#livestreamButton {
                background-color: #5865f2; color: #ffffff; font-weight: bold;
                border: none; padding: 8px; border-radius: 4px; font-size: 10pt;
                margin-top: 5px;
            }
            QPushButton#livestreamButton:hover { background-color: #4752c4; }
            QPushButton#livestreamButton:disabled { background-color: #72767d; color: #adafb6;}
            QLabel#currentStreamerLabel {
                color: #22a0f2; font-size: 9pt; font-weight: bold; margin-top: 5px;
                padding: 4px; background-color: #202225; border-radius: 3px;
                text-align: center;
            }
        """)

        self.channels_label = QLabel("KÊNH ĐÃ THAM GIA")
        sidebar_layout.addWidget(self.channels_label)
        self.channel_list = QListWidget()
        self.channel_list.setObjectName("channelListWidget")
        sidebar_layout.addWidget(self.channel_list)

        self.leave_channel_button = QPushButton("Rời Kênh")
        self.leave_channel_button.setObjectName("channelActionButton")
        sidebar_layout.addWidget(self.leave_channel_button)

        self.join_channel_button = QPushButton("Tham gia Kênh")
        self.join_channel_button.setObjectName("channelActionButton")
        sidebar_layout.addWidget(self.join_channel_button)

        self.hosting_label = QLabel("KÊNH CỦA TÔI")
        sidebar_layout.addWidget(self.hosting_label)
        self.hosting_list = QListWidget()
        self.hosting_list.setObjectName("hostingListWidget")
        sidebar_layout.addWidget(self.hosting_list)

        self.create_channel_button = QPushButton("+ Tạo Kênh")
        self.create_channel_button.setObjectName("createHostButton")
        sidebar_layout.addWidget(self.create_channel_button)

        sidebar_layout.addStretch()

        user_info_frame = QFrame()
        user_info_frame.setObjectName("userInfoFrame")
        user_info_layout = QVBoxLayout(user_info_frame)
        user_info_layout.setContentsMargins(8, 0, 8, 8)
        self.user_info_label = QLabel("Tên người dùng")
        self.user_info_label.setObjectName("userInfoLabel")
        user_info_layout.addWidget(self.user_info_label)
        status_layout = QHBoxLayout()
        self.status_combobox = QComboBox()
        self.status_combobox.setObjectName("statusComboBox")
        self.status_combobox.addItems(["Online", "Invisible", "Away"]) # Thêm "Away" nếu cần
        status_layout.addWidget(self.status_combobox)
        status_layout.addSpacerItem(QSpacerItem(5, 0, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum))
        self.logout_button = QPushButton("Đăng xuất")
        self.logout_button.setObjectName("logoutButton")
        status_layout.addWidget(self.logout_button)
        status_layout.addStretch()
        user_info_layout.addLayout(status_layout)
        sidebar_layout.addWidget(user_info_frame)

        main_chat_layout.addWidget(sidebar_frame)

        chat_frame = QFrame()
        chat_frame.setObjectName("chatFrame")
        chat_frame_layout = QVBoxLayout(chat_frame)
        chat_frame_layout.setContentsMargins(0, 0, 0, 0)
        chat_frame_layout.setSpacing(0)
        chat_frame.setStyleSheet("""
            QFrame#chatFrame { background-color: #36393f; }
            QLabel#channelNameLabel {
                font-size: 15pt; font-weight: bold; padding: 10px 15px;
                color: #ffffff; border-bottom: 1px solid #202225;
                background-color: #36393f;
            }
            QFrame#chatHeader { background-color: #36393f; }
            QTextEdit#messageDisplay {
                background-color: #36393f; color: #dcddde; border: none;
                padding: 10px 15px; font-size: 10pt;
            }
            QLineEdit#messageInput {
                background-color: #40444b; border-radius: 8px; padding: 10px 15px;
                color: #dcddde; font-size: 10pt; border: none;
                margin: 0 10px 0 15px;
            }
            QLineEdit#messageInput:focus { background-color: #484c54; }
            QPushButton#sendButton {
                background-color: #5865f2; color: #ffffff; border-radius: 8px;
                padding: 10px 18px; font-size: 10pt; font-weight: bold;
                min-width: 60px; border: none; margin-right: 15px;
            }
            QPushButton#sendButton:hover { background-color: #4752c4; }
            QPushButton#sendButton:pressed { background-color: #3c45a5; }
            QFrame#inputFrame {
                 background-color: #36393f; border-top: 1px solid #40444b;
                 padding-top: 10px; padding-bottom: 10px;
            }
        """)

        chat_header_frame = QFrame()
        chat_header_frame.setObjectName("chatHeader")
        self.chat_header_layout = QHBoxLayout(chat_header_frame)
        self.chat_header_layout.setContentsMargins(0,0,15,0)
        self.chat_header_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        self.channel_name_label = QLabel("Chọn một kênh")
        self.channel_name_label.setObjectName("channelNameLabel")
        self.chat_header_layout.addWidget(self.channel_name_label, 1)

        livestream_controls_layout = QVBoxLayout()
        livestream_controls_layout.setSpacing(2)
        self.livestream_button = QPushButton("Livestream") # Text ban đầu
        self.livestream_button.setObjectName("livestreamButton")
        self.livestream_button.setCheckable(False) # Không cần checkable nếu quản lý state qua text và enabled
        self.livestream_button.clicked.connect(self._on_livestream_button_clicked)
        livestream_controls_layout.addWidget(self.livestream_button)
        self.current_streamer_label = QLabel("")
        self.current_streamer_label.setObjectName("currentStreamerLabel")
        self.current_streamer_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        livestream_controls_layout.addWidget(self.current_streamer_label)
        self.chat_header_layout.addLayout(livestream_controls_layout)
        chat_frame_layout.addWidget(chat_header_frame)

        self.message_display = QTextEdit()
        self.message_display.setObjectName("messageDisplay")
        self.message_display.setReadOnly(True)
        chat_frame_layout.addWidget(self.message_display)

        input_frame = QFrame()
        input_frame.setObjectName("inputFrame")
        message_input_layout = QHBoxLayout(input_frame)
        message_input_layout.setContentsMargins(0,0,0,0)
        message_input_layout.setSpacing(0)
        self.message_input = QLineEdit()
        self.message_input.setObjectName("messageInput")
        self.message_input.setPlaceholderText("Nhập tin nhắn...")
        message_input_layout.addWidget(self.message_input)
        self.send_button = QPushButton("Gửi")
        self.send_button.setObjectName("sendButton")
        message_input_layout.addWidget(self.send_button)
        chat_frame_layout.addWidget(input_frame)
        main_chat_layout.addWidget(chat_frame, 1)

        user_list_frame = QFrame()
        user_list_frame.setObjectName("userListFrame")
        user_list_frame.setMinimumWidth(180)
        user_list_frame.setMaximumWidth(200)
        user_list_layout = QVBoxLayout(user_list_frame)
        user_list_layout.setContentsMargins(0, 5, 5, 5)
        user_list_layout.setSpacing(0)
        user_list_frame.setStyleSheet("""
            QFrame#userListFrame { background-color: #2f3136; border-left: 1px solid #202225;}
            QLabel#memberListLabel {
                color: #96989d; font-size: 10pt; font-weight: bold;
                margin: 8px 8px 3px 8px; text-transform: uppercase;
            }
            QListWidget#memberListWidget {
                background-color: #2f3136; border: none;
                font-size: 10pt; padding-left: 0px;
            }
            QListWidget#memberListWidget::item:selected {
                 background-color: #393c43;
            }
        """)

        self.member_list_label = QLabel("THÀNH VIÊN")
        self.member_list_label.setObjectName("memberListLabel")
        user_list_layout.addWidget(self.member_list_label)
        self.member_list_widget = QListWidget()
        self.member_list_widget.setObjectName("memberListWidget")
        user_list_layout.addWidget(self.member_list_widget)
        user_list_layout.addStretch()
        main_chat_layout.addWidget(user_list_frame)

        self.send_button.clicked.connect(self._on_send_clicked)
        self.message_input.returnPressed.connect(self._on_send_clicked)
        self.channel_list.currentItemChanged.connect(self._on_channel_selected)
        self.hosting_list.currentItemChanged.connect(self._on_channel_selected)
        self.logout_button.clicked.connect(self.logout_requested.emit)
        self.create_channel_button.clicked.connect(self._prompt_create_channel)
        self.join_channel_button.clicked.connect(self._prompt_join_channel)
        self.leave_channel_button.clicked.connect(self._on_leave_channel_clicked)
        self.status_combobox.currentTextChanged.connect(self.status_changed.emit)

        self.is_someone_streaming = False
        self.current_streamer_id_in_channel: Optional[str] = None
        self.current_streamer_name_in_channel: Optional[str] = None
        self.livestream_button.setEnabled(False)
        self.current_streamer_label.setText("")
        self.current_streamer_label.setVisible(False) # Ẩn label ban đầu

    @Slot(Message)
    def display_message_object(self, msg: Message):
        sender = msg.sender_display_name or f"User_{msg.user_id[:6]}"
        timestamp_str = msg.get_formatted_timestamp("%H:%M") if hasattr(msg, 'get_formatted_timestamp') else "timestamp"
        escaped_content = html.escape(msg.content) if msg.content else ""
        content_html = escaped_content.replace('\n', '<br/>')
        formatted_message = f"""
        <div style='margin-bottom: 2px; padding-left: 0px; padding-top: 5px;'>
            <span style='color: #FFFFFF; font-weight: 550;'>{html.escape(sender)}</span>
            <span style='color: #a3a6aa; font-size: 9pt; margin-left: 8px;'>{timestamp_str}</span>
        </div>
        <div style='margin-bottom: 8px; padding-left: 0px; color: #dcddde; line-height: 1.4;'>
            {content_html}
        </div>
        """
        self.message_display.append(formatted_message)
        scrollbar = self.message_display.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    @Slot()
    def clear_message_display(self):
        self.message_display.clear()

    @Slot(str)
    def set_current_channel_name(self, name: str):
        self.channel_name_label.setText(name if name else "Chọn một kênh")
        if self.controller and self.controller.current_channel:
            self.on_livestream_status_changed(False, "", "") # Reset khi chuyển kênh
        else:
            self.livestream_button.setText("Livestream")
            self.livestream_button.setEnabled(False)
            self.current_streamer_label.setText("")
            self.current_streamer_label.setVisible(False)
            self.is_someone_streaming = False
            self.current_streamer_id_in_channel = None
            self.current_streamer_name_in_channel = None

    @Slot(list, list)
    def update_channel_lists(self, joined_channels: List[Channel], hosted_channels: List[Channel]):
        log_event(f"[UI][ChatPage] update_channel_lists called. Joined: {len(joined_channels)}, Hosted: {len(hosted_channels)}")
        current_selection_id = None
        selected_item = self.channel_list.currentItem()
        if not selected_item:
            selected_item = self.hosting_list.currentItem()
        if selected_item:
            channel_data = selected_item.data(Qt.UserRole)
            if isinstance(channel_data, Channel):
                current_selection_id = channel_data.id
        self._update_list_widget(self.channel_list, joined_channels, current_selection_id)
        self._update_list_widget(self.hosting_list, hosted_channels, current_selection_id)
        self.channels_label.setText(f"KÊNH ĐÃ THAM GIA ({len(joined_channels)})")
        self.hosting_label.setText(f"KÊNH CỦA TÔI ({len(hosted_channels)})")

    def _update_list_widget(self, list_widget: QListWidget, channels: List[Channel], current_selection_id: Optional[str]):
        list_widget.blockSignals(True)
        list_widget.clear()
        log_event(f"[UI][ChatPage] Updating list widget '{list_widget.objectName()}' with {len(channels)} channels.")
        item_to_select = None
        for channel in channels:
            if isinstance(channel, Channel):
                item = QListWidgetItem(channel.name)
                item.setToolTip(f"ID: {channel.id}\nOwner: {channel.owner_id}")
                item.setData(Qt.UserRole, channel)
                list_widget.addItem(item)
                if channel.id == current_selection_id:
                    item_to_select = item
            else:
                log_event(f"[WARN][UI][ChatPage] Invalid channel data type found: {type(channel)} for widget '{list_widget.objectName()}'")
        list_widget.blockSignals(False)
        if item_to_select:
            list_widget.setCurrentItem(item_to_select)
            log_event(f"[UI][ChatPage] Restored selection for channel '{item_to_select.text()}' in '{list_widget.objectName()}'.")

    @Slot(list)
    def update_member_list_ui(self, members_info: List[Dict[str, Any]]):
        self.member_list_widget.clear()
        log_event(f"[UI][ChatPage] update_member_list_ui called with {len(members_info)} member infos.")
        members_info.sort(key=lambda m: (
            not m.get('is_online', False),
            (m.get('display_name') or f"User_{m.get('user_id', '')[:6]}").lower()
        ))
        valid_member_count = 0
        for member_data in members_info:
            user_id = member_data.get("user_id")
            if not user_id:
                log_event("[WARN][UI][ChatPage] Member data missing user_id in update_member_list_ui.")
                continue
            display_name = member_data.get("display_name") or f"User_{user_id[:6]}"
            is_online_profile_status = member_data.get("is_online", False)
            has_p2p = member_data.get("has_p2p_activity", False) # Thêm dòng này
            actual_db_status = member_data.get("actual_status", "offline") # Thêm dòng này

            item = QListWidgetItem(display_name)
            tooltip_text = f"User ID: {user_id}\nStatus: {actual_db_status}"
            if is_online_profile_status and has_p2p : # Chỉ thêm (P2P Active) nếu user online theo DB và có P2P
                tooltip_text += " (P2P Active)"
            item.setToolTip(tooltip_text)

            item.setData(Qt.UserRole, member_data)
            if is_online_profile_status: # Màu dựa trên is_online (tức profiles.status == 'online')
                 item.setForeground(self.online_text_color) # Màu xanh lá mặc định cho online
                 # Có thể thêm logic đổi màu nếu has_p2p (vd: màu xanh dương)
                 # if has_p2p: item.setForeground(QColor(Qt.GlobalColor.blue))
            else:
                 item.setForeground(self.offline_text_color) # Màu vàng cho các trạng thái khác

            self.member_list_widget.addItem(item)
            valid_member_count +=1
        self.member_list_label.setText(f"THÀNH VIÊN — {valid_member_count}")
        log_event(f"[UI][ChatPage] Member list UI updated with {valid_member_count} members.")

    @Slot(str)
    def update_user_info_display(self, display_name: str):
        self.user_info_label.setText(display_name if display_name else "Không xác định")
        self.user_info_label.setToolTip(f"Logged in as: {display_name}")

    def clear_all(self):
        self.message_display.clear()
        self.channel_list.clear()
        self.hosting_list.clear()
        self.member_list_widget.clear()
        self.message_input.clear()
        self.channel_name_label.setText("Chọn một kênh")
        self.channels_label.setText("KÊNH ĐÃ THAM GIA")
        self.hosting_label.setText("KÊNH CỦA TÔI")
        self.member_list_label.setText("THÀNH VIÊN")
        self.user_info_label.setText("Tên người dùng")
        self.livestream_button.setText("Livestream")
        self.livestream_button.setEnabled(False)
        self.current_streamer_label.setText("")
        self.current_streamer_label.setVisible(False)
        self.is_someone_streaming = False
        self.current_streamer_id_in_channel = None
        self.current_streamer_name_in_channel = None
        log_event("[UI][ChatPage] ChatPage UI cleared.")

    def _on_send_clicked(self):
        text = self.message_input.text().strip()
        if text:
            log_event(f"[UI][ChatPage] Send button clicked. Emitting signal for: '{text[:30]}...'")
            self.send_message_requested.emit(text)
            self.message_input.clear()
        else:
             log_event("[UI][ChatPage] Send button clicked. Message is empty, not sending.")

    def _on_channel_selected(self, current: Optional[QListWidgetItem], previous: Optional[QListWidgetItem]):
        selected_channel_id = None
        selected_channel_name = "Chọn một kênh"
        sender_list = self.sender()
        other_list = self.hosting_list if sender_list == self.channel_list else self.channel_list

        if current:
            channel_data = current.data(Qt.UserRole)
            if isinstance(channel_data, Channel):
                selected_channel_id = channel_data.id
                selected_channel_name = channel_data.name
                log_event(f"[UI][ChatPage] Channel selected: Name='{selected_channel_name}', ID='{selected_channel_id}' from list '{sender_list.objectName()}'")
                if other_list and other_list.currentItem():
                     other_list.blockSignals(True)
                     other_list.setCurrentItem(None)
                     other_list.blockSignals(False)
            else:
                 log_event(f"[WARN][UI][ChatPage] Invalid data (not Channel object) in selected item of '{sender_list.objectName()}'. Data: {channel_data}")
        else:
             log_event(f"[UI][ChatPage] Channel deselected from list '{sender_list.objectName()}'.")
             if not (other_list and other_list.currentItem()):
                 self.set_current_channel_name(selected_channel_name)
                 self.channel_selected.emit("")
                 self.member_list_widget.clear()
                 self.member_list_label.setText("THÀNH VIÊN")
                 self.livestream_button.setText("Livestream")
                 self.livestream_button.setEnabled(False)
                 self.current_streamer_label.setText("")
                 self.current_streamer_label.setVisible(False)
                 self.is_someone_streaming = False
                 self.current_streamer_id_in_channel = None
                 self.current_streamer_name_in_channel = None
        if selected_channel_id:
             self.channel_selected.emit(selected_channel_id)
             # Khi kênh thay đổi, gọi on_livestream_status_changed để reset nút
             self.on_livestream_status_changed(False, "", "")

    def _prompt_create_channel(self):
        channel_name, ok = QInputDialog.getText(self, "Tạo Kênh Mới", "Nhập tên kênh:")
        if ok and channel_name.strip():
            log_event(f"[UI][ChatPage] User requested to create channel: '{channel_name.strip()}'")
            self.create_channel_requested.emit(channel_name.strip())
        elif ok:
             QMessageBox.warning(self, "Lỗi Tạo Kênh", "Tên kênh không được để trống.")
        else:
            log_event("[UI][ChatPage] User cancelled channel creation.")

    def _prompt_join_channel(self):
        channel_id, ok = QInputDialog.getText(self, "Tham Gia Kênh", "Nhập ID kênh:")
        if ok and channel_id.strip():
            log_event(f"[UI][ChatPage] User requested to join channel: '{channel_id.strip()}'")
            self.join_channel_requested.emit(channel_id.strip())
        elif ok:
             QMessageBox.warning(self, "Lỗi Tham Gia Kênh", "ID kênh không được để trống.")
        else:
            log_event("[UI][ChatPage] User cancelled joining channel.")

    def _on_leave_channel_clicked(self):
        current_channel_item = self.channel_list.currentItem()
        if current_channel_item:
            channel_data = current_channel_item.data(Qt.UserRole)
            if isinstance(channel_data, Channel):
                 reply = QMessageBox.question(self, "Rời Kênh",
                                              f"Bạn có chắc chắn muốn rời kênh '{channel_data.name}' không?",
                                              QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                              QMessageBox.StandardButton.No)
                 if reply == QMessageBox.StandardButton.Yes:
                     log_event(f"[UI][ChatPage] User confirmed to leave channel: ID='{channel_data.id}', Name='{channel_data.name}'")
                     self.leave_channel_requested.emit(channel_data.id)
                 else:
                     log_event(f"[UI][ChatPage] User cancelled leaving channel: '{channel_data.name}'")
            else:
                QMessageBox.warning(self, "Lỗi", "Dữ liệu kênh không hợp lệ.")
                log_event(f"[WARN][UI][ChatPage] Invalid data for selected item in channel_list for leaving.")
        else:
            QMessageBox.information(self, "Thông Báo", "Vui lòng chọn một kênh trong danh sách 'Kênh Đã Tham Gia' để rời.")
            log_event("[UI][ChatPage] Leave channel clicked but no joined channel selected.")

    def _on_livestream_button_clicked(self):
        if not self.controller or not self.controller.current_user or not self.controller.current_channel:
            log_event("[UI][ChatPage] Livestream button clicked but controller, user, or channel not available.")
            return

        current_user_id = self.controller.current_user.id

        if self.is_someone_streaming:
            if self.current_streamer_id_in_channel == current_user_id:
                log_event(f"[UI][ChatPage] User '{current_user_id}' (current streamer) clicked 'Stop Livestream'. Livestream should be stopped via HostWindow.")
                # Nút này thực tế sẽ bị disable khi user đang stream, việc dừng là từ cửa sổ host
            elif self.current_streamer_id_in_channel and self.current_streamer_name_in_channel:
                log_event(f"[UI][ChatPage] User '{current_user_id}' preparing to emit request_view_livestream for '{self.current_streamer_name_in_channel}' (ID: {self.current_streamer_id_in_channel}).")
                self.request_view_livestream.emit(self.current_streamer_id_in_channel, self.current_streamer_name_in_channel)
            else:
                log_event(f"[WARN][UI][ChatPage] Livestream button clicked while someone is streaming, but streamer info is missing.")
        else: # Chưa có ai stream
            log_event(f"[UI][ChatPage] User '{current_user_id}' preparing to emit request_start_livestream for channel '{self.controller.current_channel.id}'.")
            self.request_start_livestream.emit()

    @Slot(bool, str, str)
    def on_livestream_status_changed(self, is_streaming: bool, streamer_id: str, streamer_name: str):
        log_event(f"[UI][ChatPage] Slot on_livestream_status_changed: is_streaming={is_streaming}, streamer_id='{streamer_id}', streamer_name='{streamer_name}'")

        self.is_someone_streaming = is_streaming
        self.current_streamer_id_in_channel = streamer_id if is_streaming else None
        self.current_streamer_name_in_channel = streamer_name if is_streaming else None

        if not self.controller or not self.controller.current_channel:
            self.livestream_button.setText("Livestream")
            self.livestream_button.setEnabled(False)
            self.current_streamer_label.setText("")
            self.current_streamer_label.setVisible(False)
            log_event("[UI][ChatPage] No current channel, disabling livestream button and hiding label.")
            return

        current_user_id = self.controller.current_user.id if self.controller.current_user else None

        if is_streaming:
            self.current_streamer_label.setText(f"LIVE: {streamer_name}")
            self.current_streamer_label.setVisible(True)
            if current_user_id and streamer_id == current_user_id:
                # User hiện tại đang stream
                self.livestream_button.setText("Đang Livestream...")
                self.livestream_button.setEnabled(False) # Vô hiệu hóa, việc dừng sẽ qua cửa sổ host
                log_event(f"[UI][ChatPage] Current user '{current_user_id}' is streaming. Button set to 'Đang Livestream...' and disabled.")
            else:
                # Người khác đang stream
                self.livestream_button.setText(f"Xem Stream của {streamer_name}")
                self.livestream_button.setEnabled(True)
                log_event(f"[UI][ChatPage] Streamer '{streamer_name}' is live. Button set to 'Xem Stream...' and enabled.")
        else: # Không có ai stream
            self.current_streamer_label.setText("")
            self.current_streamer_label.setVisible(False)
            
            can_stream_in_current_channel = False
            if self.controller.current_channel and current_user_id:
                # Ví dụ: chỉ chủ kênh mới được stream
                if self.controller.current_channel.owner_id == current_user_id:
                    can_stream_in_current_channel = True
                # Hoặc có thể thêm logic kiểm tra quyền stream phức tạp hơn từ controller
                # can_stream_in_current_channel = self.controller.can_user_stream(current_user_id, self.controller.current_channel.id)

            if can_stream_in_current_channel:
                self.livestream_button.setText("Bắt đầu Livestream")
                self.livestream_button.setEnabled(True)
                log_event(f"[UI][ChatPage] No stream. Current user '{current_user_id}' can stream. Button set to 'Bắt đầu Livestream' and enabled.")
            else:
                self.livestream_button.setText("Livestream") # Hoặc "Không có quyền"
                self.livestream_button.setEnabled(False) # Người dùng không thể stream trong kênh này
                log_event(f"[UI][ChatPage] No stream. Current user '{current_user_id}' cannot stream in this channel. Button disabled.")