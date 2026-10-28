"""Schema dùng chung."""
import re as _re
from typing import Annotated, Generic, TypeVar

from pydantic import AfterValidator, BaseModel, ConfigDict

T = TypeVar("T")


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int = 1
    page_size: int = 50


class Message(BaseModel):
    ok: bool = True
    message: str = ""


_EMAIL_RE = _re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(\.[A-Za-z0-9\-]+)+$")


def _email(v: str) -> str:
    v = v.strip().lower()
    if len(v) > 255 or not _EMAIL_RE.match(v):
        raise ValueError("Email không hợp lệ")
    return v


Email = Annotated[str, AfterValidator(_email)]
