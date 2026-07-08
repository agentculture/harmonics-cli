"""Entry point for ``python -m harmonics``."""

from __future__ import annotations

import sys

from harmonics.cli import main

if __name__ == "__main__":
    sys.exit(main())
