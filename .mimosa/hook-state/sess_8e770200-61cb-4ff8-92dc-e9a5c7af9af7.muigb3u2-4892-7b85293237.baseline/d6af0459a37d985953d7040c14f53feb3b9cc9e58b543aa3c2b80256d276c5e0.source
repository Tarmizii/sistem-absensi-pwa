"""Local development entry point."""

from __future__ import annotations

import os

from app import create_app


app = create_app()


if __name__ == "__main__":
    app.run(
        host=os.getenv("HOST", app.config["HOST"]),
        port=int(os.getenv("PORT", str(app.config["PORT"]))),
        debug=app.config["DEBUG"],
    )
