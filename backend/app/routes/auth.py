"""
Blueprint de autenticação — /api/auth
Rotas públicas de registro, login e gerenciamento de tokens JWT.
"""
from datetime import datetime, timezone
from flask import Blueprint, request, jsonify
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    jwt_required,
    get_jwt_identity,
    get_jwt,
)
from app.extensions import db, limiter
from app.models.user import User
from app.models.trainer import Trainer

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")

# Armazena refresh tokens invalidados (blocklist simples em memória).
# Em produção, substituir por Redis ou tabela no banco.
_refresh_token_blocklist: set[str] = set()


# ------------------------------------------------------------------ #
#  Helpers                                                            #
# ------------------------------------------------------------------ #

def _success(data=None, message="", status=200):
    return jsonify({"success": True, "data": data, "message": message}), status


def _error(message="Erro interno", status=400, data=None):
    return jsonify({"success": False, "data": data, "message": message}), status


# ------------------------------------------------------------------ #
#  Callback JWT — verificação de blocklist                            #
# ------------------------------------------------------------------ #

from app.extensions import jwt as jwt_manager  # importação circular segura


@jwt_manager.token_in_blocklist_loader
def check_if_token_revoked(jwt_header, jwt_payload):
    """Retorna True se o refresh token tiver sido invalidado via /logout."""
    return jwt_payload.get("jti") in _refresh_token_blocklist


# ------------------------------------------------------------------ #
#  POST /api/auth/register                                            #
# ------------------------------------------------------------------ #

@auth_bp.route("/register", methods=["POST"])
@limiter.limit("5 per hour")
def register():
    """
    Cadastra um novo personal trainer.
    Rate limit: 5 requisições por hora por IP.
    """
    data = request.get_json(silent=True)
    if not data:
        return _error("Corpo da requisição inválido ou ausente.", 400)

    # Validação dos campos obrigatórios
    required = ["name", "email", "password"]
    missing = [f for f in required if not data.get(f, "").strip()]
    if missing:
        return _error(f"Campos obrigatórios ausentes: {', '.join(missing)}.", 422)

    name = data["name"].strip()
    email = data["email"].strip().lower()
    password = data["password"]
    phone = (data.get("phone") or "").strip() or None
    cref  = (data.get("cref")  or "").strip() or None

    # Validação de tamanho mínimo da senha
    if len(password) < 8:
        return _error("A senha deve ter no mínimo 8 caracteres.", 422)

    # Verifica e-mail duplicado
    if User.query.filter_by(email=email).first():
        return _error("Este e-mail já está cadastrado.", 409)

    # Cria o trainer
    trainer = Trainer(
        name=name,
        email=email,
        phone=phone,
        cref=cref,
        role="trainer",
    )
    trainer.set_password(password)

    db.session.add(trainer)
    db.session.commit()

    # Gera tokens imediatamente para já logar após o cadastro
    access_token = create_access_token(identity=trainer.id)
    refresh_token = create_refresh_token(identity=trainer.id)

    return _success(
        data={
            "user": trainer.to_dict(),
            "access_token": access_token,
            "refresh_token": refresh_token,
        },
        message="Cadastro realizado com sucesso! Bem-vindo ao FitFlow Pro.",
        status=201,
    )


# ------------------------------------------------------------------ #
#  POST /api/auth/login                                               #
# ------------------------------------------------------------------ #

@auth_bp.route("/login", methods=["POST"])
@limiter.limit("20 per hour")
def login():
    """Autentica um usuário (trainer ou student) e retorna os tokens JWT."""
    data = request.get_json(silent=True)
    if not data:
        return _error("Corpo da requisição inválido ou ausente.", 400)

    email = data.get("email", "").strip().lower()
    password = data.get("password", "")

    if not email or not password:
        return _error("E-mail e senha são obrigatórios.", 422)

    user = User.query.filter_by(email=email).first()

    # Mensagem genérica para não revelar se o e-mail existe
    if not user or not user.check_password(password):
        return _error("E-mail ou senha incorretos.", 401)

    if not user.is_active:
        return _error("Conta desativada. Entre em contato com o suporte.", 403)

    access_token = create_access_token(identity=user.id)
    refresh_token = create_refresh_token(identity=user.id)

    return _success(
        data={
            "user": user.to_dict(),
            "access_token": access_token,
            "refresh_token": refresh_token,
        },
        message="Login realizado com sucesso.",
    )


# ------------------------------------------------------------------ #
#  POST /api/auth/refresh                                             #
# ------------------------------------------------------------------ #

@auth_bp.route("/refresh", methods=["POST"])
@jwt_required(refresh=True)
def refresh():
    """Renova o access_token usando um refresh_token válido."""
    user_id = get_jwt_identity()
    user = db.session.get(User, user_id)

    if not user or not user.is_active:
        return _error("Usuário não encontrado ou desativado.", 401)

    new_access_token = create_access_token(identity=user_id)

    return _success(
        data={"access_token": new_access_token},
        message="Token renovado com sucesso.",
    )


# ------------------------------------------------------------------ #
#  POST /api/auth/logout                                              #
# ------------------------------------------------------------------ #

@auth_bp.route("/logout", methods=["POST"])
@jwt_required(refresh=True)
def logout():
    """
    Invalida o refresh_token atual adicionando seu JTI à blocklist.
    O cliente deve descartar ambos os tokens do storage.
    """
    jti = get_jwt().get("jti")
    if jti:
        _refresh_token_blocklist.add(jti)

    return _success(message="Logout realizado com sucesso.")


# ------------------------------------------------------------------ #
#  GET /api/auth/me                                                   #
# ------------------------------------------------------------------ #

@auth_bp.route("/me", methods=["GET"])
@jwt_required()
def me():
    """Retorna os dados do usuário autenticado."""
    user_id = get_jwt_identity()
    user = db.session.get(User, user_id)

    if not user:
        return _error("Usuário não encontrado.", 404)

    return _success(data={"user": user.to_dict()})
