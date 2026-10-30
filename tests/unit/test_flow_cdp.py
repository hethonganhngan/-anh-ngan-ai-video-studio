"""Flow tự động qua CDP (D21): dựng prompt, luồng gửi → chờ video mới → tải, các nhánh chờ thủ công — trình duyệt giả lập."""
import sys
import types

import pytest
from app.providers.video import flow_cdp as F
from app.providers.video.base import GenerationSpec, ProviderError
from app.providers.video.flow_cdp import FlowCDPProvider, to_flow_prompt

PROMPT = ("[1. LOẠI CẢNH] Talking Head\n[2. NHÂN VẬT] Mẹ Ánh Ngân [Character Lock CHR-2610-0003 v2]: ấm áp; đeo kính\n"
          "[3. HÀNH ĐỘNG] Mẹ Ánh Ngân chào khách\n[8. THOẠI] Chào cả nhà / hôm nay mình nói về sữa\n"
          "[9. NEGATIVE PROMPT] logo sai, chữ méo\nĐịnh dạng: video dọc 9:16, 8 giây\nLưu ý: da có khuyết điểm thật.")
MP4 = b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 20000


def test_prompt_one_paragraph_without_lock_tags():
    p = to_flow_prompt(PROMPT, 8, speech_in_video=False)
    assert p.startswith("Tạo 1 video (không tạo hình ảnh) dọc 9:16, 8 giây")
    # nguyên khối nhận diện được lặp lại ở mọi cảnh, bỏ mã khoá; quy tắc "Lưu ý" của template đi kèm
    assert "Nhân vật: Mẹ Ánh Ngân (ấm áp; đeo kính)," in p and "CHR-" not in p and "Character Lock" not in p
    assert "Lưu ý: da có khuyết điểm thật." in p and "Định dạng" not in p
    # Flow chỉ tạo hình: khẩu hình theo thoại nhưng không phát tiếng, bỏ mục âm thanh "giọng thoại rõ"
    assert "không phát thành tiếng): Chào cả nhà hôm nay mình nói về sữa" in p and "Tránh: logo sai, chữ méo." in p
    assert "Lời thoại:" not in p and "Âm thanh:" not in p
    assert F.NO_TEXT in p and F.SILENT_SPEECH in p and "\n" not in p
    spoken = to_flow_prompt(PROMPT + "\n[7. ÂM THANH] giọng thoại rõ", 8, speech_in_video=True)
    assert F.SILENT_SPEECH not in spoken and "Lời thoại: Chào cả nhà" in spoken and "Âm thanh: giọng thoại rõ." in spoken


def test_status_and_result_from_job_id():
    p = FlowCDPProvider("flow_cdp", "Flow", {})
    assert p.unit_cost_vnd_per_sec == 0 and p.estimate_cost(GenerationSpec(job_ref="j", prompt_text="x")) == 0
    assert p.get_status(F.OK + "C:/tmp/a.mp4").state == "SUCCEEDED" and p.get_result(F.OK + "C:/tmp/a.mp4") == "C:/tmp/a.mp4"
    st = p.get_status(F.MANUAL + "Flow yêu cầu đăng nhập")
    assert st.state == "NEEDS_MANUAL_ACTION" and st.error_message == "Flow yêu cầu đăng nhập"
    with pytest.raises(ProviderError):
        p.get_result(F.MANUAL + "x")


def test_cdp_only_localhost():
    with pytest.raises(ProviderError) as e:
        FlowCDPProvider("flow_cdp", "Flow", {"cdp_url": "http://10.0.0.5:9222"})._connect(object())
    assert e.value.code == "BAD_URL"


EDIT = F.DEFAULT_PROJECT + "/edit/33333333-3333-3333-3333-333333333333"


class FakeLocator:
    """Đủ dùng cho get_by_role/locator/filter/first của Playwright trong luồng Flow."""

    def __init__(self, page, kind, name=None, text=None):
        self.p, self.kind, self.name, self.text = page, kind, name, text

    @property
    def first(self):
        return self

    def _items(self):
        s = self.p.s
        if self.kind == "menuitem":
            items = ["720p / Kích thước gốc", "1080p / Đã tăng độ phân giải"] if s["menu"] else []
            return [i for i in items if self.text is None or self.text.search(i)]
        if self.kind == "button" and self.name == F.DOWNLOAD_BUTTON:
            return ["download"] if EDIT_ID_RE.search(self.p.url) else []
        if self.kind == "option":  # hộp chọn "@": chỉ có các thành phần đã lưu trong dự án Flow
            q = s["typed"].rsplit("@", 1)[-1]
            return [n for n in s["library"] if q and n.startswith(q) and (self.text is None or self.text in n)]
        if self.kind == "chip":
            return list(s["chips"])
        if self.kind == "tile":
            return ["tile"]
        return ["x"]

    def inner_text(self):  # ô đầu lưới: % khi đang tạo, tiêu đề khi xong
        s = self.p.s
        if s["clicked"] and not s["ready"] and s["ticks"] - s["clicked_at"] >= s.get("start_at", 1):
            return "45%"
        return s["first_tile"]

    def count(self):
        return len(self._items())

    def filter(self, has_text):
        return FakeLocator(self.p, self.kind, self.name, has_text)

    def get_by_role(self, role, name=None):
        return FakeLocator(self.p, role, name)

    def locator(self, sel):
        return FakeLocator(self.p, "chip" if "mention-chip" in sel else "other")

    def press(self, key):
        pass

    def wait_for(self, **_):
        if self.kind == "textbox" and self.p.s.get("redirect"):
            raise TimeoutError
        if not self._items():
            raise TimeoutError

    def fill(self, text):
        self.p.s["filled"] = text

    def click(self):
        s = self.p.s
        if self.kind == "button" and self.name == F.SUBMIT_BUTTON:
            assert s["filled"]
            s["clicked"], s["clicked_at"] = True, s["ticks"]
        elif self.kind == "button" and self.name == F.DOWNLOAD_BUTTON:
            s["menu"] = s["ready"]
        elif self.kind == "option":
            s["chips"].append(self._items()[0])
            s["typed"] = ""
        elif self.kind == "tile":
            self.p.url = EDIT
            s["opened"] = s["first_tile"]
        elif self.kind == "menuitem":
            s["downloads"].append(self.text.pattern)


class FakePage:
    def __init__(self, state):
        self.s, self.url = state, F.DEFAULT_PROJECT
        self.keyboard = types.SimpleNamespace(press=lambda k: state.update(menu=False, typed=""),
                                              type=lambda t, delay=0: state.update(typed=state["typed"] + t))

    def goto(self, url, **_):
        self.url = self.s.get("redirect", url)

    def get_by_role(self, role, name=None):
        return FakeLocator(self, role, name)

    def locator(self, sel):
        return FakeLocator(self, "tile" if sel == F.TILE else "other")

    def wait_for_url(self, pattern, **_):
        assert pattern.search(self.url)

    def wait_for_timeout(self, _):
        s = self.s
        s["ticks"] += 1
        if s["clicked"] and s["ticks"] - s["clicked_at"] >= s["ready_at"] and not s["ready"]:
            s["ready"] = True
            s["first_tile"] = "Mẹ tư vấn chọn sữa (mới)"

    def expect_download(self, **_):
        s = self.s

        class Ctx:
            def __enter__(self_inner):
                return types.SimpleNamespace(value=types.SimpleNamespace(
                    suggested_filename=s["file_name"], cancel=lambda: s.update(cancelled=True),
                    save_as=lambda path: open(path, "wb").write(MP4)))

            def __exit__(self_inner, *a):
                return False

        s["expected_download"] = True
        return Ctx()

    def close(self):
        self.s["closed"] = True

    def screenshot(self, path):
        open(path, "wb").write(b"png")


EDIT_ID_RE = F.EDIT_ID


@pytest.fixture
def fake_chrome(monkeypatch):
    s = {"first_tile": "Cửa hàng Ánh Ngân.jpg", "ticks": 0, "ready_at": 3, "ready": False, "clicked": False, "menu": False,
         "filled": None, "closed": False, "downloads": [], "typed": "", "chips": [],
         "library": ["Mẹ Ánh Ngân", "Cửa hàng Ánh Ngân.jpg"], "file_name": "Mẹ_tư_vấn_chọn_sữa_22222222.mp4"}
    ctx = types.SimpleNamespace(new_page=lambda: FakePage(s))
    browser = types.SimpleNamespace(contexts=[ctx])

    class PW:
        chromium = types.SimpleNamespace(connect_over_cdp=lambda url, timeout: browser)

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setitem(sys.modules, "playwright.sync_api", types.SimpleNamespace(sync_playwright=PW))
    monkeypatch.setattr(F.time, "monotonic", lambda: s["ticks"] * 10.0)  # mỗi lần chờ 10 giây giả
    return s


def test_generate_opens_new_item_and_downloads_original_720p(fake_chrome):
    job_id = FlowCDPProvider("flow_cdp", "Flow", {})._generate(GenerationSpec(job_ref="j", prompt_text=PROMPT))
    assert job_id.startswith(F.OK) and fake_chrome["closed"]
    assert fake_chrome["downloads"] == [F.QUALITY.pattern]  # chọn bản gốc 720p, không phải bản tăng độ phân giải
    with open(job_id[len(F.OK):], "rb") as f:
        assert f.read() == MP4
    assert "Mẹ Ánh Ngân chào khách" in fake_chrome["filled"]
    assert fake_chrome["chips"] == ["Mẹ Ánh Ngân", "Cửa hàng Ánh Ngân.jpg"]  # gắn nhân vật + ảnh cửa hàng trước khi tạo
    assert fake_chrome["opened"] == "Mẹ tư vấn chọn sữa (mới)"  # mở đúng ô vừa tạo xong, không phải nội dung cũ


def test_no_ingredient_found_stops_before_spending_credits(fake_chrome):
    fake_chrome["library"] = []
    job_id = FlowCDPProvider("flow_cdp", "Flow", {})._generate(GenerationSpec(job_ref="j", prompt_text=PROMPT))
    assert job_id.startswith(F.MANUAL) and "Không tìm thấy thành phần" in job_id and not fake_chrome["clicked"]


def test_timeout_needs_manual_without_resubmit(fake_chrome):
    fake_chrome["ready_at"] = 10**6
    job_id = FlowCDPProvider("flow_cdp", "Flow", {"timeout_min": 0})._generate(GenerationSpec(job_ref="j", prompt_text=PROMPT))
    assert job_id.startswith(F.MANUAL) and "không tự gửi lại" in job_id and fake_chrome["clicked"]


def test_login_page_needs_manual_and_nothing_submitted(fake_chrome):
    fake_chrome["redirect"] = "https://accounts.google.com/v3/signin"
    job_id = FlowCDPProvider("flow_cdp", "Flow", {})._generate(GenerationSpec(job_ref="j", prompt_text=PROMPT))
    assert job_id.startswith(F.MANUAL) and "đăng nhập" in job_id and not fake_chrome["clicked"]


def test_flow_never_starts_needs_manual_without_opening_old_items(fake_chrome):
    fake_chrome.update(start_at=10**6, ready_at=10**6)  # tác nhân không tạo gì (vd. hỏi lại)
    job_id = FlowCDPProvider("flow_cdp", "Flow", {})._generate(GenerationSpec(job_ref="j", prompt_text=PROMPT))
    assert job_id.startswith(F.MANUAL) and "chưa bắt đầu tạo" in job_id and "opened" not in fake_chrome
