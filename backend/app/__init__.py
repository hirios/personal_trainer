"""
Application Factory do FitFlow Pro.
Cria e configura a instância Flask com todas as extensões e blueprints.
"""
from flask import Flask
from app.config import config_map
from app.extensions import db, migrate, jwt, mail, cors, limiter


def create_app(config_name: str = "default") -> Flask:
    """
    Cria a aplicação Flask com a configuração especificada.

    Args:
        config_name: 'development', 'production', 'testing' ou 'default'.

    Returns:
        Instância Flask configurada e pronta para uso.
    """
    app = Flask(__name__)

    # --- Carrega configuração ---
    config_class = config_map.get(config_name, config_map["default"])
    app.config.from_object(config_class)

    # --- Inicializa extensões ---
    _init_extensions(app)

    # --- Registra blueprints ---
    _register_blueprints(app)

    # --- Registra handlers de erro globais ---
    _register_error_handlers(app)

    # --- Cria tabelas automaticamente em desenvolvimento ---
    # Em produção use: flask db upgrade
    if app.config.get("DEBUG") or app.config.get("TESTING"):
        with app.app_context():
            db.create_all()

    return app


def _init_extensions(app: Flask) -> None:
    """Inicializa todas as extensões Flask com a instância da aplicação."""
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    mail.init_app(app)
    limiter.init_app(app)

    # CORS: permite as origens configuradas em CORS_ORIGINS.
    # Wildcard "*" (usado em desenvolvimento) é incompatível com supports_credentials=True,
    # por isso o parâmetro é omitido quando origins for "*".
    origins = app.config["CORS_ORIGINS"]
    cors_kwargs = {"resources": {r"/api/*": {"origins": origins}}}
    if origins != "*":
        cors_kwargs["supports_credentials"] = True
    cors.init_app(app, **cors_kwargs)


def _register_blueprints(app: Flask) -> None:
    """Registra todos os blueprints da aplicação."""
    from app.routes.auth import auth_bp
    from app.routes.students import students_bp
    from app.routes.workouts import workouts_bp
    from app.routes.ai import ai_bp
    from app.routes.assessments import assessments_bp
    from app.routes.uploads import uploads_bp
    from app.routes.appointments import appointments_bp
    from app.routes.trainer import trainer_bp
    from app.routes.payments import payments_bp
    from app.routes.messages import messages_bp
    from app.routes.frontend import frontend_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(students_bp)
    app.register_blueprint(workouts_bp)
    app.register_blueprint(ai_bp)
    app.register_blueprint(assessments_bp)
    app.register_blueprint(uploads_bp)
    app.register_blueprint(appointments_bp)
    app.register_blueprint(trainer_bp)
    app.register_blueprint(payments_bp)
    app.register_blueprint(messages_bp)
    app.register_blueprint(frontend_bp)


def _register_error_handlers(app: Flask) -> None:
    """Handlers globais para erros HTTP comuns."""
    from flask import jsonify

    @app.errorhandler(400)
    def bad_request(e):
        return jsonify({"success": False, "data": None, "message": "Requisição inválida."}), 400

    @app.errorhandler(401)
    def unauthorized(e):
        return jsonify({"success": False, "data": None, "message": "Não autorizado."}), 401

    @app.errorhandler(403)
    def forbidden(e):
        return jsonify({"success": False, "data": None, "message": "Acesso negado."}), 403

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"success": False, "data": None, "message": "Recurso não encontrado."}), 404

    @app.errorhandler(405)
    def method_not_allowed(e):
        return jsonify({"success": False, "data": None, "message": "Método não permitido."}), 405

    @app.errorhandler(429)
    def ratelimit_handler(e):
        return jsonify({
            "success": False,
            "data": None,
            "message": f"Muitas requisições. Tente novamente em breve. {e.description}",
        }), 429

    @app.errorhandler(500)
    def internal_error(e):
        db.session.rollback()
        return jsonify({"success": False, "data": None, "message": "Erro interno do servidor."}), 500
