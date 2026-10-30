"""Google Flow tự động (thử nghiệm, D21) — Playwright điều khiển Chrome đã đăng nhập Flow qua CDP.

Dùng lượt tạo video của gói Google (AI Pro/Ultra) → không phát sinh phí API. Rủi ro đã được CEO chấp nhận:
Google có thể hạn chế tài khoản vì truy cập tự động; giao diện Flow đổi là phải chỉnh bộ chọn bên dưới.
- Chrome chạy riêng: scripts/windows/start-flow-chrome.ps1 (cổng CDP chỉ nghe 127.0.0.1, profile riêng đã đăng nhập Flow).
- Mỗi lần chỉ 1 cảnh (khoá Redis): gửi prompt → chờ cảnh mới (trang chỉnh sửa /edit/… hoặc ảnh thu nhỏ mới)
  → Tải xuống 720p (kích thước gốc) → đóng tab.
  Toàn bộ chạy đồng bộ trong submit_generation; provider_job_id mang kết quả (đường dẫn file hoặc lý do chờ thủ công).
- Không đăng nhập, không vượt CAPTCHA: gặp trang đăng nhập/xác minh → NEEDS_MANUAL_ACTION, người dùng tự xử lý.
- Đã bấm tạo mà quá thời gian chờ → NEEDS_MANUAL_ACTION (không gửi lại để khỏi tốn lượt): tải tay trên Flow rồi nhập ở M05.
"""
import os
import re
import tempfile
import time

from app.providers.video.base import GenerationSpec, ProviderError, ProviderStatus, VideoProvider
from app.providers.video.veo_vertex import NO_TEXT, SILENT_SPEECH

DEFAULT_CDP = "http://127.0.0.1:9222"
DEFAULT_PROJECT = "https://flow.google.com/project/6ae396ef-7905-495b-90b1-564042d940cd"
PROMPT_BOX = "Bạn muốn tạo gì?"
SUBMIT_BUTTON = "Bắt đầu tạo"
OK, MANUAL = "flowcdp:ok:", "flowcdp:manual:"
LOCK_KEY = "anngan:flow_cdp:lock"
CHALLENGE = re.compile(r"accounts\.google\.com|/sorry/|recaptcha|challenge", re.I)
SECTION = re.compile(r"^\[\d+\.\s*([^\]]+)\]\s*(.*)$", re.MULTILINE)
LOCK_TAG = re.compile(r"\[(Character|Scene) Lock[^\]]*\]|\b(CHR|SCN)-\d{4}-\d{4}\s*")

DOWNLOAD_BUTTON = "Tải nội dung nghe nhìn xuống"
QUALITY = re.compile(r"720p|Kích thước gốc")  # bản gốc — các mức 1080p/4K là tăng độ phân giải
EDIT_ID = re.compile(r"/edit/([0-9a-f-]{36})")
THUMB_ID = re.compile(r"/image/([0-9a-f-]{36})")
# Flow phát video bằng canvas (không có <video>): nhận ra nội dung mới qua id ảnh thu nhỏ trong lưới dự án
_THUMBS_JS = "() => [...document.querySelectorAll('img')].map(i => i.src)"


def to_flow_prompt(prompt_text: str, duration_sec: int, speech_in_video: bool) -> str:
    """Prompt 9 mục → 1 đoạn văn cho tác nhân Flow (tương đương toFlowPrompt ở web)."""
    parts = {m.group(1).strip().upper(): m.group(2) for m in SECTION.finditer(prompt_text)}

    def get(k: str) -> str:
        return re.sub(r"\s+", " ", LOCK_TAG.sub("", parts.get(k, ""))).strip().rstrip(".;,")

    who, _, manner = get("NHÂN VẬT").partition(":")
    out = [
        f"Tạo 1 video (không tạo hình ảnh) dọc 9:16, {duration_sec} giây, chuyển động tự nhiên, chân thực.",
        f"Nhân vật: {who.strip() or 'Nhân vật'}, giữ nguyên khuôn mặt và trang phục theo nhân vật đã lưu trong dự án; "
        f"thần thái {manner.split(';')[0].strip() or 'ấm áp, nhẹ nhàng'}.",
    ]
    for key, label in (("LOẠI CẢNH", "Kiểu cảnh"), ("HÀNH ĐỘNG", "Hành động"), ("BỐI CẢNH", "Bối cảnh"),
                       ("MÁY QUAY", "Máy quay"), ("ÁNH SÁNG", "Ánh sáng"), ("ÂM THANH", "Âm thanh")):
        if get(key):
            out.append(f"{label}: {get(key)}.")
    if get("THOẠI"):
        out.append(f"Lời thoại: {get('THOẠI').replace(' / ', ' ')}")
    if get("NEGATIVE PROMPT"):
        out.append(f"Tránh: {get('NEGATIVE PROMPT')}.")
    if not parts:  # prompt tự do (không theo 9 mục)
        out = [out[0], prompt_text.strip()]
    out.append(NO_TEXT)
    if not speech_in_video:
        out.append(SILENT_SPEECH)
    return " ".join(out)


class _NeedsManual(Exception):
    pass


class FlowCDPProvider(VideoProvider):
    kind = "REAL_API"
    is_real = True
    supported_aspects = ("9:16", "16:9")
    max_duration_sec = 8

    def __init__(self, code: str, name: str, config: dict, unit_cost_vnd_per_sec=0):
        self.code = code
        self.name = name
        self.config = config or {}
        self.cdp_url = self.config.get("cdp_url", DEFAULT_CDP)
        self.project_url = self.config.get("project_url", DEFAULT_PROJECT)
        self.timeout_sec = int(self.config.get("timeout_min", 15)) * 60
        self.speech_in_video = bool(self.config.get("speech_in_video", False))
        self.unit_cost_vnd_per_sec = 0  # dùng lượt của gói Google — không tính phí API

    # ---------- trình duyệt ----------
    def _connect(self, pw):
        if not re.match(r"^http://(127\.0\.0\.1|localhost):\d+$", self.cdp_url):
            raise ProviderError("CDP chỉ được kết nối Chrome trên máy này (127.0.0.1)", code="BAD_URL", retryable=False)
        try:
            browser = pw.chromium.connect_over_cdp(self.cdp_url, timeout=15000)
        except Exception as e:  # noqa: BLE001
            raise ProviderError(f"Không kết nối được Chrome Flow ({self.cdp_url}). Chạy scripts/windows/start-flow-chrome.ps1 "
                                f"rồi tạo lại cảnh. Chi tiết: {str(e)[:200]}", code="PROVIDER_UNAVAILABLE", retryable=False)
        if not browser.contexts:
            raise ProviderError("Chrome Flow không có profile đang mở", code="PROVIDER_UNAVAILABLE", retryable=False)
        return browser, browser.contexts[0]

    def _open_project(self, ctx):
        page = ctx.new_page()
        page.goto(self.project_url, wait_until="domcontentloaded", timeout=60000)
        box = page.get_by_role("textbox", name=PROMPT_BOX)
        try:
            box.wait_for(state="visible", timeout=45000)
        except Exception:  # noqa: BLE001
            if CHALLENGE.search(page.url) or page.locator("iframe[src*='recaptcha']").count():
                return page, None, "Flow yêu cầu đăng nhập/xác minh — mở Chrome Flow, đăng nhập rồi tạo lại cảnh"
            return page, None, f"Không thấy ô '{PROMPT_BOX}' trên Flow (giao diện có thể đã đổi) — {page.url}"
        return page, box, None

    def _thumb_ids(self, page) -> list[str]:
        return [m.group(1) for src in page.evaluate(_THUMBS_JS) if (m := THUMB_ID.search(src or ""))]

    def _try_download(self, page) -> tuple[str, str | None]:
        """Ở trang chỉnh sửa của 1 nội dung: Tải xuống → 720p (kích thước gốc).
        ('ok', đường dẫn) | ('wait', None) chưa sẵn sàng | ('skip', None) không phải video."""
        btn = page.get_by_role("button", name=DOWNLOAD_BUTTON)
        if not btn.count():
            return "wait", None
        btn.first.click()
        items = page.get_by_role("menuitem")
        try:
            items.first.wait_for(timeout=5000)
        except Exception:  # noqa: BLE001 — chưa có menu: video còn đang tạo
            page.keyboard.press("Escape")
            return "wait", None
        item = items.filter(has_text=QUALITY)
        if not item.count():  # menu của ảnh (1K/2K/4K) → không phải video
            page.keyboard.press("Escape")
            return "skip", None
        with page.expect_download(timeout=180000) as d:
            item.first.click()
        dl = d.value
        if not dl.suggested_filename.lower().endswith(".mp4"):
            return "skip", None
        fd, path = tempfile.mkstemp(suffix=".mp4")
        os.close(fd)
        dl.save_as(path)
        if os.path.getsize(path) < 10000:
            raise ProviderError("File video Flow tải về quá nhỏ", code="DOWNLOAD_FAILED", retryable=False)
        return "ok", path

    def _wait_for_video(self, page, before: set[str]) -> str | None:
        """Chờ nội dung mới: Flow tự mở trang chỉnh sửa của cảnh vừa tạo, hoặc ảnh thu nhỏ mới xuất hiện đầu lưới."""
        skipped: set[str] = set()
        deadline = time.monotonic() + self.timeout_sec
        while time.monotonic() < deadline:
            page.wait_for_timeout(10000)
            if CHALLENGE.search(page.url):
                raise _NeedsManual("Flow chuyển sang trang đăng nhập/xác minh trong lúc tạo — xử lý trên Chrome Flow")
            edit = EDIT_ID.search(page.url)
            if edit is None:
                new = [i for i in self._thumb_ids(page) if i not in before and i not in skipped]
                if not new:
                    continue
                page.locator(f"img[src*='{new[0]}']").first.click()
                try:
                    page.wait_for_url(EDIT_ID, timeout=15000)
                except Exception:  # noqa: BLE001
                    continue
                edit = EDIT_ID.search(page.url)
            if edit.group(1) in skipped:
                continue
            state, path = self._try_download(page)
            if state == "ok":
                return path
            if state == "skip":
                skipped.add(edit.group(1))
                skipped.update(self._thumb_ids(page)[:1])
                page.goto(self.project_url, wait_until="domcontentloaded", timeout=60000)
        return None

    def _generate(self, spec: GenerationSpec) -> str:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as pw:
            _, ctx = self._connect(pw)
            page = None
            try:
                page, box, problem = self._open_project(ctx)
                if problem:
                    return MANUAL + problem
                page.wait_for_timeout(4000)  # chờ lưới nội dung tải xong để lấy mốc
                before = set(self._thumb_ids(page))
                box.click()
                box.fill(to_flow_prompt(spec.prompt_text, spec.duration_sec, self.speech_in_video))
                page.get_by_role("button", name=SUBMIT_BUTTON).click()
                try:
                    path = self._wait_for_video(page, before)
                except _NeedsManual as e:
                    return MANUAL + str(e)
                if path:
                    return OK + path
                return MANUAL + (f"Đã gửi lên Flow nhưng sau {self.timeout_sec // 60} phút chưa tải được video — "
                                 "kiểm tra trên Flow, tải MP4 rồi 'Nhập từ Flow' (không tự gửi lại để khỏi tốn lượt)")
            finally:
                if page is not None:
                    page.close()  # chỉ đóng tab đã mở; thoát sync_playwright là ngắt CDP, Chrome vẫn chạy

    # ---------- VideoProvider ----------
    def submit_generation(self, spec: GenerationSpec) -> str:
        import redis
        from app.core.config import get_settings

        lock = redis.Redis.from_url(get_settings().redis_url).lock(LOCK_KEY, timeout=self.timeout_sec + 600,
                                                                    blocking_timeout=3 * 3600)
        if not lock.acquire():
            raise ProviderError("Chrome Flow bận quá lâu với cảnh khác", code="BUSY", retryable=True)
        try:
            return self._generate(spec)
        finally:
            try:
                lock.release()
            except redis.exceptions.LockError:
                pass

    def get_status(self, provider_job_id: str) -> ProviderStatus:
        if provider_job_id.startswith(OK):
            return ProviderStatus(state="SUCCEEDED", progress=100)
        if provider_job_id.startswith(MANUAL):
            return ProviderStatus(state="NEEDS_MANUAL_ACTION", error_code="FLOW_MANUAL",
                                  error_message=provider_job_id[len(MANUAL):][:500])
        return ProviderStatus(state="FAILED", error_code="BAD_JOB_ID", error_message="Mã tác vụ Flow không hợp lệ")

    def get_result(self, provider_job_id: str) -> str:
        if not provider_job_id.startswith(OK):
            raise ProviderError("Chưa có video Flow", code="NOT_READY", retryable=False)
        return provider_job_id[len(OK):]

    def cancel_job(self, provider_job_id: str) -> bool:
        return False

    def test_connection(self) -> str:
        """Mở dự án Flow trong Chrome CDP và kiểm tra thấy ô nhập lệnh — không tạo video."""
        from playwright.sync_api import sync_playwright

        with sync_playwright() as pw:
            _, ctx = self._connect(pw)
            page, _, problem = self._open_project(ctx)
            page.close()
            if problem:
                raise ProviderError(problem, code="NOT_LOGGED_IN", retryable=False)
            return "Chrome Flow sẵn sàng"
