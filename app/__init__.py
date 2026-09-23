"""Application factory for the student attendance system."""

from __future__ import annotations

from flask import Flask

from config import Config


def create_app(test_config: dict | None = None) -> Flask:
    """Create and configure a Flask application instance.

    A factory keeps setup explicit and allows later tests to provide isolated
    configuration without changing the development entry point.
    """

    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(Config)

    if test_config is not None:
        app.config.update(test_config)
    Config.validate(app.config)

    from app.auth.routes import auth_bp
    from app.admin.routes import admin_bp
    from app.database import init_app as init_database
    from app.role_routes import role_bp
    from app.routes import main_bp
    from app.student.routes import student_bp
    from app.services.auth_service import (
        enforce_password_change_gate,
        enforce_student_enrollment_gate,
        load_current_user,
    )
    from app.services.csrf_service import issue_csrf_token, protect_mutating_request
    from app.services.storage_service import init_storage

    init_database(app)
    with app.app_context():
        init_storage()
    app.before_request(load_current_user)
    app.before_request(protect_mutating_request)
    app.before_request(enforce_password_change_gate)
    app.before_request(enforce_student_enrollment_gate)

    @app.after_request
    def prevent_private_caching(response):
        from flask import request
        if request.endpoint != "static":
            response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @app.context_processor
    def inject_csrf_token():
        return {"csrf_token": issue_csrf_token}

    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(role_bp)
    app.register_blueprint(student_bp)
    return app
