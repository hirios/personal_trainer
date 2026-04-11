"""
Blueprint de mensagens internas — /api/messages
Chat entre trainer e aluno com paginação reversa (infinite scroll).

Autenticação dupla:
  - Trainer: JWT via @trainer_required
  - Aluno: access_token no body ou query param (rotas públicas /student/*)
"""
from datetime import datetime, timezone
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from sqlalchemy import func

from app.extensions import db
from app.models.message import Message
from app.models.student import Student
from app.models.trainer import Trainer
from app.utils.decorators import trainer_required

messages_bp = Blueprint("messages", __name__, url_prefix="/api/messages")

# Mensagens retornadas por página (infinite scroll reverso)
PAGE_SIZE = 30


# ------------------------------------------------------------------ #
#  Helpers                                                            #
# ------------------------------------------------------------------ #

def _success(data=None, message="", status=200):
    return jsonify({"success": True, "data": data, "message": message}), status


def _error(message="Erro", status=400, data=None):
    return jsonify({"success": False, "data": data, "message": message}), status


def _get_student_for_trainer(student_id: str, trainer_id: str):
    """Busca aluno garantindo que pertence ao trainer. Retorna (student, None) ou (None, err)."""
    s = db.session.get(Student, student_id)
    if not s or s.trainer_id != trainer_id:
        return None, _error("Aluno não encontrado.", 404)
    return s, None


def _validate_content(content: str) -> str | None:
    """Valida o conteúdo da mensagem. Retorna mensagem de erro ou None se válido."""
    if not content:
        return "O conteúdo da mensagem não pode estar vazio."
    if len(content) > 4000:
        return "Mensagem muito longa (máx. 4000 caracteres)."
    return None


# ------------------------------------------------------------------ #
#  GET /api/messages/unread-count   (trainer)                         #
# ------------------------------------------------------------------ #

@messages_bp.route("/unread-count", methods=["GET"])
@jwt_required()
@trainer_required
def unread_count(**kwargs):
    """
    Retorna total de mensagens não lidas agrupadas por aluno.
    Apenas mensagens enviadas pelo aluno (sender_role='student') contam.
    Resultado: { unread: [{student_id, student_name, count}], total }
    """
    trainer = kwargs["current_trainer"]

    rows = (
        db.session.query(
            Message.student_id,
            Student.name.label("student_name"),
            func.count(Message.id).label("count"),
        )
        .join(Student, Student.id == Message.student_id)
        .filter(
            Message.trainer_id == trainer.id,
            Message.sender_role == "student",
            Message.is_read == False,
        )
        .group_by(Message.student_id, Student.name)
        .order_by(func.count(Message.id).desc())
        .all()
    )

    return _success(data={
        "unread": [
            {"student_id": r.student_id, "student_name": r.student_name, "count": r.count}
            for r in rows
        ],
        "total": sum(r.count for r in rows),
    })


# ------------------------------------------------------------------ #
#  GET /api/messages/student/preview   (público — aluno)             #
# ------------------------------------------------------------------ #

@messages_bp.route("/student/preview", methods=["GET"])
def student_preview():
    """
    Endpoint público — aluno consulta suas mensagens recentes e contagem de não lidas.
    Query param: access_token (obrigatório)
    Retorna: últimas 20 mensagens + unread_count (mensagens do trainer não lidas)
    """
    access_token = (request.args.get("access_token") or "").strip()
    if not access_token:
        return _error("access_token é obrigatório.", 422)

    student = Student.query.filter_by(access_token=access_token).first()
    if not student or not student.is_active:
        return _error("Link de acesso inválido ou expirado.", 404)

    mensagens = (
        Message.query
        .filter(
            Message.trainer_id == student.trainer_id,
            Message.student_id == student.id,
        )
        .order_by(Message.created_at.desc())
        .limit(20)
        .all()
    )
    mensagens = list(reversed(mensagens))  # cronológica

    # Mensagens do trainer que o aluno ainda não leu
    unread = Message.query.filter(
        Message.trainer_id == student.trainer_id,
        Message.student_id == student.id,
        Message.sender_role == "trainer",
        Message.is_read == False,
    ).count()

    return _success(data={
        "messages": [m.to_dict() for m in mensagens],
        "unread_count": unread,
        "trainer_id": student.trainer_id,
        "student_id": student.id,
    })


# ------------------------------------------------------------------ #
#  POST /api/messages/student   (público — aluno envia)              #
# ------------------------------------------------------------------ #

@messages_bp.route("/student", methods=["POST"])
def student_send():
    """
    Endpoint público — aluno envia mensagem ao trainer.
    Body: { access_token, content }
    """
    data = request.get_json(silent=True)
    if not data:
        return _error("Corpo da requisição inválido.", 400)

    access_token = (data.get("access_token") or "").strip()
    content = (data.get("content") or "").strip()

    if not access_token:
        return _error("access_token é obrigatório.", 422)

    err = _validate_content(content)
    if err:
        return _error(err, 422)

    student = Student.query.filter_by(access_token=access_token).first()
    if not student or not student.is_active:
        return _error("Link de acesso inválido ou expirado.", 404)

    trainer = db.session.get(Trainer, student.trainer_id)
    if not trainer or not trainer.is_active:
        return _error("Personal trainer não encontrado.", 404)

    msg = Message(
        trainer_id=trainer.id,
        student_id=student.id,
        sender_role="student",
        content=content,
        is_read=False,
    )
    db.session.add(msg)
    db.session.commit()

    return _success(
        data={"message": msg.to_dict()},
        message="Mensagem enviada ao seu personal trainer.",
        status=201,
    )


# ------------------------------------------------------------------ #
#  GET /api/messages/<student_id>   (trainer autenticado)            #
# ------------------------------------------------------------------ #

@messages_bp.route("/<student_id>", methods=["GET"])
@jwt_required()
@trainer_required
def get_messages(student_id, **kwargs):
    """
    Histórico de mensagens da conversa com o aluno, ordem ASC por created_at.
    Paginação reversa via `before_id`: retorna PAGE_SIZE mensagens anteriores ao id informado.
    Query param: before_id (opcional) — id da mensagem mais antiga já carregada.
    """
    trainer = kwargs["current_trainer"]
    _, err = _get_student_for_trainer(student_id, trainer.id)
    if err:
        return err

    query = Message.query.filter(
        Message.trainer_id == trainer.id,
        Message.student_id == student_id,
    )

    before_id = request.args.get("before_id")
    if before_id:
        pivot = db.session.get(Message, before_id)
        if pivot:
            query = query.filter(Message.created_at < pivot.created_at)

    mensagens = (
        query
        .order_by(Message.created_at.desc())
        .limit(PAGE_SIZE)
        .all()
    )
    mensagens = list(reversed(mensagens))  # retorna ASC (mais antigo primeiro)

    # Verifica se há mensagens ainda mais antigas
    has_more = False
    if mensagens:
        older = Message.query.filter(
            Message.trainer_id == trainer.id,
            Message.student_id == student_id,
            Message.created_at < mensagens[0].created_at,
        ).first()
        has_more = older is not None

    return _success(data={
        "messages": [m.to_dict() for m in mensagens],
        "has_more": has_more,
    })


# ------------------------------------------------------------------ #
#  POST /api/messages/   (trainer envia)                             #
# ------------------------------------------------------------------ #

@messages_bp.route("/", methods=["POST"])
@jwt_required()
@trainer_required
def send_message(**kwargs):
    """
    Trainer envia mensagem para um aluno.
    Body: { student_id, content }
    """
    trainer = kwargs["current_trainer"]
    data = request.get_json(silent=True)
    if not data:
        return _error("Corpo da requisição inválido.", 400)

    student_id = (data.get("student_id") or "").strip()
    content = (data.get("content") or "").strip()

    if not student_id:
        return _error("student_id é obrigatório.", 422)

    err = _validate_content(content)
    if err:
        return _error(err, 422)

    _, err = _get_student_for_trainer(student_id, trainer.id)
    if err:
        return err

    msg = Message(
        trainer_id=trainer.id,
        student_id=student_id,
        sender_role="trainer",
        content=content,
        is_read=False,
    )
    db.session.add(msg)
    db.session.commit()

    return _success(
        data={"message": msg.to_dict()},
        message="Mensagem enviada.",
        status=201,
    )


# ------------------------------------------------------------------ #
#  PATCH /api/messages/<student_id>/read   (trainer)                 #
# ------------------------------------------------------------------ #

@messages_bp.route("/<student_id>/read", methods=["PATCH"])
@jwt_required()
@trainer_required
def mark_as_read(student_id, **kwargs):
    """
    Marca todas as mensagens NÃO LIDAS do aluno (sender_role='student') como lidas.
    Chamado automaticamente ao abrir a aba de mensagens do aluno.
    """
    trainer = kwargs["current_trainer"]
    _, err = _get_student_for_trainer(student_id, trainer.id)
    if err:
        return err

    updated = (
        db.session.query(Message)
        .filter(
            Message.trainer_id == trainer.id,
            Message.student_id == student_id,
            Message.sender_role == "student",
            Message.is_read == False,
        )
        .update({"is_read": True}, synchronize_session=False)
    )
    db.session.commit()

    return _success(
        data={"updated": updated},
        message=f"{updated} mensagem(s) marcada(s) como lida(s).",
    )
