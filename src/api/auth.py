# SegmentChatClient/src/api/auth.py
from .client import get_supabase_client
from typing import Optional, Dict, Any
# Giả sử bạn có model User trong src.models.user
# Nếu không, bạn có thể dùng Any hoặc import từ gotrue nếu cần chi tiết hơn
# from gotrue.models import User, Session # Hoặc từ supabase.lib.auth.models
from src.models.user import User # Sử dụng model User của bạn
from gotrue.types import Session # Sử dụng Session từ gotrue
from src.utils.logger import log_event
from gotrue.errors import AuthApiError # Import lỗi cụ thể

# Định nghĩa kiểu trả về chung cho các hàm auth trả về dict
AuthResponse = Dict[str, Any]

async def sign_up(email: str, password: str, display_name: Optional[str] = None) -> AuthResponse:
    """Gọi API đăng ký Supabase (async) với logging chi tiết."""
    log_event(f"[DEBUG][API_AUTH][sign_up] Function started. Email: {email}, DisplayName: {display_name}")
    supabase = get_supabase_client()
    if not supabase:
        log_event("[ERROR][API_AUTH][sign_up] Supabase client not available.")
        return {"success": False, "error": "Supabase client chưa khởi tạo"}
    log_event(f"[DEBUG][API_AUTH][sign_up] Supabase client obtained for {email}.")

    options_data = {}
    if display_name:
        options_data["display_name"] = display_name
        log_event(f"[DEBUG][API_AUTH][sign_up] Added display_name to options for {email}.")

    try:
        payload = {"email": email, "password": password, "options": {"data": options_data}}
        log_event(f"[INFO][API_AUTH][sign_up] Attempting sign up for {email} with payload: {payload}") # Log cả payload

        # === Gọi API ===
        res = await supabase.auth.sign_up(payload)
        # ===============

        log_event(f"[DEBUG][API_AUTH][sign_up] Raw response received for {email}: {repr(res)}") # Log phản hồi thô

        if res.user and res.session:
            log_event(f"[INFO][API_AUTH][sign_up] Sign up successful with session for {email}. User ID: {res.user.id}")
            result = {"success": True, "user": res.user, "session": res.session}
        elif res.user and not res.session:
            log_event(f"[INFO][API_AUTH][sign_up] Sign up successful for {email}, requires email verification. User ID: {res.user.id}")
            result = {"success": True, "needs_verification": True, "user": res.user}
        else:
            log_event(f"[WARN][API_AUTH][sign_up] Sign up for {email} returned unexpected result structure: {repr(res)}")
            result = {"success": False, "error": "Phản hồi đăng ký không mong muốn"}

        log_event(f"[DEBUG][API_AUTH][sign_up] Function finished for {email}.")
        return result

    except AuthApiError as e:
        log_event(f"[ERROR][API_AUTH][sign_up] AuthApiError for {email}. Type: {type(e).__name__}, Status: {e.status}, Message: {e.message}")
        error_message = f"Lỗi API ({e.status}): {e.message}"
        if e.status == 400:
             if "already registered" in e.message.lower(): error_message = "Email này đã được đăng ký."
             elif "Password should be at least 6 characters" in e.message: error_message = "Mật khẩu phải có ít nhất 6 ký tự."
             else: error_message = f"Dữ liệu không hợp lệ: {e.message}"
        elif e.status == 429:
             error_message = "Bạn đã gửi quá nhiều yêu cầu, vui lòng thử lại sau."

        log_event(f"[DEBUG][API_AUTH][sign_up] Function finished with error for {email}.")
        return {"success": False, "error": error_message}
    except Exception as e:
        # Bắt các lỗi khác không phải AuthApiError (ví dụ: TypeError nếu có)
        log_event(f"[ERROR][API_AUTH][sign_up] Unexpected error for {email}. Type: {type(e).__name__}, Error: {e}", exc_info=True) # Thêm exc_info=True để log cả traceback
        log_event(f"[DEBUG][API_AUTH][sign_up] Function finished with unexpected error for {email}.")
        return {"success": False, "error": f"Lỗi không xác định: {type(e).__name__} - {e}"}


async def sign_in(email: str, password: str) -> AuthResponse:
    """Gọi API đăng nhập Supabase (async) với logging chi tiết."""
    log_event(f"[DEBUG][API_AUTH][sign_in] Function started for email: {email}")
    supabase = get_supabase_client()
    if not supabase:
        log_event("[ERROR][API_AUTH][sign_in] Supabase client not available.")
        return {"success": False, "error": "Supabase client chưa khởi tạo"}
    log_event(f"[DEBUG][API_AUTH][sign_in] Supabase client obtained for {email}.")

    try:
        payload = {"email": email, "password": password}
        log_event(f"[INFO][API_AUTH][sign_in] Attempting sign in for {email}") # Không log password ở đây

        # === Gọi API ===
        res = await supabase.auth.sign_in_with_password(payload)
        # ===============

        # Log phản hồi thô NGAY LẬP TỨC để kiểm tra kiểu dữ liệu và cấu trúc
        log_event(f"[DEBUG][API_AUTH][sign_in] Raw response received: Type={type(res)}, Value={repr(res)}")

        if res and hasattr(res, 'user') and hasattr(res, 'session') and res.user and res.session:
            log_event(f"[INFO][API_AUTH][sign_in] Sign in successful for user {res.user.id}.")
            result = {"success": True, "user": res.user, "session": res.session}
        else:
            # Log chi tiết hơn về cấu trúc không mong đợi
            user_info = f"User: {repr(res.user)}" if hasattr(res, 'user') else "User attribute missing"
            session_info = f"Session: {repr(res.session)}" if hasattr(res, 'session') else "Session attribute missing"
            log_event(f"[WARN][API_AUTH][sign_in] Sign in for {email} returned unexpected result structure. {user_info}, {session_info}. Full response: {repr(res)}")
            result = {"success": False, "error": "Phản hồi đăng nhập không mong muốn hoặc thiếu thông tin"}

        log_event(f"[DEBUG][API_AUTH][sign_in] Function finished for {email}.")
        return result

    except AuthApiError as e:
        log_event(f"[ERROR][API_AUTH][sign_in] AuthApiError for {email}. Type: {type(e).__name__}, Status: {e.status}, Message: {e.message}")
        error_message = f"Lỗi API ({e.status}): {e.message}"
        if e.status == 400:
            if "Invalid login credentials" in e.message: error_message = "Sai thông tin đăng nhập (email hoặc mật khẩu)."
            elif "Email not confirmed" in e.message: error_message = "Email chưa được xác thực. Vui lòng kiểm tra hộp thư của bạn."
        elif e.status == 429:
            error_message = "Bạn đã gửi quá nhiều yêu cầu, vui lòng thử lại sau."

        log_event(f"[DEBUG][API_AUTH][sign_in] Function finished with AuthApiError for {email}.")
        return {"success": False, "error": error_message}
    except Exception as e:
        # Bắt các lỗi khác, bao gồm TypeError nếu nó xảy ra ở đây
        log_event(f"[ERROR][API_AUTH][sign_in] Unexpected error for {email}. Type: {type(e).__name__}, Error: {e}", exc_info=True) # Log traceback
        log_event(f"[DEBUG][API_AUTH][sign_in] Function finished with unexpected error for {email}.")
        return {"success": False, "error": f"Lỗi không xác định: {type(e).__name__} - {e}"}


async def sign_out() -> bool:
    """Gọi API đăng xuất Supabase (async) với logging chi tiết."""
    log_event("[DEBUG][API_AUTH][sign_out] Function started.")
    supabase = get_supabase_client()
    if not supabase:
        log_event("[ERROR][API_AUTH][sign_out] Supabase client not available.")
        return False
    log_event("[DEBUG][API_AUTH][sign_out] Supabase client obtained.")

    try:
        log_event("[INFO][API_AUTH][sign_out] Attempting sign out.")
        # === Gọi API ===
        await supabase.auth.sign_out()
        # ===============
        log_event("[INFO][API_AUTH][sign_out] Sign out successful.")
        log_event("[DEBUG][API_AUTH][sign_out] Function finished successfully.")
        return True
    except AuthApiError as e:
        log_event(f"[ERROR][API_AUTH][sign_out] AuthApiError during sign out. Type: {type(e).__name__}, Status: {e.status}, Message: {e.message}")
        log_event("[DEBUG][API_AUTH][sign_out] Function finished with AuthApiError.")
        return False
    except Exception as e:
        log_event(f"[ERROR][API_AUTH][sign_out] Unexpected error during sign out. Type: {type(e).__name__}, Error: {e}", exc_info=True) # Log traceback
        log_event("[DEBUG][API_AUTH][sign_out] Function finished with unexpected error.")
        return False

# Sử dụng type hint cụ thể hơn nếu có thể
async def get_current_session_user() -> Optional[User]:
    """
    Lấy thông tin user từ session hiện tại mà thư viện quản lý (async).
    Hữu ích để kiểm tra trạng thái đăng nhập khi khởi động app. (Logging chi tiết)
    """
    log_event("[DEBUG][API_AUTH][get_current_session_user] Function started.")
    supabase = get_supabase_client()
    if not supabase:
        log_event("[ERROR][API_AUTH][get_current_session_user] Supabase client not available.")
        return None
    log_event("[DEBUG][API_AUTH][get_current_session_user] Supabase client obtained.")

    try:
        log_event("[INFO][API_AUTH][get_current_session_user] Attempting to get current session.")
        # === Gọi API ===
        session_info = await supabase.auth.get_session()
        # ===============
        log_event(f"[DEBUG][API_AUTH][get_current_session_user] Raw session info received: {repr(session_info)}")

        # Kiểm tra cẩn thận cấu trúc session_info
        if session_info and hasattr(session_info, 'user') and session_info.user:
            user_id = session_info.user.id if hasattr(session_info.user, 'id') else 'ID missing'
            log_event(f"[INFO][API_AUTH][get_current_session_user] Active session found for user {user_id}")
            log_event("[DEBUG][API_AUTH][get_current_session_user] Function finished, returning user.")
            # Trả về đối tượng User từ session (đảm bảo User type hint đúng)
            return session_info.user
        else:
            log_event("[INFO][API_AUTH][get_current_session_user] No active session found by client or session structure invalid.")
            log_event("[DEBUG][API_AUTH][get_current_session_user] Function finished, returning None.")
            return None
    except AuthApiError as e:
         log_event(f"[ERROR][API_AUTH][get_current_session_user] AuthApiError getting session. Type: {type(e).__name__}, Status: {e.status}, Message: {e.message}")
         log_event("[DEBUG][API_AUTH][get_current_session_user] Function finished with AuthApiError.")
         return None
    except Exception as e:
         log_event(f"[ERROR][API_AUTH][get_current_session_user] Unexpected error getting session. Type: {type(e).__name__}, Error: {e}", exc_info=True) # Log traceback
         log_event("[DEBUG][API_AUTH][get_current_session_user] Function finished with unexpected error.")
         return None

# Sử dụng type hint cụ thể hơn nếu có thể
async def set_session(access_token: str, refresh_token: str) -> Optional[Session]:
      """
      Khôi phục session từ access và refresh token (async).
      Lưu ý: Phiên bản supabase-py v2 thường dùng set_session(access_token, refresh_token)
      hoặc refresh_session(refresh_token) rồi get_session().
      Kiểm tra lại tài liệu supabase-py nếu cách dùng này không đúng.
      (Logging chi tiết)
      """
      log_event("[DEBUG][API_AUTH][set_session] Function started.")
      supabase = get_supabase_client()
      if not supabase:
          log_event("[ERROR][API_AUTH][set_session] Supabase client not available.")
          return None
      log_event("[DEBUG][API_AUTH][set_session] Supabase client obtained.")

      try:
          log_event("[INFO][API_AUTH][set_session] Attempting to set session using tokens.")
          # === Gọi API ===
          # Lưu ý quan trọng: Kiểm tra tài liệu supabase-py v2.x
          # Thông thường bạn sẽ dùng set_session(access_token, refresh_token)
          # Hoặc có thể cần dùng supabase.auth.refresh_session(refresh_token) trước
          # rồi gọi supabase.auth.get_session().
          # Ví dụ dưới đây giả định set_session chấp nhận cả hai.
          # Nếu không, hãy điều chỉnh lại logic.
          res = await supabase.auth.set_session(access_token=access_token, refresh_token=refresh_token)
          # ===============
          log_event(f"[DEBUG][API_AUTH][set_session] Raw response received: {repr(res)}")

          # Kiểm tra phản hồi từ set_session (thường là Session object)
          if res and hasattr(res, 'user') and hasattr(res, 'access_token') and res.user:
               user_id = res.user.id if hasattr(res.user, 'id') else 'ID missing'
               log_event(f"[INFO][API_AUTH][set_session] Session restored/set successfully for user {user_id}.")
               log_event("[DEBUG][API_AUTH][set_session] Function finished, returning session.")
               return res # Trả về đối tượng Session
          else:
               log_event(f"[WARN][API_AUTH][set_session] set_session did not return expected structure. Response: {repr(res)}")
               log_event("[DEBUG][API_AUTH][set_session] Function finished, returning None.")
               return None
      except AuthApiError as e:
          log_event(f"[ERROR][API_AUTH][set_session] AuthApiError setting session. Type: {type(e).__name__}, Status: {e.status}, Message: {e.message}")
          log_event("[DEBUG][API_AUTH][set_session] Function finished with AuthApiError.")
          return None
      except Exception as e:
          log_event(f"[ERROR][API_AUTH][set_session] Unexpected error setting session. Type: {type(e).__name__}, Error: {e}", exc_info=True) # Log traceback
          log_event("[DEBUG][API_AUTH][set_session] Function finished with unexpected error.")
          return None