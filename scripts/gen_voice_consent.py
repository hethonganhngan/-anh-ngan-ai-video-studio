"""Sinh giấy đồng ý (consent) sử dụng giọng nói cho Voice Profile — PDF tiếng Việt.

Dùng:
    python3 scripts/gen_voice_consent.py                       # mẫu trống
    python3 scripts/gen_voice_consent.py --code VOI-2610-0004 --name "nữ tính" \
        --region "Miền Nam" --gender "Nữ" --age 35 \
        --tone "Nhẹ nhàng, ấm áp" --speed "Vừa phải" --source "Thu âm thủ công"

Cần: reportlab, font DejaVu (/usr/share/fonts/truetype/dejavu).
Đây là MẪU THAM KHẢO — cần pháp chế/luật sư rà soát trước khi sử dụng chính thức.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

FONT_DIR = Path("/usr/share/fonts/truetype/dejavu")
pdfmetrics.registerFont(TTFont("Serif", FONT_DIR / "DejaVuSerif.ttf"))
pdfmetrics.registerFont(TTFont("Serif-Bold", FONT_DIR / "DejaVuSerif-Bold.ttf"))
pdfmetrics.registerFont(TTFont("Sans", FONT_DIR / "DejaVuSans.ttf"))
pdfmetrics.registerFontFamily("Serif", normal="Serif", bold="Serif-Bold", italic="Serif", boldItalic="Serif-Bold")

BASE = ParagraphStyle("base", fontName="Serif", fontSize=9.5, leading=13, alignment=TA_JUSTIFY)
CENTER = ParagraphStyle("center", parent=BASE, alignment=TA_CENTER)
TITLE = ParagraphStyle("title", parent=CENTER, fontName="Serif-Bold", fontSize=13.5, leading=18, spaceBefore=6)
H = ParagraphStyle("h", parent=BASE, fontName="Serif-Bold", spaceBefore=6, spaceAfter=1)
ITEM = ParagraphStyle("item", parent=BASE, leftIndent=14, firstLineIndent=-10)
SMALL = ParagraphStyle("small", parent=BASE, fontName="Sans", fontSize=7.5, leading=10, textColor=colors.grey)

BOX = "<font name=\"Sans\">☐</font>"
DOTS = "." * 70


def blank(value: str | None, width: int = 60) -> str:
    return value if value else "." * width


def footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Sans", 7.5)
    canvas.setFillColor(colors.grey)
    canvas.drawString(18 * mm, 10 * mm, f"{doc.consent_no} · Mẫu tham khảo — cần pháp chế/luật sư rà soát trước khi sử dụng")
    canvas.drawRightString(A4[0] - 18 * mm, 10 * mm, f"Trang {doc.page}")
    canvas.restoreState()


def field_table(rows):
    t = Table([[Paragraph(k, BASE), Paragraph(v, BASE)] for k, v in rows], colWidths=[52 * mm, 122 * mm])
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
                           ("TOPPADDING", (0, 0), (-1, -1), 1.5), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
    return t


def build(args) -> Path:
    code = args.code or "VOI-" + "." * 12
    consent_no = f"CONSENT-{args.code}" if args.code else "CONSENT-VOI-............"
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(str(out), pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                            topMargin=13 * mm, bottomMargin=16 * mm,
                            title="Giấy đồng ý sử dụng giọng nói", author="Hệ thống Sữa Ánh Ngân")
    doc.consent_no = consent_no
    s = []
    p = lambda text, style=BASE: s.append(Paragraph(text, style))  # noqa: E731

    p("<b>CỘNG HOÀ XÃ HỘI CHỦ NGHĨA VIỆT NAM</b>", CENTER)
    p("<b>Độc lập – Tự do – Hạnh phúc</b>", CENTER)
    p("───────────", CENTER)
    p("GIẤY ĐỒNG Ý CHO PHÉP THU ÂM, SỬ DỤNG GIỌNG NÓI<br/>VÀ XỬ LÝ DỮ LIỆU CÁ NHÂN", TITLE)
    p(f"Số: {consent_no}", CENTER)
    s.append(Spacer(1, 6))
    p("Căn cứ Bộ luật Dân sự 2015 (Điều 32 về quyền của cá nhân đối với hình ảnh và quyền nhân thân); "
      "Nghị định 13/2023/NĐ-CP về bảo vệ dữ liệu cá nhân và các văn bản pháp luật hiện hành có liên quan; "
      "trên cơ sở tự nguyện, hai bên thống nhất như sau:")

    p("BÊN A – NGƯỜI CHO PHÉP SỬ DỤNG GIỌNG NÓI (Chủ thể dữ liệu)", H)
    s.append(field_table([
        ("Họ và tên:", DOTS), ("Ngày sinh:", DOTS), ("Số CCCD:", DOTS),
        ("Ngày cấp / Nơi cấp:", DOTS), ("Địa chỉ thường trú:", DOTS),
        ("Số điện thoại:", DOTS), ("Email:", DOTS),
    ]))

    p("BÊN B – BÊN SỬ DỤNG", H)
    s.append(field_table([
        ("Tên tổ chức:", "CÔNG TY TNHH THƯƠNG MẠI ÁNH NGÂN (Hệ thống Sữa Ánh Ngân)"),
        ("Mã số thuế:", DOTS), ("Địa chỉ:", DOTS),
        ("Người đại diện:", DOTS), ("Chức vụ:", DOTS),
    ]))

    p("ĐIỀU 1. ĐỐI TƯỢNG ĐỒNG Ý", H)
    p("Bên A đồng ý cho Bên B thu âm, lưu trữ và sử dụng giọng nói của Bên A, bao gồm các bản ghi âm mẫu "
      "(audio reference) và hồ sơ giọng nói (Voice Profile) được tạo từ các bản ghi này, cụ thể:")
    s.append(field_table([
        ("Mã Voice Profile:", code), ("Tên hồ sơ giọng:", blank(args.name)),
        ("Vùng miền / Giới tính:", f"{blank(args.region, 25)} / {blank(args.gender, 20)}"),
        ("Độ tuổi giọng:", blank(args.age, 20)), ("Chất giọng:", blank(args.tone)),
        ("Tốc độ đọc:", blank(args.speed)), ("Nguồn tạo giọng:", blank(args.source)),
    ]))
    p("Sau khi giấy này được ký và tải lên hệ thống, hồ sơ giọng nói sẽ được khoá (Voice Lock) để bảo đảm "
      "không bị chỉnh sửa ngoài phạm vi đã đồng ý.")

    p("ĐIỀU 2. MỤC ĐÍCH SỬ DỤNG (đánh dấu ☒ mục được đồng ý)", H)
    for item in ("Lồng tiếng video marketing, giới thiệu cửa hàng và sản phẩm được phép quảng cáo;",
                 "Nội dung chăm sóc khách hàng, hướng dẫn và tư vấn;",
                 "Tài liệu đào tạo nội bộ;",
                 "Tạo giọng đọc bằng công nghệ AI (chuyển văn bản thành giọng nói / mô phỏng giọng) từ mẫu giọng của Bên A;",
                 "Mục đích khác: " + "." * 50):
        p(f"{BOX} {item}", ITEM)
    p("Bên B không sử dụng giọng nói của Bên A cho bất kỳ mục đích nào ngoài các mục đã được đánh dấu.")

    p("ĐIỀU 3. PHẠM VI VÀ THỜI HẠN", H)
    p("Kênh sử dụng: " + "  ".join(f"{BOX} {c}" for c in ("Facebook", "TikTok", "YouTube", "Zalo",
                                                           "Website", "Màn hình tại cửa hàng")), ITEM)
    p(f"Lãnh thổ: {BOX} Việt Nam   {BOX} Toàn cầu (nền tảng trực tuyến)", ITEM)
    p("Thời hạn: từ ngày ....../....../20......  đến ngày ....../....../20......  "
      "(nếu để trống: 24 tháng kể từ ngày ký).", ITEM)

    p("ĐIỀU 4. CAM KẾT CỦA BÊN B", H)
    for i, item in enumerate((
        "Chỉ sử dụng giọng nói đúng mục đích, phạm vi và thời hạn tại Điều 2, Điều 3.",
        "Không dùng giọng nói của Bên A để tạo nội dung sai sự thật, xúc phạm, phản cảm, chính trị, "
        "lừa đảo, hoặc khiến người nghe hiểu nhầm rằng Bên A đã phát ngôn điều Bên A không nói.",
        "Không dùng giọng nói của Bên A trong quảng cáo trái pháp luật, bao gồm quảng cáo sản phẩm dinh dưỡng "
        "thay thế sữa mẹ dùng cho trẻ dưới 24 tháng tuổi theo Nghị định 100/2014/NĐ-CP; không tự tạo công dụng "
        "sản phẩm chưa được kiểm chứng.",
        "Không chuyển giao, bán hoặc cho bên thứ ba sử dụng mẫu giọng, trừ nhà cung cấp dịch vụ kỹ thuật "
        "(lưu trữ, chuyển văn bản thành giọng nói) có cam kết bảo mật và chỉ xử lý theo chỉ dẫn của Bên B.",
        "Lưu trữ bản ghi và hồ sơ giọng trên hệ thống có phân quyền, ghi nhật ký truy cập (audit log); "
        "chỉ người được giao nhiệm vụ mới được sử dụng.",
        "Gắn nhãn “nội dung có sử dụng giọng đọc AI” khi phát hành nội dung tạo bằng AI, theo quy định của "
        "nền tảng và pháp luật.",
        "Xoá bản ghi gốc và hồ sơ giọng khi hết thời hạn hoặc khi Bên A rút lại sự đồng ý, trừ trường hợp "
        "pháp luật yêu cầu lưu trữ.",
    ), 1):
        p(f"4.{i}. {item}", ITEM)

    p("ĐIỀU 5. QUYỀN CỦA BÊN A", H)
    p("Bên A có các quyền của chủ thể dữ liệu theo Nghị định 13/2023/NĐ-CP: được biết, đồng ý, truy cập, "
      "yêu cầu chỉnh sửa, xoá, hạn chế xử lý, phản đối xử lý, rút lại sự đồng ý, khiếu nại và yêu cầu bồi thường.")
    p("Bên A có thể rút lại sự đồng ý bất kỳ lúc nào bằng văn bản gửi Bên B. Trong vòng 72 giờ kể từ khi nhận "
      "văn bản, Bên B ngừng dùng giọng nói của Bên A cho nội dung mới; trong vòng 30 ngày, Bên B gỡ các nội dung "
      "đã đăng còn trong quyền kiểm soát của mình. Việc rút lại không ảnh hưởng đến tính hợp pháp của việc sử dụng "
      "trước thời điểm rút lại.")

    p("ĐIỀU 6. THÙ LAO", H)
    p(f"{BOX} Không có thù lao (Bên A tự nguyện).", ITEM)
    p(f"{BOX} Có thù lao: ......................................... VNĐ; hình thức thanh toán: ................................", ITEM)

    p("ĐIỀU 7. HIỆU LỰC", H)
    p("Giấy này có hiệu lực kể từ ngày ký, được lập thành 02 bản có giá trị như nhau, mỗi bên giữ 01 bản. "
      "Bản scan PDF được lưu cùng Voice Profile trong hệ thống Ánh Ngân AI Video Studio.")
    s.append(Spacer(1, 6))
    p(f"{BOX} Bên A xác nhận đã đọc, hiểu rõ nội dung, đã được giải thích về việc giọng nói có thể được mô phỏng "
      "bằng AI, và tự nguyện ký tên.", ITEM)

    sign = Table([
        [Paragraph("......................., ngày ...... tháng ...... năm 20......", CENTER), ""],
        [Paragraph("<b>BÊN A</b><br/>(Ký, ghi rõ họ tên)", CENTER),
         Paragraph("<b>ĐẠI DIỆN BÊN B</b><br/>(Ký, ghi rõ họ tên, đóng dấu)", CENTER)],
        ["", ""],
    ], colWidths=[87 * mm, 87 * mm], rowHeights=[None, None, 28 * mm])
    sign.setStyle(TableStyle([("SPAN", (0, 0), (1, 0)), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                              ("TOPPADDING", (0, 1), (-1, 1), 8)]))
    s.append(KeepTogether([Spacer(1, 8), sign]))

    doc.build(s, onFirstPage=footer, onLaterPages=footer)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--code"); ap.add_argument("--name"); ap.add_argument("--region")
    ap.add_argument("--gender"); ap.add_argument("--age"); ap.add_argument("--tone")
    ap.add_argument("--speed"); ap.add_argument("--source")
    ap.add_argument("--out", default="docs/templates/consent_giong_noi_MAU.pdf")
    print(build(ap.parse_args()))


if __name__ == "__main__":
    main()
