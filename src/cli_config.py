"""

"""

from __future__ import annotations
from typing import TypedDict, Optional


class CronyConfiguration(TypedDict):
    course: str
    courses: str
    email: bool
    only: str
    cache: bool
    progress: bool
    settings: Optional[str]
    output: Optional[str]
    log: str
    # Whether to re-raise exceptions (unsafe) or suppress them (safe). Logs either way
    unsafe: bool
