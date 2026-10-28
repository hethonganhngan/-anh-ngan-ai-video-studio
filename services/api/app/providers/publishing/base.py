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


class FacebookPagesPublisher(_OfficialApiPublisher):
    platform, provider_code = "FACEBOOK", "facebook_pages"
    required_config = ("page_id",)
    docs = "https://developers.facebook.com/docs/video-api/guides/reels-publishing"


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
