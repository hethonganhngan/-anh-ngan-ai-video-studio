"""Import toàn bộ model để Alembic và metadata nhận đủ bảng."""
from app.db.base import Base  # noqa: F401
from app.modules.administration.models import *  # noqa: F401,F403
from app.modules.projects.models import *  # noqa: F401,F403
from app.modules.scripts.models import *  # noqa: F401,F403
from app.modules.characters.models import *  # noqa: F401,F403
from app.modules.prompts.models import *  # noqa: F401,F403
from app.modules.generation.models import *  # noqa: F401,F403
from app.modules.rendering.models import *  # noqa: F401,F403
from app.modules.quality.models import *  # noqa: F401,F403
from app.modules.feedback.models import *  # noqa: F401,F403
from app.modules.learning.models import *  # noqa: F401,F403
from app.modules.publishing.models import *  # noqa: F401,F403
from app.modules.analytics.models import *  # noqa: F401,F403
from app.media.models import *  # noqa: F401,F403
from app.agents.models import *  # noqa: F401,F403
