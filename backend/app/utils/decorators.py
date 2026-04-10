"""
Decorators de autorização por papel (role).
Uso:
    @jwt_required()
    @trainer_required
    def minha_rota(**kwargs):
        trainer = kwargs['current_trainer']
"""
from functools import wraps
from flask import jsonify
from flask_jwt_extended import get_jwt_identity
from app.extensions import db


def trainer_required(fn):
    """
    Exige que o usuário autenticado seja um Trainer ativo.
    Injeta `current_trainer` nos kwargs da função decorada.
    Deve ser usado APÓS @jwt_required().
    """

    @wraps(fn)
    def wrapper(*args, **kwargs):
        from app.models.trainer import Trainer

        user_id = get_jwt_identity()
        trainer = db.session.get(Trainer, user_id)

        if not trainer:
            return (
                jsonify(
                    {
                        "success": False,
                        "data": None,
                        "message": "Acesso restrito a personal trainers.",
                    }
                ),
                403,
            )

        if not trainer.is_active:
            return (
                jsonify(
                    {
                        "success": False,
                        "data": None,
                        "message": "Conta de trainer desativada. Entre em contato com o suporte.",
                    }
                ),
                403,
            )

        kwargs["current_trainer"] = trainer
        return fn(*args, **kwargs)

    return wrapper


def student_required(fn):
    """
    Exige que o usuário autenticado seja um Student ativo.
    Injeta `current_student` nos kwargs da função decorada.
    Deve ser usado APÓS @jwt_required().
    """

    @wraps(fn)
    def wrapper(*args, **kwargs):
        from app.models.student import Student

        user_id = get_jwt_identity()
        student = db.session.get(Student, user_id)

        if not student:
            return (
                jsonify(
                    {
                        "success": False,
                        "data": None,
                        "message": "Acesso restrito a alunos.",
                    }
                ),
                403,
            )

        if not student.is_active:
            return (
                jsonify(
                    {
                        "success": False,
                        "data": None,
                        "message": "Conta de aluno desativada. Entre em contato com seu personal trainer.",
                    }
                ),
                403,
            )

        kwargs["current_student"] = student
        return fn(*args, **kwargs)

    return wrapper
