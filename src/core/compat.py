"""Python 3.10 compatibility shim for datetime.UTC and other Python 3.11+ features."""
from __future__ import annotations

import sys

# Create UTC constant for Python < 3.11
if sys.version_info < (3, 11):
    from datetime import timezone as _timezone
    UTC = _timezone.utc
else:
    from datetime import UTC

__all__ = ["UTC"]
