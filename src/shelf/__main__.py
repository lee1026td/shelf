"""Enable ``python -m shelf`` as an alias for the ``shelf`` console script."""

from __future__ import annotations

from shelf.cli.app import main

if __name__ == "__main__":  # pragma: no cover - thin shim
    main()
