"""Publisher adapters — CHỈ qua API chính thức được cấp quyền. Chưa có quyền → NotConnected (không giả lập thành công)."""
from abc import ABC, abstractmethod


class PublisherNotConnected(Exception):
    pass


class Publisher(ABC):
    platform = "abstract"
    provider_code = "abstract"
    docs = ""

    def __init__(self, credentials: str | None, config: dict):
        self.credentials = credentials
        self.config = config or {}

    @abstractmethod
    def publish(self, video_path: str, caption: str, thumbnail_path: str | None = None) -> str:
        """Trả về URL bài đăng."""


class _OfficialApiPublisher(Publisher):
    required_config: tuple = ()

    def publish(self, video_path, caption, thumbnail_path=None):
        missing = [k for k in self.required_config if not self.config.get(k)]
        if not self.credentials or missing:
            raise PublisherNotConnected(f"{self.platform}: chưa cấu hình quyền API chính thức ({', '.join(missing) or 'token'}). "
                                        f"Xem {self.docs}")
        raise PublisherNotConnected(f"{self.platform}: adapter chưa được xác minh với tài khoản thật — "
                                    "dùng chế độ xuất file & cập nhật thủ công")


class PublishError(Exception):
    pass


class FacebookPagesPublisher(Publisher):
    """Facebook Reels Publishing API (Graph API chính thức). CHỈ tải lên dạng BẢN NHÁP (video_state=DRAFT):
    bài nằm trong Meta Business Suite chờ người duyệt đăng — hệ thống không tự công khai (CEO chốt 31/10/2026).
    Token (mã hoá trong M15): Page token, hoặc User token dài hạn có pages_manage_posts để lấy Page token từng Fanpage."""
    platform, provider_code = "FACEBOOK", "facebook_pages"
    docs = "https://developers.facebook.com/docs/video-api/guides/reels-publishing"

    def __init__(self, credentials, config, client=None):
        super().__init__(credentials, config)
        import httpx

        self.version = self.config.get("graph_version", "v26.0")
        self.http = client or httpx.Client(timeout=httpx.Timeout(30, read=300))

    @staticmethod
    def _auth(token: str) -> dict:
        """Token đi trong header, KHÔNG nằm trên URL (URL bị ghi log bởi httpx/proxy → lộ token)."""
        return {"Authorization": f"OAuth {token}"}

    def _check(self, r) -> dict:
        try:
            data = r.json()
        except ValueError:
            data = {}
        if r.status_code >= 400 or "error" in data:
            err = data.get("error") or {}
            msg = err.get("message") or r.text[:300]
            if r.status_code in (401, 403) or err.get("code") in (190, 200, 10):
                raise PublisherNotConnected(f"Facebook từ chối quyền: {msg}")
            raise PublishError(f"Facebook lỗi {err.get('code', r.status_code)}: {msg}")
        return data

    def pages(self) -> list[dict]:
        """Các Fanpage token truy cập được: User token → /me/accounts; Page token → chính trang đó."""
        if not self.credentials:
            raise PublisherNotConnected("Facebook: chưa nhập token trong M15 → API connections")
        g = f"https://graph.facebook.com/{self.version}"
        r = self.http.get(f"{g}/me/accounts", params={"fields": "id,name,tasks", "limit": 100}, headers=self._auth(self.credentials))
        if r.status_code < 400 and "error" not in r.json():
            return [{"id": p["id"], "name": p.get("name", ""), "can_post": "CREATE_CONTENT" in (p.get("tasks") or ["CREATE_CONTENT"])}
                    for p in r.json().get("data", [])]
        me = self._check(self.http.get(f"{g}/me", params={"fields": "id,name"}, headers=self._auth(self.credentials)))
        return [{"id": me["id"], "name": me.get("name", ""), "can_post": True}]

    def page_info(self, page_id: str) -> dict:
        """Tên Fanpage + Page token. Token đưa vào là Page token thì Graph vẫn trả access_token của chính trang đó."""
        if not self.credentials:
            raise PublisherNotConnected("Facebook: chưa nhập token trong M15 → API connections")
        r = self.http.get(f"https://graph.facebook.com/{self.version}/{page_id}",
                          params={"fields": "id,name,access_token"}, headers=self._auth(self.credentials))
        data = self._check(r)
        return {"id": data.get("id", page_id), "name": data.get("name", ""), "token": data.get("access_token") or self.credentials}

    def upload_draft(self, page_id: str, video_path: str, caption: str) -> str:
        """3 bước: start → tải file nhị phân → finish với video_state=DRAFT. Trả về video_id (cũng là id Reel)."""
        import os

        token = self.page_info(page_id)["token"]
        base = f"https://graph.facebook.com/{self.version}/{page_id}/video_reels"
        vid = self._check(self.http.post(base, json={"upload_phase": "start"}, headers=self._auth(token)))["video_id"]
        with open(video_path, "rb") as f:
            self._check(self.http.post(f"https://rupload.facebook.com/video-upload/{self.version}/{vid}", content=f.read(),
                                       headers={"Authorization": f"OAuth {token}", "offset": "0",
                                                "file_size": str(os.path.getsize(video_path)),
                                                "Content-Type": "application/octet-stream"}))
        self._check(self.http.post(base, data={"video_id": vid, "upload_phase": "finish", "video_state": "DRAFT",
                                               "description": caption[:2200], "is_ai_generated": "true"},
                                   headers=self._auth(token)))
        return str(vid)

    def status(self, page_id: str, video_id: str) -> dict:
        """publish_status: draft | scheduled | published | error (người duyệt đăng trên Facebook → published)."""
        token = self.page_info(page_id)["token"]
        data = self._check(self.http.get(f"https://graph.facebook.com/{self.version}/{video_id}",
                                         params={"fields": "status,permalink_url"}, headers=self._auth(token)))
        st = data.get("status") or {}
        pub = st.get("publishing_phase") or {}
        err = (st.get("processing_phase") or {}).get("error") or pub.get("error")
        link = data.get("permalink_url") or ""
        if link.startswith("/"):
            link = "https://www.facebook.com" + link
        return {"video_status": st.get("video_status"), "publish_status": pub.get("publish_status"),
                "permalink_url": link or f"https://www.facebook.com/reel/{video_id}",
                "error": (err or {}).get("message") if isinstance(err, dict) else err}

    def publish(self, video_path, caption, thumbnail_path=None):
        raise PublisherNotConnected("Facebook: hệ thống chỉ tải bản nháp chờ duyệt (upload_draft), không tự đăng công khai")


class TikTokPublisher(_OfficialApiPublisher):
    platform, provider_code = "TIKTOK", "tiktok_content"
    required_config = ("client_key",)
    docs = "https://developers.tiktok.com/doc/content-posting-api-get-started"


class YouTubePublisher(_OfficialApiPublisher):
    platform, provider_code = "YOUTUBE", "youtube_data"
    required_config = ("channel_id",)
    docs = "https://developers.google.com/youtube/v3/guides/uploading_a_video"


class ZaloOAPublisher(_OfficialApiPublisher):
    platform, provider_code = "ZALO", "zalo_oa"
    required_config = ("oa_id",)
    docs = "https://developers.zalo.me/docs/official-account"


PUBLISHERS = {c.platform: c for c in (FacebookPagesPublisher, TikTokPublisher, YouTubePublisher, ZaloOAPublisher)}
URL_DOMAINS = {
    "FACEBOOK": ("facebook.com", "fb.watch", "fb.com"),
    "TIKTOK": ("tiktok.com",),
    "YOUTUBE": ("youtube.com", "youtu.be"),
    "ZALO": ("zalo.me", "oa.zalo.me"),
}
