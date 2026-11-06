"""M14 Skills: cắm skill (SKILL.md) vào agent dùng LLM, bật/tắt từng skill, ghép vào system prompt và ghi vào log chạy."""
from app.agents.router import parse_skill_md
from app.agents.runner import SkilledLLM

from tests.helpers import create_project

SKILL_MD = """---
name: Ánh Ngân DNA
description: Giọng thương hiệu ấm áp, chân thành
---
# DNA
Luôn xưng "mình", gọi khách là "ba mẹ". Không dùng từ tuyệt đối hoá.
"""


def test_parse_skill_md_frontmatter_and_fallback():
    p = parse_skill_md(SKILL_MD, "SKILL.md")
    assert p["name"] == "Ánh Ngân DNA" and p["description"].startswith("Giọng thương hiệu") and p["content"].startswith("# DNA")
    assert parse_skill_md("Chỉ có nội dung hướng dẫn", "quy-tac.md")["name"] == "quy-tac"


def test_skilled_llm_prepends_enabled_skills_to_system_prompt():
    class FakeLLM:
        code, model, is_real = "fake", "fake-1", False

        def complete_json(self, *, system, **kw):
            return system

    skill = type("S", (), {"code": "dna", "name": "DNA", "content": "Gọi khách là ba mẹ."})()
    llm = SkilledLLM(FakeLLM(), [skill])
    system = llm.complete_json(system="A02 viết kịch bản", prompt="x", schema={})
    assert "## Skill: DNA\nGọi khách là ba mẹ." in system and system.endswith("A02 viết kịch bản")
    assert llm.model == "fake-1" and llm.skill_codes == ["dna"]  # thuộc tính khác chuyển thẳng cho provider gốc


def test_skill_crud_toggle_and_runtime_injection(login, channels):
    admin, pm = login("admin"), login("pm")
    with_file = admin.post("/agents/skills/import", files={"file": ("SKILL.md", SKILL_MD.encode())}, data={"agent_codes": "A02"})
    assert with_file.status_code == 201, with_file.text
    skill = with_file.json()
    assert skill["code"] == "anh-ngan-dna" and skill["agent_codes"] == ["A02"] and skill["source"] == "UPLOAD"

    # Chỉ agent dùng LLM nhận skill; người không có quyền agent.manage không sửa được
    r = admin.patch(f"/agents/skills/{skill['id']}", json={"agent_codes": ["A02", "A07"]})
    assert r.status_code == 422 and r.json()["error"]["code"] == "SKILL_AGENT_NOT_LLM"
    assert pm.patch(f"/agents/skills/{skill['id']}", json={"is_enabled": False}).status_code == 403

    p = create_project(pm, channels["ANNGAN"]["id"], topic="Skill DNA vào A02", duration_sec=8)
    pm.post(f"/projects/{p['id']}/script/ideas")
    ex = admin.get(f"/agents/executions?agent_code=A02&project_id={p['id']}").json()["items"][0]
    assert ex["input_ref"]["skills"] == ["anh-ngan-dna"]

    # Tắt skill → lần chạy sau không dùng nữa
    assert admin.patch(f"/agents/skills/{skill['id']}", json={"is_enabled": False}).json()["is_enabled"] is False
    p2 = create_project(pm, channels["ANNGAN"]["id"], topic="Skill đã tắt", duration_sec=8)
    pm.post(f"/projects/{p2['id']}/script/ideas")
    ex2 = admin.get(f"/agents/executions?agent_code=A02&project_id={p2['id']}").json()["items"][0]
    assert "skills" not in ex2["input_ref"]

    second = admin.post("/agents/skills", json={"name": "Ánh Ngân DNA", "content": "Bản 2 của skill", "agent_codes": ["A08"]})
    assert second.status_code == 201 and second.json()["code"] == "anh-ngan-dna-2"
    assert admin.delete(f"/agents/skills/{second.json()['id']}").status_code == 204
    assert [s["code"] for s in admin.get("/agents/skills").json()] == ["anh-ngan-dna"]
    admin.delete(f"/agents/skills/{skill['id']}")
