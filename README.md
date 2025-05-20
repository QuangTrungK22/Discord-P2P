# Địa Thư - Ứng dụng Giao tiếp P2P (Đồ án Mạng Máy Tính)

## Giới thiệu

**Địa Thư** là một ứng dụng chat và livestream desktop được phát triển bằng Python, sử dụng kiến trúc mạng ngang hàng (Peer-to-Peer - P2P) kết hợp với backend Supabase để hỗ trợ các tính năng nền tảng. Dự án này được thực hiện như một phần của đồ án môn học Mạng Máy Tính, nhằm mục đích khám phá và triển khai các kỹ thuật giao tiếp P2P, xử lý bất đồng bộ, và tích hợp với dịch vụ backend.

Ứng dụng cho phép người dùng đăng ký/đăng nhập, tạo/tham gia các kênh chat, gửi tin nhắn văn bản trực tiếp P2P, và đặc biệt là tính năng livestream video thời gian thực giữa các thành viên trong kênh.

## Nhóm Sinh viên Thực hiện

* Lâm Quang Trung - 2213686
* Nguyễn Quốc Tuấn Lâm - 2211516

*Trường Đại học Bách Khoa - ĐHQG TP.HCM, Khoa Khoa học và Kỹ thuật Máy tính*
*Giảng viên hướng dẫn: Bùi Xuân Giang*

## Tính năng chính

* **Xác thực Người dùng:** Đăng ký, đăng nhập, đăng xuất an toàn sử dụng Supabase Auth. Quản lý phiên làm việc người dùng.
* **Quản lý Kênh Chat:**
    * Tạo kênh chat mới (dữ liệu lưu trên Supabase).
    * Tham gia vào các kênh chat hiện có.
    * Rời khỏi kênh đã tham gia.
    * Hiển thị danh sách kênh đã tham gia và kênh do người dùng sở hữu.
* **Chat Thời gian thực (P2P):**
    * Gửi và nhận tin nhắn văn bản trực tiếp giữa các thành viên trong kênh thông qua kết nối P2P.
    * Lịch sử chat được lưu trữ cục bộ bằng SQLite (đặc biệt cho host kênh).
    * Tin nhắn được sao lưu lên Supabase để các thành viên khác có thể truy cập lịch sử.
* **Livestream Video (P2P):**
    * **Host Livestream:** Người dùng có thể phát video trực tiếp từ webcam của mình tới các peer khác trong kênh.
    * **View Livestream:** Người dùng có thể xem luồng video đang được phát bởi một thành viên khác.
    * Sử dụng giao thức P2P tùy chỉnh để truyền tải dữ liệu video frame và tín hiệu điều khiển.
* **Khám phá Peer:** Sử dụng Supabase làm "tracker" trung gian để các peer đăng ký thông tin (IP, port, user\_id, last\_seen\_at) và tìm thấy nhau.
* **Quản lý Trạng thái Người dùng:** Cho phép người dùng cập nhật và hiển thị trạng thái (Online, Offline, Invisible). Trạng thái được lưu trên Supabase.
* **Giao diện Người dùng:** Xây dựng bằng PySide6, cung cấp trải nghiệm trực quan và tương tác cho các chức năng.
* **Logging:** Ghi lại các sự kiện hoạt động, lỗi và thông tin gỡ lỗi của ứng dụng vào file `logs/app.log`.

## Kiến trúc Hệ thống

Ứng dụng sử dụng kiến trúc **Hybrid (Lai ghép)**:

* **Peer-to-Peer (P2P):** Là phương thức giao tiếp chính cho các hoạt động thời gian thực như chat và livestream. Dữ liệu được truyền trực tiếp giữa các client (Peer).
* **Client-Backend (Supabase):**
    * **Supabase Auth:** Xử lý toàn bộ quá trình xác thực người dùng.
    * **Supabase Database (PostgreSQL):**
        * Lưu trữ thông tin người dùng (bảng `profiles`), thông tin kênh (bảng `channels`), danh sách thành viên (bảng `channel_members`).
        * Hoạt động như một "registry/tracker" cho việc khám phá peer (bảng `peers`).
        * Sao lưu tin nhắn chat (bảng `messages`).

Sơ đồ kiến trúc và các sơ đồ thiết kế chi tiết khác (Use Case, Class Diagram, Activity Diagram) được hiện thực trong báo cáo dự án

Sơ lượt về UI của dự án:
![](C:\Users\win\BTL1-MMT-242\hoantatlivestream\hoantatlivestream\images\main_UI.png "Giao diện Main_UI")

![](C:\Users\win\BTL1-MMT-242\hoantatlivestream\hoantatlivestream\images\Screenshot 2025-05-20 181224.png "Giao diện đăng ký")

![](C:\Users\win\BTL1-MMT-242\hoantatlivestream\hoantatlivestream\images\Screenshot 2025-05-20 181506.png "Giao diện Host Livestream")

## Công nghệ sử dụng

* **Ngôn ngữ:** Python (phiên bản 3.8+)
* **Giao diện người dùng (GUI):** PySide6
* **Lập trình bất đồng bộ:** `asyncio`, `qasync`
* **Backend:** Supabase (Authentication, PostgreSQL Database)
    * Thư viện tương tác: `supabase-py`
* **Lưu trữ cục bộ:** SQLite (thông qua `sqlite3` của Python)
* **Giao tiếp P2P:** Socket TCP cơ bản (qua `asyncio.start_server`, `asyncio.open_connection`)
* **Định dạng dữ liệu P2P:** JSON (được định nghĩa trong `src/p2p/protocol.py`)
* **Xử lý video (Livestream):** **TODO:** *Xác nhận thư viện cụ thể (ví dụ: OpenCV-Python, NumPy, Pillow) nếu có và thêm vào đây.*
* **Version Control:** Git, GitHub

Hướng dẫn chạy project:
### 1. Yêu cầu tiên quyết:
* Cài đặt [Python](https://www.python.org/downloads/) (phiên bản 3.8 trở lên được khuyến nghị).
* Cài đặt [Git](https://git-scm.com/downloads/).
* (Windows) Có thể cần cài đặt [Microsoft Visual C++ Redistributable](https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist?view=msvc-170) để cài đặt PySide6 thuận lợi.

### 2. Clone Repository:
Mở Terminal (hoặc Command Prompt/PowerShell) và chạy các lệnh sau:
```bash
git clone <https://github.com/QuangTrungK22/Discord-P2P.git>

cd <C:\Users\win\BTL1-MMT-242\hoantatlivestream\hoantatlivestream>

pip install -r requirements.txt
## chạy ứng dụng
python main1.py


