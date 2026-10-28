# Worker rendering

Engine FFmpeg nằm ở `services/api/app/modules/rendering/ffmpeg.py` (B06) và được worker gọi qua
`app.workflows.jobs.run_render_job`. Worker container cài FFmpeg + font DejaVu (hỗ trợ tiếng Việt) để burn phụ đề.
Queue: `render` (nặng CPU, nên chạy concurrency thấp), `generation`, `celery` (bảo trì).
