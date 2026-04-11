"""
Blueprint de configurações do trainer — /api/trainer
Rotas para atualizar perfil, disponibilidade e preferências de agendamento.
Todas as rotas exigem trainer autenticado.
"""
from datetime import datetime, timezone, timedelta

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from sqlalchemy import func, or_

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


# ------------------------------------------------------------------ #
#  Helpers internos do dashboard                                      #
# ------------------------------------------------------------------ #

def _subtract_months(dt: datetime, months: int) -> datetime:
    """Subtrai N meses de um datetime e retorna com day=1, hora zerada."""
    month = dt.month - months
    year = dt.year
    while month <= 0:
        month += 12
        year -= 1
    return dt.replace(year=year, month=month, day=1,
                      hour=0, minute=0, second=0, microsecond=0)


# ------------------------------------------------------------------ #
#  GET /api/trainer/dashboard                                         #
# ------------------------------------------------------------------ #

@trainer_bp.route("/dashboard", methods=["GET"])
@jwt_required()
@trainer_required
def get_dashboard(**kwargs):
    """
    Retorna todos os dados do dashboard do trainer em um único request:
    métricas, agendamentos de hoje, alertas, atividade recente, histórico MRR
    e distribuição de objetivos.
    """
    from app.models import Student, Payment, Appointment, Workout, Message

    trainer = kwargs["current_trainer"]
    # SQLite armazena datetimes sem timezone; usamos naive UTC para comparações com o banco
    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end   = now.replace(hour=23, minute=59, second=59, microsecond=999999)
    first_of_month   = today_start.replace(day=1)
    prev_month_start = _subtract_months(first_of_month, 1)
    seven_days_ago   = now - timedelta(days=7)
    thirty_days_ago  = now - timedelta(days=30)

    # --- Alunos ativos ---
    students_active_count = Student.query.filter_by(
        trainer_id=trainer.id, status="active"
    ).count()

    # Novos alunos este mês (delta para exibir "▲ N este mês")
    students_delta = Student.query.filter(
        Student.trainer_id == trainer.id,
        Student.created_at >= first_of_month,
    ).count()

    # --- MRR atual e anterior ---
    mrr_current = float(
        db.session.query(func.sum(Payment.amount)).filter(
            Payment.trainer_id == trainer.id,
            Payment.status == "paid",
            Payment.paid_at >= first_of_month,
        ).scalar() or 0
    )
    mrr_prev = float(
        db.session.query(func.sum(Payment.amount)).filter(
            Payment.trainer_id == trainer.id,
            Payment.status == "paid",
            Payment.paid_at >= prev_month_start,
            Payment.paid_at < first_of_month,
        ).scalar() or 0
    )
    mrr_delta = round(mrr_current - mrr_prev, 2)

    # --- Inadimplentes ---
    overdue_count = Student.query.filter_by(
        trainer_id=trainer.id, status="pending_payment"
    ).count()

    # --- Agendamentos de hoje (max 5, ordenados por horário) ---
    today_appts = Appointment.query.filter(
        Appointment.trainer_id == trainer.id,
        Appointment.starts_at >= today_start,
        Appointment.starts_at <= today_end,
        Appointment.status.in_(["scheduled", "confirmed"]),
    ).order_by(Appointment.starts_at.asc()).limit(5).all()

    # Próxima sessão ainda não iniciada
    next_appt = next(
        (a for a in today_appts if a.starts_at > now),
        today_appts[0] if today_appts else None,
    )

    # --- Alunos em risco: sem acesso 7+ dias E pagamento pendente ---
    at_risk = Student.query.filter(
        Student.trainer_id == trainer.id,
        Student.status == "pending_payment",
        or_(
            Student.last_access_at < seven_days_ago,
            Student.last_access_at.is_(None),
        ),
    ).limit(5).all()

    # --- Alunos sem ficha ativa ou ficha não atualizada há 30+ dias ---
    ok_workout_ids = db.session.query(Workout.student_id).filter(
        Workout.trainer_id == trainer.id,
        Workout.is_active == True,          # noqa: E712
        Workout.updated_at >= thirty_days_ago,
    ).distinct()

    students_without_workout = Student.query.filter(
        Student.trainer_id == trainer.id,
        Student.status == "active",
        ~Student.id.in_(ok_workout_ids),
    ).limit(5).all()

    # --- Alunos com pagamento pendente/vencido ---
    overdue_students = Student.query.filter_by(
        trainer_id=trainer.id, status="pending_payment"
    ).limit(5).all()

    # --- Atividade recente: mix de pagamentos, novos alunos e mensagens ---
    recent_payments = Payment.query.filter(
        Payment.trainer_id == trainer.id,
        Payment.status == "paid",
        Payment.paid_at.isnot(None),
    ).order_by(Payment.paid_at.desc()).limit(10).all()

    recent_new_students = Student.query.filter(
        Student.trainer_id == trainer.id,
    ).order_by(Student.created_at.desc()).limit(10).all()

    # Mensagens recebidas de alunos (sender_role='student')
    recent_msgs = db.session.query(Message, Student).join(
        Student, Message.student_id == Student.id
    ).filter(
        Message.trainer_id == trainer.id,
        Message.sender_role == "student",
    ).order_by(Message.created_at.desc()).limit(10).all()

    activity = []
    for p in recent_payments:
        sname = p.student.name if p.student else "Aluno"
        activity.append({
            "type": "payment",
            "description": f"Pagamento de R${float(p.amount):.2f}",
            "created_at": p.paid_at.isoformat(),
            "student_id": p.student_id,
            "student_name": sname,
            "student_avatar": p.student.avatar_url if p.student else None,
        })
    for s in recent_new_students:
        activity.append({
            "type": "new_student",
            "description": "Novo aluno cadastrado",
            "created_at": s.created_at.isoformat(),
            "student_id": s.id,
            "student_name": s.name,
            "student_avatar": s.avatar_url,
        })
    for msg, student in recent_msgs:
        activity.append({
            "type": "message",
            "description": "Nova mensagem recebida",
            "created_at": msg.created_at.isoformat(),
            "student_id": msg.student_id,
            "student_name": student.name,
            "student_avatar": student.avatar_url,
        })

    activity.sort(key=lambda x: x["created_at"], reverse=True)
    recent_activity = activity[:10]

    # --- MRR histórico: últimos 6 meses ---
    mrr_history = []
    for i in range(5, -1, -1):
        m_start = _subtract_months(first_of_month, i)
        m_end   = _subtract_months(first_of_month, i - 1) if i > 0 else now
        m_sum = float(
            db.session.query(func.sum(Payment.amount)).filter(
                Payment.trainer_id == trainer.id,
                Payment.status == "paid",
                Payment.paid_at >= m_start,
                Payment.paid_at < m_end,
            ).scalar() or 0
        )
        mrr_history.append({
            "month": m_start.strftime("%b/%y"),
            "amount": m_sum,
        })

    # --- Distribuição de objetivos dos alunos ativos ---
    obj_rows = db.session.query(
        Student.objective,
        func.count(Student.id).label("count"),
    ).filter(
        Student.trainer_id == trainer.id,
        Student.status == "active",
        Student.objective.isnot(None),
    ).group_by(Student.objective).all()

    objectives_distribution = [
        {"objective": row.objective, "count": row.count}
        for row in obj_rows
    ]

    return _success(data={
        "students_active_count": students_active_count,
        "students_delta":        students_delta,
        "mrr_current":           mrr_current,
        "mrr_delta":             mrr_delta,
        "overdue_count":         overdue_count,
        "today_count":           len(today_appts),
        "today_appointments":    [a.to_dict() for a in today_appts],
        "next_appointment":      next_appt.to_dict() if next_appt else None,
        "at_risk_students":      [s.to_dict() for s in at_risk],
        "students_without_workout": [s.to_dict() for s in students_without_workout],
        "overdue_students":      [s.to_dict() for s in overdue_students],
        "recent_activity":       recent_activity,
        "mrr_history":           mrr_history,
        "objectives_distribution": objectives_distribution,
    })
