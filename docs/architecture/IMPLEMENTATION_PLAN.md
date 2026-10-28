# Kế hoạch triển khai

| Giai đoạn | Nội dung | Trạng thái |
|---|---|---|
| 0 — Khảo sát | Git, Node 22, Python 3.13, PostgreSQL 16, Redis 7, FFmpeg 6.1 + libass, Playwright 1.63. Docker CLI có, **daemon không chạy** trong môi trường build | ✅ |
| 1 — Foundation | Cấu trúc repo, 45 bảng + migration + trigger, Auth/RBAC/CSRF, seed (4 kênh, 10 agent, prompt, provider, ngân sách), layout + sidebar 15 màn hình | ✅ |
| 2 — Core Studio | B01–B04, A01–A04, state machine, Agent Registry/Runner | ✅ |
| 3 — Production | Provider adapters (Mock/Flow/Real API), Generation jobs, Object Storage, FFmpeg render, Celery queue/retry/recover | ✅ |
| 4 — Quality | QC 10 tiêu chí, phê duyệt, Feedback Loop 360°, CAPA, Lessons Learned + rollback | ✅ |
| 5 — Management | Publishing, Analytics, Dashboard CEO, Agent Control Center, Cost/Budget, Admin, Backup/Restore | ✅ |
| 6 — Verification | Unit + integration (pytest), E2E Playwright 15 màn hình, security review, Docker, tài liệu | ✅ (xem PROJECT_STATUS.md) |

## Lộ trình mở rộng (sau V2.0)

1. Kết nối API thật khi có quyền: Claude (đã có adapter), Veo/Vertex AI (điền cấu hình RealAPIProvider), TTS, Facebook/TikTok/YouTube/Zalo (adapter đã khung sẵn).
2. Timeline nâng cao (kéo thả đa track trên canvas, chuyển cảnh, hiệu ứng chữ).
3. Lip-sync và nhận diện khuôn mặt tự động để chấm tiêu chí Nhân vật/Khẩu hình bán tự động.
4. Lịch đăng tự động khi API nền tảng được cấp quyền (vẫn giữ phê duyệt người).
5. SSO (Google Workspace) và thông báo qua Zalo OA/Email.
