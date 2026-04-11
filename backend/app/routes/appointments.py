"""
Blueprint de agendamentos — /api/appointments
Gestão completa de sessões entre trainer e alunos.
Rotas públicas: /available-slots e /book (acesso via access_token do aluno).
"""
from datetime import datetime, timedelta, timezone, time
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from sqlalchemy import and_, or_

from app.extensions import db
from app.models.appointment import Appointment
from app.models.student import Student
from app.models.trainer import Trainer
from app.utils.decorators import trainer_required

appointments_bp = Blueprint("appointments", __name__, url_prefix="/api/appointments")

# Status válidos para transições
VALID_STATUSES = {
    "scheduled", "confirmed", "completed",
    "cancelled_trainer", "cancelled_student", "no_show",
}

# Disponibilidade padrão quando o trainer não configurou: seg-sex, 06h–22h
DEFAULT_AVAILABILITY = {
    "1": [{"start": "06:00", "end": "22:00"}],
    "2": [{"start": "06:00", "end": "22:00"}],
    "3": [{"start": "06:00", "end": "22:00"}],
    "4": [{"start": "06:00", "end": "22:00"}],
    "5": [{"start": "06:00", "end": "22:00"}],
    "6": [],
    "7": [],
}


# ------------------------------------------------------------------ #
#  Helpers                                                            #
# ------------------------------------------------------------------ #

def _success(data=None, message="", status=200):
    return jsonify({"success": True, "data": data, "message": message}), status


def _error(message="Erro", status=400, data=None):
    return jsonify({"success": False, "data": data, "message": message}), status


def _parse_week(week_str: str):
    """
    Converte 'YYYY-WNN' em (datetime_segunda, datetime_domingo).
    Exemplo: '2026-W15' → (2026-04-06 00:00 UTC, 2026-04-12 23:59:59 UTC).
    Retorna (None, None) se o formato for inválido.
    """
    try:
        monday = datetime.strptime(f"{week_str}-1", "%G-W%V-%u").replace(
            tzinfo=timezone.utc
        )
        sunday_end = monday + timedelta(days=7) - timedelta(seconds=1)
        return monday, sunday_end
    except (ValueError, TypeError):
        return None, None


def _has_conflict(trainer_id: str, starts_at: datetime, ends_at: datetime, exclude_id: str = None) -> bool:
    """
    Verifica se existe agendamento ativo (não cancelado) que conflite
    com o intervalo [starts_at, ends_at[ para o trainer informado.
    """
    active_statuses = ["scheduled", "confirmed"]
    query = Appointment.query.filter(
        Appointment.trainer_id == trainer_id,
        Appointment.status.in_(active_statuses),
        Appointment.starts_at < ends_at,
        Appointment.ends_at > starts_at,
    )
    if exclude_id:
        query = query.filter(Appointment.id != exclude_id)

    return query.first() is not None


def _parse_datetime(value: str, field_name: str = "data/hora"):
    """
    Faz parse de uma string ISO 8601. Retorna (datetime_utc, None) ou (None, response_error).
    """
    if not value:
        return None, _error(f"{field_name} é obrigatório.", 422)
    try:
        dt = datetime.fromisoformat(value)
        # Normaliza para UTC se tiver fuso informado; assume UTC se não tiver
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)
        return dt, None
    except ValueError:
        return None, _error(f"Formato inválido para {field_name}. Use ISO 8601.", 422)


def _get_trainer_availability(trainer: Trainer) -> dict:
    """Retorna a grade de disponibilidade do trainer, usando default se não configurada."""
    return trainer.availability or DEFAULT_AVAILABILITY


def _slots_for_day(availability: dict, date: datetime.date, session_duration: int) -> list[dict]:
    """
    Gera lista de slots disponíveis para um dia com base na disponibilidade
    e duração de sessão do trainer.
    Retorna lista de {"start": "HH:MM", "end": "HH:MM"}.
    """
    iso_weekday = str(date.isoweekday())  # "1"=seg … "7"=dom
    day_blocks = availability.get(iso_weekday, [])
    slots = []

    for block in day_blocks:
        try:
            block_start = datetime.strptime(block["start"], "%H:%M").time()
            block_end = datetime.strptime(block["end"], "%H:%M").time()
        except (KeyError, ValueError):
            continue

        # Avança em incrementos de session_duration
        current = datetime.combine(date, block_start)
        end_limit = datetime.combine(date, block_end)

        while current + timedelta(minutes=session_duration) <= end_limit:
            slot_end = current + timedelta(minutes=session_duration)
            slots.append({
                "start": current.strftime("%H:%M"),
                "end": slot_end.strftime("%H:%M"),
            })
            current = slot_end

    return slots


def _get_appointment_or_404(appointment_id: str, trainer_id: str):
    """Busca agendamento garantindo que pertence ao trainer. Retorna (appointment, None) ou (None, err)."""
    appt = db.session.get(Appointment, appointment_id)
    if not appt or appt.trainer_id != trainer_id:
        return None, _error("Agendamento não encontrado.", 404)
    return appt, None


# ------------------------------------------------------------------ #
#  GET /api/appointments/?week=YYYY-WNN                               #
# ------------------------------------------------------------------ #

@appointments_bp.route("/", methods=["GET"])
@jwt_required()
@trainer_required
def list_appointments(**kwargs):
    """
    Retorna todos os agendamentos do trainer para uma semana específica.
    Query param: week=YYYY-WNN (default = semana atual).
    """
    trainer = kwargs["current_trainer"]

    week_str = request.args.get("week")
    if not week_str:
        # Calcula a semana atual no formato ISO
        now = datetime.now(timezone.utc)
        week_str = now.strftime("%G-W%V")

    week_start, week_end = _parse_week(week_str)
    if week_start is None:
        return _error("Formato de semana inválido. Use YYYY-WNN (ex: 2026-W15).", 422)

    appointments = (
        Appointment.query
        .filter(
            Appointment.trainer_id == trainer.id,
            Appointment.starts_at >= week_start,
            Appointment.starts_at <= week_end,
        )
        .order_by(Appointment.starts_at.asc())
        .all()
    )

    return _success(data={
        "week": week_str,
        "week_start": week_start.isoformat(),
        "week_end": week_end.isoformat(),
        "appointments": [a.to_dict() for a in appointments],
    })


# ------------------------------------------------------------------ #
#  POST /api/appointments/                                            #
# ------------------------------------------------------------------ #

@appointments_bp.route("/", methods=["POST"])
@jwt_required()
@trainer_required
def create_appointment(**kwargs):
    """
    Cria novo agendamento. Valida conflito de horário.
    Body: student_id, starts_at, ends_at (ou duration_min), location, notes
    """
    trainer = kwargs["current_trainer"]
    data = request.get_json(silent=True)
    if not data:
        return _error("Corpo da requisição inválido.", 400)

    # Parse de horários
    starts_at, err = _parse_datetime(data.get("starts_at"), "starts_at")
    if err:
        return err

    # ends_at pode ser calculado a partir de duration_min
    if data.get("ends_at"):
        ends_at, err = _parse_datetime(data.get("ends_at"), "ends_at")
        if err:
            return err
    elif data.get("duration_min"):
        try:
            duration = int(data["duration_min"])
            if duration <= 0:
                raise ValueError
        except (ValueError, TypeError):
            return _error("duration_min deve ser um número inteiro positivo.", 422)
        ends_at = starts_at + timedelta(minutes=duration)
    else:
        # Usa duração padrão do trainer
        ends_at = starts_at + timedelta(minutes=trainer.session_duration)

    if ends_at <= starts_at:
        return _error("ends_at deve ser posterior a starts_at.", 422)

    # Valida aluno (opcional — permite criar slot bloqueado sem aluno)
    student_id = data.get("student_id") or None
    if student_id:
        student = db.session.get(Student, student_id)
        if not student or student.trainer_id != trainer.id:
            return _error("Aluno não encontrado.", 404)

    # Verifica conflito de horário
    if _has_conflict(trainer.id, starts_at, ends_at):
        return _error("Conflito de horário: já existe um agendamento nesse período.", 409)

    appt = Appointment(
        trainer_id=trainer.id,
        student_id=student_id,
        starts_at=starts_at,
        ends_at=ends_at,
        status="scheduled",
        location=(data.get("location") or "").strip() or None,
        notes=(data.get("notes") or "").strip() or None,
    )
    db.session.add(appt)
    db.session.commit()

    return _success(
        data={"appointment": appt.to_dict()},
        message="Agendamento criado com sucesso.",
        status=201,
    )


# ------------------------------------------------------------------ #
#  GET /api/appointments/<id>                                         #
# ------------------------------------------------------------------ #

@appointments_bp.route("/<appointment_id>", methods=["GET"])
@jwt_required()
@trainer_required
def get_appointment(appointment_id, **kwargs):
    """Retorna detalhes completos de um agendamento."""
    trainer = kwargs["current_trainer"]
    appt, err = _get_appointment_or_404(appointment_id, trainer.id)
    if err:
        return err

    return _success(data={"appointment": appt.to_dict()})


# ------------------------------------------------------------------ #
#  PATCH /api/appointments/<id>                                       #
# ------------------------------------------------------------------ #

@appointments_bp.route("/<appointment_id>", methods=["PATCH"])
@jwt_required()
@trainer_required
def update_appointment(appointment_id, **kwargs):
    """Edita hora, local ou notas de um agendamento não cancelado."""
    trainer = kwargs["current_trainer"]
    appt, err = _get_appointment_or_404(appointment_id, trainer.id)
    if err:
        return err

    if appt.status in ("cancelled_trainer", "cancelled_student", "completed", "no_show"):
        return _error("Não é possível editar um agendamento já encerrado.", 422)

    data = request.get_json(silent=True)
    if not data:
        return _error("Corpo da requisição inválido.", 400)

    # Atualiza horários se fornecidos
    new_starts = appt.starts_at
    new_ends = appt.ends_at

    if "starts_at" in data:
        new_starts, err = _parse_datetime(data["starts_at"], "starts_at")
        if err:
            return err

    if "ends_at" in data:
        new_ends, err = _parse_datetime(data["ends_at"], "ends_at")
        if err:
            return err
    elif "duration_min" in data:
        try:
            duration = int(data["duration_min"])
            if duration <= 0:
                raise ValueError
        except (ValueError, TypeError):
            return _error("duration_min deve ser um inteiro positivo.", 422)
        new_ends = new_starts + timedelta(minutes=duration)

    if new_ends <= new_starts:
        return _error("ends_at deve ser posterior a starts_at.", 422)

    # Verifica conflito (excluindo o próprio agendamento)
    if (new_starts != appt.starts_at or new_ends != appt.ends_at):
        if _has_conflict(trainer.id, new_starts, new_ends, exclude_id=appt.id):
            return _error("Conflito de horário: já existe um agendamento nesse período.", 409)

    appt.starts_at = new_starts
    appt.ends_at = new_ends

    # Atualiza campos simples
    if "location" in data:
        appt.location = (data["location"] or "").strip() or None
    if "notes" in data:
        appt.notes = (data["notes"] or "").strip() or None
    if "status" in data and data["status"] in VALID_STATUSES:
        appt.status = data["status"]
    if "student_id" in data:
        sid = data["student_id"] or None
        if sid:
            student = db.session.get(Student, sid)
            if not student or student.trainer_id != trainer.id:
                return _error("Aluno não encontrado.", 404)
        appt.student_id = sid

    db.session.commit()

    return _success(
        data={"appointment": appt.to_dict()},
        message="Agendamento atualizado com sucesso.",
    )


# ------------------------------------------------------------------ #
#  POST /api/appointments/<id>/cancel                                 #
# ------------------------------------------------------------------ #

@appointments_bp.route("/<appointment_id>/cancel", methods=["POST"])
@jwt_required()
@trainer_required
def cancel_appointment(appointment_id, **kwargs):
    """
    Cancela um agendamento registrando motivo e timestamp.
    Body: reason (opcional)
    """
    trainer = kwargs["current_trainer"]
    appt, err = _get_appointment_or_404(appointment_id, trainer.id)
    if err:
        return err

    if appt.status in ("cancelled_trainer", "cancelled_student", "completed", "no_show"):
        return _error("Este agendamento já foi encerrado.", 422)

    data = request.get_json(silent=True) or {}

    appt.status = "cancelled_trainer"
    appt.cancellation_reason = (data.get("reason") or "").strip() or None
    appt.cancelled_at = datetime.now(timezone.utc)

    db.session.commit()

    return _success(
        data={"appointment": appt.to_dict()},
        message="Agendamento cancelado.",
    )


# ------------------------------------------------------------------ #
#  POST /api/appointments/<id>/complete                               #
# ------------------------------------------------------------------ #

@appointments_bp.route("/<appointment_id>/complete", methods=["POST"])
@jwt_required()
@trainer_required
def complete_appointment(appointment_id, **kwargs):
    """Marca agendamento como concluído."""
    trainer = kwargs["current_trainer"]
    appt, err = _get_appointment_or_404(appointment_id, trainer.id)
    if err:
        return err

    if appt.status in ("cancelled_trainer", "cancelled_student", "no_show"):
        return _error("Não é possível concluir um agendamento cancelado.", 422)
    if appt.status == "completed":
        return _error("Agendamento já está concluído.", 422)

    appt.status = "completed"
    db.session.commit()

    return _success(
        data={"appointment": appt.to_dict()},
        message="Sessão marcada como concluída.",
    )


# ------------------------------------------------------------------ #
#  GET /api/appointments/available-slots (público)                    #
# ------------------------------------------------------------------ #

@appointments_bp.route("/available-slots", methods=["GET"])
def available_slots():
    """
    Endpoint público — retorna horários disponíveis do trainer para um dia.
    Query params: trainer_id (obrigatório), date=YYYY-MM-DD (obrigatório).
    """
    trainer_id = request.args.get("trainer_id")
    date_str = request.args.get("date")

    if not trainer_id or not date_str:
        return _error("trainer_id e date são obrigatórios.", 422)

    try:
        target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return _error("Formato de date inválido. Use YYYY-MM-DD.", 422)

    trainer = db.session.get(Trainer, trainer_id)
    if not trainer or not trainer.is_active:
        return _error("Trainer não encontrado.", 404)

    availability = _get_trainer_availability(trainer)
    all_slots = _slots_for_day(availability, target_date, trainer.session_duration)

    if not all_slots:
        return _success(data={"date": date_str, "slots": [], "session_duration": trainer.session_duration})

    # Busca agendamentos ativos do dia para filtrar conflitos
    day_start = datetime.combine(target_date, time(0, 0), tzinfo=timezone.utc)
    day_end = datetime.combine(target_date, time(23, 59, 59), tzinfo=timezone.utc)

    existing = Appointment.query.filter(
        Appointment.trainer_id == trainer_id,
        Appointment.status.in_(["scheduled", "confirmed"]),
        Appointment.starts_at >= day_start,
        Appointment.starts_at <= day_end,
    ).all()

    # Filtra slots que conflitem com agendamentos existentes
    available = []
    for slot in all_slots:
        slot_start = datetime.combine(target_date, datetime.strptime(slot["start"], "%H:%M").time(), tzinfo=timezone.utc)
        slot_end = datetime.combine(target_date, datetime.strptime(slot["end"], "%H:%M").time(), tzinfo=timezone.utc)

        conflict = any(
            slot_start < appt.ends_at and slot_end > appt.starts_at
            for appt in existing
        )
        if not conflict:
            available.append(slot)

    return _success(data={
        "date": date_str,
        "trainer_id": trainer_id,
        "session_duration": trainer.session_duration,
        "slots": available,
    })


# ------------------------------------------------------------------ #
#  GET /api/appointments/student (público — próximas sessões aluno)   #
# ------------------------------------------------------------------ #

@appointments_bp.route("/student", methods=["GET"])
def student_appointments():
    """
    Endpoint público — retorna os próximos agendamentos do aluno.
    Query param: access_token (obrigatório)
    Retorna até 3 sessões futuras com status scheduled ou confirmed.
    """
    access_token = (request.args.get("access_token") or "").strip()
    if not access_token:
        return _error("access_token é obrigatório.", 422)

    student = Student.query.filter_by(access_token=access_token).first()
    if not student or not student.is_active:
        return _error("Link de acesso inválido ou expirado.", 404)

    now = datetime.now(timezone.utc)

    upcoming = (
        Appointment.query
        .filter(
            Appointment.student_id == student.id,
            Appointment.starts_at > now,
            Appointment.status.in_(["scheduled", "confirmed"]),
        )
        .order_by(Appointment.starts_at.asc())
        .limit(3)
        .all()
    )

    return _success(data={
        "appointments": [a.to_dict(include_student=False, include_trainer=True) for a in upcoming],
    })


# ------------------------------------------------------------------ #
#  POST /api/appointments/book (público — aluno agenda via token)     #
# ------------------------------------------------------------------ #

@appointments_bp.route("/book", methods=["POST"])
def book_appointment():
    """
    Endpoint público para aluno agendar horário.
    Body: access_token, starts_at, notes (opcional)
    O ends_at é calculado com a duração padrão do trainer.
    """
    data = request.get_json(silent=True)
    if not data:
        return _error("Corpo da requisição inválido.", 400)

    access_token = (data.get("access_token") or "").strip()
    if not access_token:
        return _error("access_token é obrigatório.", 422)

    # Valida o aluno pelo access_token
    student = Student.query.filter_by(access_token=access_token).first()
    if not student or not student.is_active:
        return _error("Link de acesso inválido ou expirado.", 404)

    trainer = db.session.get(Trainer, student.trainer_id)
    if not trainer or not trainer.is_active:
        return _error("Personal trainer não encontrado.", 404)

    # Parse do horário
    starts_at, err = _parse_datetime(data.get("starts_at"), "starts_at")
    if err:
        return err

    ends_at = starts_at + timedelta(minutes=trainer.session_duration)

    # Verifica se está dentro da disponibilidade
    availability = _get_trainer_availability(trainer)
    available_slots_list = _slots_for_day(availability, starts_at.date(), trainer.session_duration)
    slot_start_str = starts_at.strftime("%H:%M")
    slot_match = any(s["start"] == slot_start_str for s in available_slots_list)
    if not slot_match:
        return _error("Este horário não está disponível na agenda do personal trainer.", 422)

    # Verifica conflito
    if _has_conflict(trainer.id, starts_at, ends_at):
        return _error("Este horário não está mais disponível. Escolha outro.", 409)

    appt = Appointment(
        trainer_id=trainer.id,
        student_id=student.id,
        starts_at=starts_at,
        ends_at=ends_at,
        status="scheduled",
        notes=(data.get("notes") or "").strip() or None,
    )
    db.session.add(appt)
    db.session.commit()

    return _success(
        data={"appointment": appt.to_dict(include_trainer=True)},
        message="Agendamento realizado com sucesso! Aguarde a confirmação do seu personal trainer.",
        status=201,
    )
