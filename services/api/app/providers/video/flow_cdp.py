"""Google Flow tự động (thử nghiệm, D21) — Playwright điều khiển Chrome đã đăng nhập Flow qua CDP.

Dùng lượt tạo video của gói Google (AI Pro/Ultra) → không phát sinh phí API. Rủi ro đã được CEO chấp nhận:
Google có thể hạn chế tài khoản vì truy cập tự động; giao diện Flow đổi là phải chỉnh bộ chọn bên dưới.
- Chrome chạy riêng: scripts/windows/start-flow-chrome.ps1 (cổng CDP chỉ nghe 127.0.0.1, profile riêng đã đăng nhập Flow).
- Mỗi lần chỉ 1 cảnh (khoá Redis): phiên tác nhân mới → gửi prompt → ô đầu lưới hiện % rồi xong
  → mở ô → Tải xuống 720p (kích thước gốc) → đóng tab. Mỗi câu lệnh gắn chip '@' nhân vật + ảnh cửa hàng
  đã lưu trong dự án Flow (config 'ingredients') để giữ đúng khuôn mặt, trang phục và bối cảnh.
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
NOTE = re.compile(r"^Lưu ý:\s*(.+)$", re.MULTILINE)
LOCK_TAG = re.compile(r"\[(Character|Scene) Lock[^\]]*\]|\b(CHR|SCN)-\d{4}-\d{4}\s*")

DOWNLOAD_BUTTON = "Tải nội dung nghe nhìn xuống"
NEW_SESSION = "Bắt đầu phiên mới"  # mỗi cảnh 1 phiên tác nhân — phiên cũ khiến Flow mở lại/sửa cảnh trước
PICKER_LIST = "Danh sách thành phần"  # hộp chọn thành phần mở khi gõ "@" trong ô lệnh
DEFAULT_INGREDIENTS = ("MeAnhNgan", "Cửa hàng Ánh Ngân")  # nhân vật + ảnh cửa hàng đã lưu trong dự án Flow
QUALITY = re.compile(r"720p|Kích thước gốc")  # bản gốc — các mức 1080p/4K là tăng độ phân giải
# Lưới dự án: nội dung mới nhất luôn ở ô đầu tiên; ô đang tạo hiện % tiến độ (ảnh thu nhỏ là URL ký số, không có id)
EDIT_ID = re.compile(r"/edit/([0-9a-f-]{36})")
TILE = "flow-grid-tile-container"
PROGRESS = re.compile(r"(?<![0-9])[0-9]{1,3} ?%")
TILE_FAILED = re.compile(r"không thành công|thất bại|failed|error", re.I)
START_TIMEOUT_SEC = 300  # tác nhân phải bắt đầu tạo (ô % xuất hiện) trong 5 phút


def to_flow_prompt(prompt_text: str, duration_sec: int, speech_in_video: bool) -> str:
    """Prompt 9 mục → 1 đoạn văn cho tác nhân Flow (tương đương toFlowPrompt ở web)."""
    parts = {m.group(1).strip().upper(): m.group(2) for m in SECTION.finditer(prompt_text)}

    def get(k: str) -> str:
        return re.sub(r"\s+", " ", LOCK_TAG.sub("", parts.get(k, ""))).strip().rstrip(".;,")

    who, _, identity = get("NHÂN VẬT").partition(":")
    # Lặp NGUYÊN khối nhận diện (ngoại hình + trang phục) ở mọi cảnh để Flow không tự đổi mặt/trang phục
    out = [
        f"Tạo 1 video (không tạo hình ảnh) dọc 9:16, {duration_sec} giây, chuyển động tự nhiên, chân thực.",
        f"Nhân vật: {who.strip() or 'Nhân vật'} ({identity.strip() or 'ấm áp, nhẹ nhàng'}), giữ nguyên khuôn mặt, tóc, "
        "kính và trang phục đúng như nhân vật đã lưu trong dự án.",
    ]
    sections = [("LOẠI CẢNH", "Kiểu cảnh"), ("HÀNH ĐỘNG", "Hành động"), ("BỐI CẢNH", "Bối cảnh"),
                ("MÁY QUAY", "Máy quay"), ("ÁNH SÁNG", "Ánh sáng")]
    if speech_in_video:  # giọng do Flow đọc; ngược lại mục âm thanh ("giọng thoại rõ…") làm Flow tự tạo tiếng nói
        sections.append(("ÂM THANH", "Âm thanh"))
    for key, label in sections:
        if get(key):
            out.append(f"{label}: {get(key)}.")
    if get("THOẠI"):
        dialogue = get("THOẠI").replace(" / ", " ")
        out.append(f"Lời thoại: {dialogue}" if speech_in_video
                   else f"Khẩu hình nhân vật mấp máy theo câu (không phát thành tiếng): {dialogue}")
    if get("NEGATIVE PROMPT"):
        out.append(f"Tránh: {get('NEGATIVE PROMPT')}.")
    out += [f"Lưu ý: {n.strip().rstrip('.')}." for n in NOTE.findall(prompt_text)]  # quy tắc của template A03
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
        self.ingredients = list(self.config.get("ingredients", DEFAULT_INGREDIENTS))
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

    def _attach(self, page, box, name: str) -> bool:
        """Gõ "@" + tên → chọn trong 'Danh sách thành phần' → Flow chèn chip tham chiếu (nhân vật/ảnh) vào câu lệnh."""
        chips = box.locator(".mention-chip")
        before = chips.count()
        box.press("Control+End")
        page.keyboard.type(" @")  # "@" chỉ mở hộp chọn khi đứng sau khoảng trắng
        page.wait_for_timeout(1500)
        page.keyboard.type(name, delay=30)
        page.wait_for_timeout(2500)
        option = page.get_by_role("listbox", name=PICKER_LIST).get_by_role("option").filter(has_text=name)
        if not option.count():
            page.keyboard.press("Escape")
            return False
        option.first.click()
        page.wait_for_timeout(1200)
        return chips.count() > before

    def _try_download(self, page) -> tuple[str, str | None]:
        """Đang mở 1 nội dung: Tải xuống → 720p (kích thước gốc).
        ('ok', đường dẫn) | ('wait', None) chưa sẵn sàng | ('skip', None) không phải video."""
        btn = page.get_by_role("button", name=DOWNLOAD_BUTTON)
        if not btn.count():
            return "wait", None
        btn.first.click()
        items = page.get_by_role("menuitem")
        try:
            items.first.wait_for(timeout=5000)
        except Exception:  # noqa: BLE001 — chưa có menu: video còn đang xử lý
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
            dl.cancel()
            return "skip", None
        fd, path = tempfile.mkstemp(suffix=".mp4")
        os.close(fd)
        dl.save_as(path)
        if os.path.getsize(path) < 10000:
            raise ProviderError("File video Flow tải về quá nhỏ", code="DOWNLOAD_FAILED", retryable=False)
        return "ok", path

    def _first_tile_text(self, page) -> str:
        tile = page.locator(TILE).first
        return tile.inner_text() if tile.count() else ""

    def _wait_for_video(self, page) -> str | None:
        """Ô đầu lưới hiện % (đang tạo) → hết % (xong) → mở ô đó → tải 720p. Không đoán theo ảnh thu nhỏ
        (lưới tải trễ/URL ký số) và không dựa vào trang Flow tự mở (tác nhân có thể mở lại cảnh cũ)."""
        started = False
        now = time.monotonic()
        deadline, start_deadline = now + self.timeout_sec, now + min(START_TIMEOUT_SEC, self.timeout_sec)
        while time.monotonic() < deadline:
            page.wait_for_timeout(10000)
            if CHALLENGE.search(page.url):
                raise _NeedsManual("Flow chuyển sang trang đăng nhập/xác minh trong lúc tạo — xử lý trên Chrome Flow")
            if EDIT_ID.search(page.url):  # tác nhân tự mở trang chỉnh sửa → quay lại lưới để theo dõi ô mới
                page.goto(self.project_url, wait_until="domcontentloaded", timeout=60000)
                continue
            text = self._first_tile_text(page)
            if PROGRESS.search(text):
                started = True
                continue
            if not started:
                if time.monotonic() > start_deadline:
                    raise _NeedsManual("Flow chưa bắt đầu tạo video sau 5 phút (tác nhân có thể đang hỏi lại) — "
                                       "xem khung tác nhân trên Chrome Flow" + self._snapshot(page))
                continue
            if TILE_FAILED.search(text):
                raise _NeedsManual(f"Flow báo tạo video không thành công: {text.strip()[:200]}" + self._snapshot(page))
            page.locator(TILE).first.click()
            for _ in range(6):
                page.wait_for_timeout(3000)
                state, path = self._try_download(page)
                if state == "ok":
                    return path
                if state == "skip":
                    raise _NeedsManual("Nội dung mới nhất trên Flow không phải video" + self._snapshot(page))
            page.goto(self.project_url, wait_until="domcontentloaded", timeout=60000)
        return None

    def _snapshot(self, page) -> str:
        """Ảnh màn hình Flow lúc dừng để chẩn đoán (lỗi chụp không ảnh hưởng kết quả)."""
        try:
            fd, path = tempfile.mkstemp(prefix="flow_", suffix=".png")
            os.close(fd)
            page.screenshot(path=path)
            return f". Ảnh màn hình: {path}"
        except Exception:  # noqa: BLE001
            return ""

    def _generate(self, spec: GenerationSpec) -> str:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as pw:
            _, ctx = self._connect(pw)
            page = None
            try:
                page, box, problem = self._open_project(ctx)
                if problem:
                    return MANUAL + problem
                page.wait_for_timeout(3000)
                new_session = page.get_by_role("button", name=NEW_SESSION)
                if new_session.count():
                    new_session.first.click()
                    page.wait_for_timeout(1500)
                box.click()
                prompt = to_flow_prompt(spec.prompt_text, spec.duration_sec, self.speech_in_video)
                box.fill(prompt + (" Tham chiếu nhân vật và bối cảnh cửa hàng:" if self.ingredients else ""))
                missing = [n for n in self.ingredients if not self._attach(page, box, n)]
                if self.ingredients and len(missing) == len(self.ingredients):
                    # không gắn được gì → video sẽ lệch nhân vật/bối cảnh: dừng trước khi tốn lượt
                    return MANUAL + (f"Không tìm thấy thành phần {', '.join(missing)} trong dự án Flow "
                                     "(gõ @ trên Flow để kiểm tra tên) — chưa gửi tạo video")
                page.get_by_role("button", name=SUBMIT_BUTTON).click()
                try:
                    path = self._wait_for_video(page)
                except _NeedsManual as e:
                    return MANUAL + str(e)
                if path:
                    return OK + path
                return MANUAL + (f"Đã gửi lên Flow nhưng sau {self.timeout_sec // 60} phút chưa tải được video — "
                                 "kiểm tra trên Flow, tải MP4 rồi 'Nhập từ Flow' (không tự gửi lại để khỏi tốn lượt)"
                                 + self._snapshot(page))
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
