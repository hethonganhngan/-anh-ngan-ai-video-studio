"""Gộp router của 12 module + media + agents."""
from fastapi import APIRouter

from app.agents.router import router as agents_router
from app.api import auth
from app.media.router import router as media_router
from app.modules.administration.router import router as admin_router
from app.modules.analytics.router import router as analytics_router
from app.modules.characters.router import router as characters_router
from app.modules.feedback.router import router as feedback_router
from app.modules.generation.router import router as generation_router
from app.modules.learning.router import router as learning_router
from app.modules.projects.channels_router import router as channels_router
from app.modules.projects.router import router as projects_router
from app.modules.prompts.router import router as prompts_router
from app.modules.publishing.router import router as publishing_router
from app.modules.quality.router import router as quality_router
from app.modules.rendering.router import router as rendering_router
from app.modules.scripts.router import router as scripts_router

api_router = APIRouter()
for r in (auth.router, projects_router, channels_router, scripts_router, characters_router, prompts_router,
          generation_router, rendering_router, quality_router, feedback_router, learning_router, publishing_router,
          analytics_router, admin_router, agents_router, media_router):
    api_router.include_router(r)
