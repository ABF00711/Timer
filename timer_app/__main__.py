from __future__ import annotations

import sys

from timer_app.app import TimerApplication


def main() -> int:
    app = TimerApplication()
    return app.run()


if __name__ == "__main__":
    sys.exit(main())
