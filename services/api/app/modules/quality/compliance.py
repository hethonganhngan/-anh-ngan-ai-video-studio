"""Bộ lọc tuân thủ nội dung (xác định, không dùng LLM).

Quy tắc chính:
- Từ ngữ cấm theo Brand DNA (tuyệt đối hoá, công dụng y khoa…) → MAJOR.
- Quảng cáo sản phẩm dinh dưỡng thay thế sữa mẹ cho trẻ dưới 24 tháng (NĐ 100/2014/NĐ-CP) → CRITICAL.
- Tuyên bố chữa/điều trị bệnh → CRITICAL.
"""
import re
import unicodedata
from dataclasses import dataclass, asdict

SUBSTITUTE_PRODUCT = r"(sữa công thức|sữa bột|sữa bình|sữa thay thế|bình bú|núm vú giả|formula)"
UNDER_24M = (r"(dưới\s*24\s*tháng|dưới\s*2\s*tuổi|sơ sinh|0\s*[-–]\s*(6|12|24)\s*tháng|(\d|1\d|2[0-3])\s*tháng tuổi|"
             r"giai đoạn\s*1|trẻ nhỏ dưới 2)")
MEDICAL = r"(chữa\s+\w+|điều trị|đặc trị|trị\s+(dứt điểm|táo bón|biếng ăn|còi xương)|khỏi bệnh)"
ABSOLUTE = r"(100\s*%|tuyệt đối an toàn|cam kết tăng|không có tác dụng phụ)"


@dataclass
class ComplianceFinding:
    rule: str
    severity: str  # CRITICAL | MAJOR | MINOR
    match: str
    message: str

    def to_dict(self):
        return asdict(self)


def normalize(text: str) -> str:
    return unicodedata.normalize("NFC", text or "").lower()


def scan(text: str, forbidden_terms: list[str] | None = None) -> list[ComplianceFinding]:
    t = normalize(text)
    out: list[ComplianceFinding] = []
    for term in forbidden_terms or []:
        term_n = normalize(term)
        if term_n and term_n in t:
            out.append(ComplianceFinding("FORBIDDEN_TERM", "MAJOR", term, f"Dùng từ cấm theo Brand DNA: '{term}'"))
    for sentence in re.split(r"[.!?\n]", t):
        if re.search(SUBSTITUTE_PRODUCT, sentence) and re.search(UNDER_24M, sentence):
            out.append(ComplianceFinding("BMS_UNDER_24M", "CRITICAL", sentence.strip()[:120],
                                         "Có dấu hiệu quảng cáo sản phẩm thay thế sữa mẹ cho trẻ dưới 24 tháng (NĐ 100/2014/NĐ-CP)"))
    for m in re.finditer(MEDICAL, t):
        out.append(ComplianceFinding("MEDICAL_CLAIM", "CRITICAL", m.group(0), "Tuyên bố chữa/điều trị bệnh không được phép"))
    for m in re.finditer(ABSOLUTE, t):
        out.append(ComplianceFinding("ABSOLUTE_CLAIM", "MAJOR", m.group(0), "Tuyên bố tuyệt đối hoá chưa kiểm chứng"))
    seen, unique = set(), []
    for f in out:
        k = (f.rule, f.match)
        if k not in seen:
            seen.add(k)
            unique.append(f)
    return unique


def has_critical(findings: list[ComplianceFinding]) -> bool:
    return any(f.severity == "CRITICAL" for f in findings)
