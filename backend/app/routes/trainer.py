"""
Blueprint de configurações do trainer — /api/trainer
Rotas para atualizar perfil, disponibilidade e preferências de agendamento.
Todas as rotas exigem trainer autenticado.
"""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required

from app.extensions import db
from app.utils.decorators import trainer_required

trainer_bp = Blueprint("trainer", __name__, url_prefix="/api/trainer")


# ------------------------------------------------------------------ #
#  Helpers                                                            #
# ------------------------------------------------------------------ #

def _success(data=None, message="", status=200):
    return jsonify({"success": True, "data": data, "message": message}), status


def _error(message="Erro", status=400, data=None):
    return jsonify({"success": False, "data": data, "message": message}), status


# Dias válidos: 1=seg, 2=ter, 3=qua, 4=qui, 5=sex, 6=sab, 7=dom
VALID_WEEKDAYS = {"1", "2", "3", "4", "5", "6", "7"}

# Durações de sessão permitidas (minutos)
VALID_DURATIONS = {30, 45, 60, 90}


def _validate_availability(availability: dict) -> str | None:
    """
    Valida o JSON de disponibilidade.
    Retorna mensagem de erro ou None se válido.
    Formato esperado: {"1": [{"start":"HH:MM","end":"HH:MM"}], ...}
    """
    if not isinstance(availability, dict):
        return "availability deve ser um objeto JSON."

    for day_key, blocks in availability.items():
        if day_key not in VALID_WEEKDAYS:
            return f"Chave de dia inválida: '{day_key}'. Use 1 (seg) a 7 (dom)."

        if not isinstance(blocks, list):
            return f"Blocos do dia {day_key} devem ser uma lista."

        for i, block in enumerate(blocks):
            if not isinstance(block, dict):
                return f"Bloco {i} do dia {day_key} deve ser um objeto."

            for field in ("start", "end"):
                val = block.get(field)
                if not val:
                    return f"Campo '{field}' ausente no bloco {i} do dia {day_key}."
                try:
                    h, m = val.split(":")
                    if not (0 <= int(h) <= 23 and 0 <= int(m) <= 59):
                        raise ValueError
                except (ValueError, AttributeError):
                    return f"Formato inválido para '{field}' no bloco {i} do dia {day_key}. Use HH:MM."

            # Garante que start < end
            if block["start"] >= block["end"]:
                return f"'start' deve ser anterior a 'end' no bloco {i} do dia {day_key}."

    return None


# ------------------------------------------------------------------ #
#  GET /api/trainer/availability                                      #
# ------------------------------------------------------------------ #

@trainer_bp.route("/availability", methods=["GET"])
@jwt_required()
@trainer_required
def get_availability(**kwargs):
    """
    Retorna a grade de disponibilidade semanal do trainer.
    Formato: {"1": [{"start":"HH:MM","end":"HH:MM"}], ..., "7": [...]}
    """
    trainer = kwargs["current_trainer"]

    # Usa default se ainda não configurou
    from app.routes.appointments import DEFAULT_AVAILABILITY
    availability = trainer.availability or DEFAULT_AVAILABILITY

    return _success(data={
        "availability": availability,
        "session_duration": trainer.session_duration,
        "cancellation_hours_policy": trainer.cancellation_hours_policy,
    })


# ------------------------------------------------------------------ #
#  PATCH /api/trainer/availability                                    #
# ------------------------------------------------------------------ #

@trainer_bp.route("/availability", methods=["PATCH"])
@jwt_required()
@trainer_required
def update_availability(**kwargs):
    """
    Atualiza a grade de disponibilidade semanal.
    Body: {
      "availability": {"1": [{"start":"08:00","end":"12:00"}], ...},
      "session_duration": 60,           (opcional)
      "cancellation_hours_policy": 24   (opcional)
    }
    """
    trainer = kwargs["current_trainer"]
    data = request.get_json(silent=True)
    if not data:
        return _error("Corpo da requisição inválido.", 400)

    # Atualiza grade de disponibilidade
    if "availability" in data:
        err = _validate_availability(data["availability"])
        if err:
            return _error(err, 422)
        trainer.availability = data["availability"]

    # Atualiza duração de sessão
    if "session_duration" in data:
        try:
            duration = int(data["session_duration"])
            if duration not in VALID_DURATIONS:
                return _error(f"Duração inválida. Use: {sorted(VALID_DURATIONS)} minutos.", 422)
            trainer.session_duration = duration
        except (ValueError, TypeError):
            return _error("session_duration deve ser um número inteiro.", 422)

    # Atualiza política de cancelamento
    if "cancellation_hours_policy" in data:
        try:
            hours = int(data["cancellation_hours_policy"])
            if hours < 0 or hours > 72:
                return _error("Política de cancelamento deve ser entre 0 e 72 horas.", 422)
            trainer.cancellation_hours_policy = hours
        except (ValueError, TypeError):
            return _error("cancellation_hours_policy deve ser um número inteiro.", 422)

    db.session.commit()

    return _success(
        data={
            "availability": trainer.availability,
            "session_duration": trainer.session_duration,
            "cancellation_hours_policy": trainer.cancellation_hours_policy,
        },
        message="Disponibilidade atualizada com sucesso.",
    )


# ------------------------------------------------------------------ #
#  PATCH /api/trainer/profile                                         #
# ------------------------------------------------------------------ #

@trainer_bp.route("/profile", methods=["PATCH"])
@jwt_required()
@trainer_required
def update_profile(**kwargs):
    """
    Atualiza perfil público do trainer.
    Campos atualizáveis: name, phone, bio, cref, avatar_url,
                         session_duration, cancellation_hours_policy, specializations.
    """
    trainer = kwargs["current_trainer"]
    data = request.get_json(silent=True)
    if not data:
        return _error("Corpo da requisição inválido.", 400)

    # Campos de texto simples
    for field in ("name", "phone", "bio", "cref", "avatar_url"):
        if field in data:
            value = (data[field] or "").strip() or None
            setattr(trainer, field, value)

    # name não pode ser vazio
    if "name" in data and not trainer.name:
        return _error("O nome não pode estar vazio.", 422)

    # Especializações — lista de strings
    if "specializations" in data:
        specs = data["specializations"]
        if not isinstance(specs, list):
            return _error("specializations deve ser uma lista.", 422)
        trainer.specializations = [str(s).strip() for s in specs if str(s).strip()]

    # Duração de sessão
    if "session_duration" in data:
        try:
            duration = int(data["session_duration"])
            if duration not in VALID_DURATIONS:
                return _error(f"Duração inválida. Use: {sorted(VALID_DURATIONS)} minutos.", 422)
            trainer.session_duration = duration
        except (ValueError, TypeError):
            return _error("session_duration deve ser um número inteiro.", 422)

    # Política de cancelamento
    if "cancellation_hours_policy" in data:
        try:
            hours = int(data["cancellation_hours_policy"])
            if hours < 0 or hours > 72:
                return _error("Política de cancelamento deve ser entre 0 e 72 horas.", 422)
            trainer.cancellation_hours_policy = hours
        except (ValueError, TypeError):
            return _error("cancellation_hours_policy deve ser um número inteiro.", 422)

    db.session.commit()

    return _success(
        data={"trainer": trainer.to_dict()},
        message="Perfil atualizado com sucesso.",
    )
