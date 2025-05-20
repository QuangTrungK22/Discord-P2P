# SegmentChatClient/src/api/database.py
import datetime
from .client import get_supabase_client
from typing import List, Dict, Any, Optional
from src.utils.logger import log_event
from src.models.peer import Peer
from src.models.message import Message
from src.models.channel import Channel
from postgrest.exceptions import APIError # Để bắt lỗi cụ thể từ DB
PROFILES_TABLE = "profiles" # <<< THÊM TÊN BẢNG PROFILES
# Tên các bảng trong DB Supabase (nên đặt trong config hoặc constants)
PEERS_TABLE = "peers"
MESSAGES_TABLE = "messages"
CHANNELS_TABLE = "channels"
CHANNEL_MEMBERS_TABLE = "channel_members"

# Thời gian được coi là "gần đây" để lọc peer hoạt động (ví dụ: 5 phút)
ACTIVE_PEER_THRESHOLD_MINUTES = 5

async def submit_peer_info(user_id: Optional[str], ip_address: str, port: int) -> Dict[str, Any]:
    """
    Gửi thông tin peer lên bảng 'peers' (async).
    Sử dụng upsert dựa trên user_id nếu có.
    Trả về dict chứa success: bool và data hoặc error.
    """
    supabase = get_supabase_client()
    if not supabase:
        return {"success": False, "error": "Supabase client chưa khởi tạo"}

    peer_data = {
        "ip_address": ip_address,
        "port": port,
        "last_seen_at": datetime.datetime.now(datetime.timezone.utc).isoformat(), # Gửi timestamp UTC
        # user_id sẽ là cột conflict hoặc cần được thêm vào nếu chưa có
    }
    # Thêm user_id vào data nếu nó không phải là None
    if user_id:
         peer_data["user_id"] = user_id

    try:
        log_event(f"[API_DB] Submitting peer info: IP={ip_address}, Port={port}, UserID={user_id}")
        # Nếu có user_id, dùng upsert, giả định 'user_id' là cột conflict
        if user_id:
            # Upsert: Cập nhật nếu user_id tồn tại, ngược lại insert
            # 'on_conflict' trỏ vào cột hoặc constraint name gây xung đột
            # 'default_to_null=False' đảm bảo các cột không được cung cấp sẽ giữ giá trị cũ (nếu update)
            result = await supabase.table(PEERS_TABLE)\
                             .upsert(peer_data, on_conflict="user_id", default_to_null=False)\
                             .execute()
        else:
            # Nếu là visitor (không có user_id), bạn có thể chỉ insert
            # Hoặc bạn cần một cơ chế định danh khác cho visitor peer (ví dụ: peer_id riêng)
            # Tạm thời chỉ insert nếu không có user_id
            # Lưu ý: Cần đảm bảo bảng peers cho phép user_id là NULL
             log_event("[API_DB] Submitting peer info for visitor (inserting).")
             result = await supabase.table(PEERS_TABLE).insert(peer_data).execute()

        log_event(f"[API_DB] Peer info submitted. Result data: {result.data}")
        # Kiểm tra xem có dữ liệu trả về không (thường là list các record được ảnh hưởng)
        if result.data:
             # Trả về bản ghi peer đã được tạo/cập nhật (lấy phần tử đầu tiên)
             # Cần đảm bảo RLS cho phép select sau khi upsert/insert
             return {"success": True, "data": result.data[0]}
        else:
             # Upsert không trả về data nếu không có thay đổi hoặc không có select RLS?
             # Hoặc Insert có thể không trả về data tùy cấu hình.
             # Coi như thành công nếu không có lỗi
             log_event("[API_DB] Peer info submitted (no data returned from DB, assuming success).")
             return {"success": True, "data": None}

    except APIError as e:
        log_event(f"[ERROR][API_DB] APIError submitting peer info: {e.code} - {e.message} - {e.details}")
        return {"success": False, "error": f"Lỗi DB: {e.message}"}
    except Exception as e:
        log_event(f"[ERROR][API_DB] Unexpected error submitting peer info: {e}")
        return {"success": False, "error": f"Lỗi không xác định: {e}"}

async def update_user_status(user_id: str, new_status: str) -> bool:
    """
    Cập nhật cột 'status' và 'updated_at' cho user_id trong bảng 'profiles'.
    Args:
        user_id (str): ID của người dùng cần cập nhật.
        new_status (str): Trạng thái mới (ví dụ: 'online', 'offline', 'invisible', 'away').
    Returns:
        bool: True nếu cập nhật thành công, False nếu thất bại.
    """
    supabase = get_supabase_client()
    if not supabase:
        log_event(f"[API_DB][UPDATE_STATUS] Supabase client không khả dụng. Không thể cập nhật status cho user {user_id}.")
        return False
    if not user_id:
        log_event(f"[API_DB][UPDATE_STATUS] User ID không được cung cấp. Không thể cập nhật status.")
        return False

    # (Tùy chọn) Kiểm tra xem new_status có hợp lệ không nếu bạn có danh sách trạng thái cố định
    # valid_statuses = ["online", "offline", "invisible", "away"]
    # if new_status not in valid_statuses:
    #     log_event(f"[ERROR][API_DB][UPDATE_STATUS] Giá trị status không hợp lệ: {new_status} cho user {user_id}.")
    #     return False

    try:
        update_data = {
            "status": new_status,
            "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat() # Luôn cập nhật updated_at
        }
        log_event(f"[API_DB][UPDATE_STATUS] Đang cập nhật status cho user {user_id} thành '{new_status}'. Dữ liệu: {update_data}")

        result = await supabase.table(PROFILES_TABLE)\
                             .update(update_data)\
                             .eq("id", user_id)\
                             .execute()

        # Kiểm tra kết quả (Supabase update thường không trả về data nếu không có returning='representation')
        # Chỉ cần không có lỗi là coi như thành công nếu RLS cho phép
        if result and (hasattr(result, 'data') and result.data is not None): # Kiểm tra chặt chẽ hơn
             log_event(f"[API_DB][UPDATE_STATUS] Status được cập nhật thành công cho user {user_id}. Phản hồi data: {result.data}")
        elif result and hasattr(result, 'error') and result.error:
             log_event(f"[ERROR][API_DB][UPDATE_STATUS] Lỗi từ Supabase khi cập nhật status cho user {user_id}: {result.error}")
             return False # Có lỗi rõ ràng từ API
        else:
             # Không có data và không có lỗi, giả định thành công nếu RLS cho phép update mà không cần select
             log_event(f"[API_DB][UPDATE_STATUS] Status có thể đã được cập nhật cho user {user_id} (không có data trả về, không có lỗi).")
        return True

    except APIError as e:
        log_event(f"[ERROR][API_DB][UPDATE_STATUS] APIError khi cập nhật status cho user {user_id}: {e.code} - {e.message} - {e.details}")
        return False
    except Exception as e:
        log_event(f"[ERROR][API_DB][UPDATE_STATUS] Lỗi không mong muốn khi cập nhật status cho user {user_id}: {e}", exc_info=True)
        return False


async def get_active_peer_list() -> List[Peer]:
    """Lấy danh sách các peer đang hoạt động (async)."""
    supabase = get_supabase_client()
    if not supabase: return []

    peers_list = []
    try:
        # Tính toán thời điểm ngưỡng
        threshold_time = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=ACTIVE_PEER_THRESHOLD_MINUTES)
        threshold_iso = threshold_time.isoformat()

        log_event(f"[API_DB] Fetching active peer list (seen since {threshold_iso}).")
        result = await supabase.table(PEERS_TABLE)\
                         .select("ip_address, port, user_id")\
                         .gte("last_seen_at", threshold_iso)\
                         .execute() # Thêm các cột khác nếu cần (vd: peer_id)

        log_event(f"[API_DB] Active peer list fetched. Count: {len(result.data)}")
        for peer_data in result.data:
            # Tạo đối tượng Peer model
            peers_list.append(Peer(
                ip_address=peer_data.get("ip_address"),
                port=peer_data.get("port"),
                # peer_id=peer_data.get("peer_id"), # Lấy peer_id nếu có
                user_id=peer_data.get("user_id")
            ))
        return peers_list
    except APIError as e:
         log_event(f"[ERROR][API_DB] APIError fetching peer list: {e.message}")
         return []
    except Exception as e:
        log_event(f"[ERROR][API_DB] Unexpected error fetching peer list: {e}")
        return []


async def add_message_backup(channel_id: str, user_id: str, content: str) -> bool:
    """Lưu một tin nhắn vào bảng 'messages' làm backup (async)."""
    supabase = get_supabase_client()
    if not supabase: return False

    message_data = {
        "channel_id": channel_id,
        "user_id": user_id,
        "content": content
        # DB sẽ tự thêm timestamp nếu cột có default now()
    }
    try:
        log_event(f"[API_DB] Adding message backup for channel {channel_id}")
        await supabase.table(MESSAGES_TABLE).insert(message_data).execute()
        log_event(f"[API_DB] Message backup added for channel {channel_id}.")
        return True
    except APIError as e:
        log_event(f"[ERROR][API_DB] APIError adding message backup: {e.message}")
        return False
    except Exception as e:
        log_event(f"[ERROR][API_DB] Unexpected error adding message backup: {e}")
        return False


async def get_message_backups(channel_id: str, limit: int = 50) -> List[Message]:
    """Lấy các tin nhắn backup từ server cho một kênh (async), trả về list Message model."""
    supabase = get_supabase_client()
    if not supabase: return []

    messages_list: List[Message] = []
    try:
        log_event(f"[API_DB] Fetching message backups for channel {channel_id}, limit {limit}")
        result = await supabase.table(MESSAGES_TABLE)\
                          .select("*, profiles(id, display_name)")\
                          .eq("channel_id", channel_id)\
                          .order("created_at", desc=True)\
                          .limit(limit)\
                          .execute()

        log_event(f"[API_DB][GET_MSG_BKUPS] Kết quả thô từ Supabase (result.data): {result.data}")
        log_event(f"[API_DB] Fetched {len(result.data)} message backups for channel {channel_id}")
        for msg_data in result.data:
             # Chuyển đổi timestamp từ string ISO format sang datetime object
             ts_str = msg_data.get("created_at", "") # Giả sử tên cột là created_at
             timestamp = datetime.datetime.now(datetime.timezone.utc) # Default nếu lỗi
             try:
                 # Thêm 'Z' nếu timestamp từ Supabase là UTC và không có timezone offset
                 if ts_str and not ts_str.endswith('Z') and '+' not in ts_str:
                     # Supabase thường trả về dạng có offset +00:00
                     pass # Để nguyên nếu có offset
                 # Chuyển đổi
                 timestamp = datetime.datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
             except ValueError:
                 log_event(f"[WARN][API_DB] Could not parse timestamp string: {ts_str}")


             # Lấy display_name từ dữ liệu join (nếu có)
             sender_display_name = None
             profile_data = msg_data.get("profiles") # Tên bảng liên kết trong select
             if isinstance(profile_data, dict):
                 sender_display_name = profile_data.get("display_name")
             elif not sender_display_name:
                  # Fallback nếu không join hoặc không có display_name
                  sender_display_name = f"User_{msg_data.get('user_id', 'unknown')[:4]}"


             messages_list.append(Message(
                 id=msg_data.get("id"),
                 channel_id=msg_data.get("channel_id"),
                 user_id=msg_data.get("user_id"),
                 content=msg_data.get("content"),
                 timestamp=timestamp,
                 sender_display_name=sender_display_name
             ))
        # Đảo ngược list để hiển thị từ cũ -> mới nếu cần
        messages_list.reverse()
        return messages_list
    except APIError as e:
        log_event(f"[ERROR][API_DB] APIError fetching message backups for channel {channel_id}: {e.message}")
        return []
    except Exception as e:
        log_event(f"[ERROR][API_DB] Unexpected error fetching message backups for channel {channel_id}: {e}")
        return []

# --- Các hàm Channel ---

async def get_my_joined_channels(user_id: str) -> List[Channel]:
     """Lấy danh sách kênh user đã tham gia (từ bảng channel_members)."""
     supabase = get_supabase_client()
     if not supabase: return []
     channels: List[Channel] = []
     try:
         log_event(f"[API_DB] Fetching joined channels for user {user_id}")
         # Join bảng channel_members với bảng channels
         result = await supabase.table(CHANNEL_MEMBERS_TABLE)\
                           .select("channel_id, channels(id, name, owner_id)")\
                           .eq("user_id", user_id)\
                           .execute()
         log_event(f"[API_DB] Fetched {len(result.data)} joined channels for user {user_id}")
         log_event(f"[DEBUG][API_DB] Raw result from get_my_joined_channels for user {user_id}: {result}")
         for membership in result.data:
             channel_data = membership.get("channels")
             if isinstance(channel_data, dict):
                 channels.append(Channel(
                     id=channel_data.get("id"),
                     name=channel_data.get("name"),
                     owner_id=channel_data.get("owner_id")
                 ))
         return channels
     except APIError as e:
         log_event(f"[ERROR][API_DB] APIError fetching joined channels: {e.message}")
         return []
     except Exception as e:
         log_event(f"[ERROR][API_DB] Unexpected error fetching joined channels: {e}")
         return []


async def get_my_hosted_channels(user_id: str) -> List[Channel]:
     """Lấy danh sách kênh do user sở hữu (từ bảng channels)."""
     supabase = get_supabase_client()
     if not supabase: return []
     channels: List[Channel] = []
     try:
         log_event(f"[API_DB] Fetching hosted channels for user {user_id}")
         result = await supabase.table(CHANNELS_TABLE)\
                           .select("id, name, owner_id")\
                           .eq("owner_id", user_id)\
                           .execute()
         log_event(f"[API_DB] Fetched {len(result.data)} hosted channels for user {user_id}")
         log_event(f"[DEBUG][API_DB] Raw result from get_my_hosted_channels for user {user_id}: {result}")
         for channel_data in result.data:
             channels.append(Channel(
                 id=channel_data.get("id"),
                 name=channel_data.get("name"),
                 owner_id=channel_data.get("owner_id")
             ))
         return channels
     except APIError as e:
         log_event(f"[ERROR][API_DB] APIError fetching hosted channels: {e.message}")
         return []
     except Exception as e:
         log_event(f"[ERROR][API_DB] Unexpected error fetching hosted channels: {e}")
         return []


async def create_channel(user_id: str, channel_name: str) -> Optional[Channel]:
    """
    Tạo kênh mới trên Supabase.
    Args:
        user_id (str): ID của người tạo kênh
        channel_name (str): Tên kênh
    Returns:
        Optional[Channel]: Đối tượng Channel nếu tạo thành công, None nếu thất bại
    """
    supabase = get_supabase_client()
    if not supabase:
        log_event("[ERROR][API_DB] Supabase client không khả dụng cho create_channel")
        return None

    try:
        log_event(f"[API_DB] Đang thử tạo kênh '{channel_name}' cho user {user_id}")

        # Thực hiện insert với returning='representation' để lấy dữ liệu đã chèn
        result = await supabase.table(CHANNELS_TABLE)\
            .insert({
                "name": channel_name,
                "owner_id": user_id
            }, returning='representation')\
            .execute()

        log_event(f"[API_DB] Kết quả tạo kênh: {result}")

        # Kiểm tra và xử lý kết quả
        if result and result.data:
            channel_data = result.data[0]
            log_event(f"[API_DB] Kênh được tạo thành công: {channel_data}")
            
            # Tạo đối tượng Channel từ dữ liệu trả về
            return Channel(
                id=channel_data.get("id"),
                name=channel_data.get("name"),
                owner_id=channel_data.get("owner_id")
            )
        else:
            log_event(f"[WARN][API_DB] Tạo kênh '{channel_name}' không có dữ liệu trả về. Kiểm tra RLS SELECT.")
            return None

    except APIError as e:
        log_event(
            f"[ERROR][API_DB] Lỗi APIError khi tạo kênh '{channel_name}': "
            f"{getattr(e, 'code', 'N/A')} - {getattr(e, 'message', str(e))}",
            exc_info=True
        )
        return None
        
    except Exception as e:
        log_event(f"[ERROR][API_DB] Lỗi không mong muốn khi tạo kênh '{channel_name}': {e}", 
                 exc_info=True)
        return None


async def join_channel(user_id: str, channel_id: str) -> bool:
     """Thêm user vào bảng channel_members (async)."""
     supabase = get_supabase_client()
     if not supabase: return False
     try:
         log_event(f"[API_DB] User {user_id} joining channel {channel_id}")
         # Dùng upsert để tránh lỗi nếu user đã join rồi
         await supabase.table(CHANNEL_MEMBERS_TABLE)\
                       .upsert({"user_id": user_id, "channel_id": channel_id}, on_conflict="user_id, channel_id")\
                       .execute()
         log_event(f"[API_DB] User {user_id} joined channel {channel_id} successfully.")
         return True
     except APIError as e:
         log_event(f"[ERROR][API_DB] APIError joining channel: {e.message}")
         return False
     except Exception as e:
         log_event(f"[ERROR][API_DB] Unexpected error joining channel: {e}")
         return False

async def leave_channel(user_id: str, channel_id: str) -> bool:
      """Xóa user khỏi bảng channel_members (async)."""
      supabase = get_supabase_client()
      if not supabase: return False
      try:
          log_event(f"[API_DB] User {user_id} leaving channel {channel_id}")
          await supabase.table(CHANNEL_MEMBERS_TABLE)\
                        .delete()\
                        .match({"user_id": user_id, "channel_id": channel_id})\
                        .execute()
          log_event(f"[API_DB] User {user_id} left channel {channel_id} successfully.")
          return True
      except APIError as e:
          log_event(f"[ERROR][API_DB] APIError leaving channel: {e.message}")
          return False
      except Exception as e:
          log_event(f"[ERROR][API_DB] Unexpected error leaving channel: {e}")
          return False
async def get_channel_members(channel_id: str) -> List[str]:
    """Lấy danh sách user_id trong một kênh (async)."""
    supabase = get_supabase_client()
    if not supabase or not channel_id: return []
    members_list:List[str] = []
    # Kiểm tra channel_id có hợp lệ không (nếu cần)
    try:
        log_event(f"[API_DB] Fetching members for channel {channel_id}")
        result = await supabase.table(CHANNEL_MEMBERS_TABLE)\
                          .select("user_id")\
                          .eq("channel_id", channel_id)\
                          .execute()
        if result.data:
            member_ids = [member['user_id'] for member in result.data if 'user_id' in member]
            log_event(f"[API_DB] Found {len(member_ids)} members for channel {channel_id}")
        else:
            log_event(f"[API_DB] No members found or error fetching members for channel {channel_id}. Result: {result}")
        return member_ids
    except APIError as e:
        log_event(f"[ERROR][API_DB] APIError fetching channel members for {channel_id}: {e.message}")
        return []
    except Exception as e:
        log_event(f"[ERROR][API_DB] Unexpected error fetching channel members for {channel_id}: {e}", exc_info=True)
        return []

# --- Các hàm liên quan đến Synchronization khác ---
# Ví dụ: Lấy tin nhắn sau một thời điểm nào đó để sync khi online lại
# async def get_messages_since(channel_id: str, timestamp: datetime.datetime): ...


# === HÀM LẤY ID THÀNH VIÊN KÊNH ===
async def get_channel_member_ids(channel_id: str) -> List[str]:
    """
    Lấy danh sách user_id của các thành viên trong một kênh cụ thể.
    """
    supabase = get_supabase_client()
    if not supabase or not channel_id:
        log_event(f"[API_DB] Get members failed: No Supabase client or channel_id for {channel_id}") # Log rõ hơn
        return []

    member_ids: List[str] = []
    try:
        log_event(f"[API_DB] Fetching member IDs for channel {channel_id}")
        # Chỉ cần lấy cột user_id từ bảng channel_members
        # Đảm bảo RLS cho phép SELECT trên channel_members
        result = await supabase.table(CHANNEL_MEMBERS_TABLE)\
                           .select("user_id")\
                           .eq("channel_id", channel_id)\
                           .execute()

        if result.data:
            member_ids = [member['user_id'] for member in result.data if 'user_id' in member]
            log_event(f"[API_DB] Found {len(member_ids)} members for channel {channel_id}")
        # Xử lý trường hợp không có data hoặc lỗi nhẹ mà không throw exception
        elif hasattr(result, 'error') and result.error:
             log_event(f"[WARN][API_DB] Error fetching members for channel {channel_id}: {result.error}")
        else:
             log_event(f"[API_DB] No members data returned for channel {channel_id}.") # Có thể kênh trống
        return member_ids
    except APIError as e: # Bắt lỗi API cụ thể
        log_event(f"[ERROR][API_DB] APIError fetching channel members for {channel_id}: {getattr(e, 'code', 'N/A')} - {getattr(e, 'message', str(e))}")
        return []
    except Exception as e: # Bắt lỗi chung khác
        log_event(f"[ERROR][API_DB] Unexpected error fetching channel members for {channel_id}: {e}", exc_info=True)
        return []

# === HÀM LẤY THÔNG TIN PROFILES ===
async def get_user_profiles(user_ids: List[str]) -> Dict[str, Dict[str, Any]]:
    """
    Lấy thông tin profiles (ví dụ: display_name) cho một danh sách user_id.
    Trả về một dict với key là user_id, value là dict chứa thông tin profile.
    """
    supabase = get_supabase_client()
    if not supabase or not user_ids:
        log_event(f"[API_DB] Get profiles failed: No Supabase client or empty user_ids list.")
        return {}

    profiles_data: Dict[str, Dict[str, Any]] = {}
    try:
        log_event(f"[API_DB] Fetching profiles for {len(user_ids)} users")
        # Lấy các cột cần thiết, đảm bảo tên cột đúng với bảng profiles của bạn
        # Đảm bảo RLS cho phép SELECT trên profiles
        result = await supabase.table(PROFILES_TABLE)\
                           .select("id, display_name, status") .in_("id", user_ids)\
                           .execute()


        if result.data:
            for profile in result.data:
                user_id = profile.get("id") # Giả sử cột ID trong profiles tên là 'id'
                if user_id:
                    # Đảm bảo display_name không phải None trước khi dùng
                    profile['display_name'] = profile.get('display_name', f"User_{user_id[:6]}")
                    profile['status'] = profile.get('status', 'online')
                    profiles_data[user_id] = profile
            log_event(f"[API_DB] Fetched profile data for {len(profiles_data)} users.")
        elif hasattr(result, 'error') and result.error:
             log_event(f"[WARN][API_DB] Error fetching profiles: {result.error}")
        else:
            log_event(f"[API_DB] No profiles data returned for the given user IDs.")
        return profiles_data
    except APIError as e:
        log_event(f"[ERROR][API_DB] APIError fetching profiles: {getattr(e, 'code', 'N/A')} - {getattr(e, 'message', str(e))}")
        return {}
    except Exception as e:
        log_event(f"[ERROR][API_DB] Unexpected error fetching profiles: {e}", exc_info=True)
        return {}
