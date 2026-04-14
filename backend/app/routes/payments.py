"""
Blueprint de pagamentos — /api/payments
Gestão de cobranças, integração Asaas e dashboard financeiro.
"""
from datetime import date, datetime, timezone
from calendar import monthrange
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required
from sqlalchemy import func, and_, extract

from app.extensions import db
from app.models.payment import Payment
from app.models.student import Student
from app.utils.decorators import trainer_required

payments_bp = Blueprint("payments", __name__, url_prefix="/api/payments")

VALID_STATUSES    = {"pending", "paid", "overdue", "cancelled"}
VALID_METHODS     = {"pix", "boleto", "dinheiro", "cartao", "transferencia", "outro"}


# ------------------------------------------------------------------ #
#  Helpers                                                            #
# ------------------------------------------------------------------ #

def _success(data=None, message="", status=200):
    return jsonify({"success": True, "data": data, "message": message}), status


def _error(message="Erro", status=400, data=None):
    return jsonify({"success": False, "data": data, "message": message}), status


def _get_payment_or_404(payment_id: str, trainer_id: str):
    p = db.session.get(Payment, payment_id)
    if not p or p.trainer_id != trainer_id:
        return None, _error("Cobrança não encontrada.", 404)
    return p, None


def _month_bounds(month_str: str):
    """
    Converte 'YYYY-MM' em (date_inicio, date_fim_exclusive).
    Retorna (None, None) se inválido.
    """
    try:
        year, month = int(month_str[:4]), int(month_str[5:7])
        start = date(year, month, 1)
        last  = monthrange(year, month)[1]
        end   = date(year, month, last)
        return start, end
    except (ValueError, IndexError):
        return None, None


# ------------------------------------------------------------------ #
#  GET /api/payments/dashboard                                        #
# ------------------------------------------------------------------ #

@payments_bp.route("/dashboard", methods=["GET"])
@jwt_required()
@trainer_required
def dashboard(**kwargs):
    """
    Retorna métricas financeiras do trainer:
      mrr_current      — soma de cobranças paid+pending do mês atual
      total_paid_month — soma de cobranças paid do mês atual
      total_pending    — soma de cobranças pending (qualquer mês)
      total_overdue    — soma de cobranças overdue
      students_overdue — lista de alunos com cobranças vencidas
      mrr_history      — [{month, amount}] dos últimos 6 meses (pagos + pendentes)
    """
    trainer = kwargs["current_trainer"]

    # Garante cobranças do mês atual e atualiza overdues antes de calcular métricas
    from app.services.payment_service import generate_monthly_charges, update_overdue_payments
    generate_monthly_charges(trainer.id)
    update_overdue_payments(trainer.id)

    today = date.today()
    month_start = today.replace(day=1)
    month_end   = today.replace(day=monthrange(today.year, today.month)[1])

    # MRR atual (paid + pending do mês)
    mrr_current = db.session.query(
        func.coalesce(func.sum(Payment.amount), 0)
    ).filter(
        Payment.trainer_id == trainer.id,
        Payment.status.in_(["paid", "pending"]),
        Payment.due_date >= month_start,
        Payment.due_date <= month_end,
    ).scalar()

    # Total pago no mês
    total_paid_month = db.session.query(
        func.coalesce(func.sum(Payment.amount), 0)
    ).filter(
        Payment.trainer_id == trainer.id,
        Payment.status == "paid",
        Payment.due_date >= month_start,
        Payment.due_date <= month_end,
    ).scalar()

    # Total pendente (qualquer mês, não cancelado)
    total_pending = db.session.query(
        func.coalesce(func.sum(Payment.amount), 0)
    ).filter(
        Payment.trainer_id == trainer.id,
        Payment.status == "pending",
    ).scalar()

    # Total inadimplente
    total_overdue = db.session.query(
        func.coalesce(func.sum(Payment.amount), 0)
    ).filter(
        Payment.trainer_id == trainer.id,
        Payment.status == "overdue",
    ).scalar()

    # Alunos inadimplentes (agrupa por aluno, soma valores em aberto)
    overdue_rows = db.session.query(
        Payment.student_id,
        func.sum(Payment.amount).label("total"),
        func.count(Payment.id).label("count"),
    ).filter(
        Payment.trainer_id == trainer.id,
        Payment.status == "overdue",
    ).group_by(Payment.student_id).all()

    students_overdue = []
    for row in overdue_rows:
        student = db.session.get(Student, row.student_id)
        if student:
            students_overdue.append({
                "student_id":  student.id,
                "student_name": student.name,
                "avatar_url":  student.avatar_url,
                "total_overdue": float(row.total),
                "charge_count":  row.count,
            })

    # Histórico MRR dos últimos 6 meses
    mrr_history = []
    for i in range(5, -1, -1):
        # i meses atrás
        year  = today.year
        month = today.month - i
        while month <= 0:
            month += 12
            year  -= 1
        m_start = date(year, month, 1)
        m_end   = date(year, month, monthrange(year, month)[1])

        total = db.session.query(
            func.coalesce(func.sum(Payment.amount), 0)
        ).filter(
            Payment.trainer_id == trainer.id,
            Payment.status.in_(["paid", "pending"]),
            Payment.due_date >= m_start,
            Payment.due_date <= m_end,
        ).scalar()

        mrr_history.append({
            "month":  m_start.strftime("%Y-%m"),
            "label":  m_start.strftime("%b/%y"),
            "amount": float(total),
        })

    return _success(data={
        "mrr_current":      float(mrr_current),
        "total_paid_month": float(total_paid_month),
        "total_pending":    float(total_pending),
        "total_overdue":    float(total_overdue),
        "students_overdue": students_overdue,
        "mrr_history":      mrr_history,
    })


# ------------------------------------------------------------------ #
#  GET /api/payments/                                                 #
# ------------------------------------------------------------------ #

@payments_bp.route("/", methods=["GET"])
@jwt_required()
@trainer_required
def list_payments(**kwargs):
    """
    Lista cobranças com filtros.
    Query params: student_id, month=YYYY-MM, status, search, sort, page, per_page
    """
    trainer = kwargs["current_trainer"]

    student_id = request.args.get("student_id")
    month_str  = request.args.get("month")
    status     = request.args.get("status")
    search     = request.args.get("search", "").strip()
    sort_by    = request.args.get("sort", "due_date_desc")
    page       = max(1, int(request.args.get("page", 1)))
    per_page   = min(100, max(1, int(request.args.get("per_page", 30))))

    query = Payment.query.filter_by(trainer_id=trainer.id)

    if student_id:
        query = query.filter(Payment.student_id == student_id)

    if month_str:
        m_start, m_end = _month_bounds(month_str)
        if m_start:
            query = query.filter(Payment.due_date >= m_start, Payment.due_date <= m_end)

    if status and status in VALID_STATUSES:
        query = query.filter(Payment.status == status)

    # Busca por nome do aluno (join)
    if search:
        query = query.join(Student, Payment.student_id == Student.id).filter(
            Student.name.ilike(f"%{search}%")
        )

    # Ordenação
    if sort_by == "due_date_asc":
        query = query.order_by(Payment.due_date.asc())
    elif sort_by == "amount_desc":
        query = query.order_by(Payment.amount.desc())
    else:  # due_date_desc (default)
        query = query.order_by(Payment.due_date.desc())

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return _success(data={
        "payments": [p.to_dict() for p in pagination.items],
        "pagination": {
            "page":     pagination.page,
            "per_page": pagination.per_page,
            "total":    pagination.total,
            "pages":    pagination.pages,
            "has_next": pagination.has_next,
            "has_prev": pagination.has_prev,
        },
    })


# ------------------------------------------------------------------ #
#  POST /api/payments/                                                #
# ------------------------------------------------------------------ #

@payments_bp.route("/", methods=["POST"])
@jwt_required()
@trainer_required
def create_payment(**kwargs):
    """
    Cria cobrança manual. Se ASAAS_API_KEY estiver configurada,
    tenta criar cobrança Pix no Asaas.
    Body: student_id, amount, due_date, notes (opcional)
    """
    trainer = kwargs["current_trainer"]
    data = request.get_json(silent=True)
    if not data:
        return _error("Corpo da requisição inválido.", 400)

    # Valida campos
    student_id = data.get("student_id")
    if not student_id:
        return _error("student_id é obrigatório.", 422)

    student = db.session.get(Student, student_id)
    if not student or student.trainer_id != trainer.id:
        return _error("Aluno não encontrado.", 404)

    amount_raw = data.get("amount")
    try:
        amount = float(amount_raw)
        if amount <= 0:
            raise ValueError
    except (TypeError, ValueError):
        return _error("amount deve ser um número positivo.", 422)

    due_str = data.get("due_date", "")
    try:
        due_date = date.fromisoformat(due_str)
    except (ValueError, TypeError):
        return _error("due_date inválido. Use YYYY-MM-DD.", 422)

    payment = Payment(
        student_id=student_id,
        trainer_id=trainer.id,
        amount=amount,
        due_date=due_date,
        status="pending",
        notes=(data.get("notes") or "").strip() or None,
    )
    db.session.add(payment)
    db.session.flush()

    # Tenta Asaas se chave configurada
    asaas_error = None
    if current_app.config.get("ASAAS_API_KEY"):
        from app.services.payment_service import create_pix_charge
        ok, err = create_pix_charge(payment, student)
        if not ok:
            asaas_error = err

    db.session.commit()

    return _success(
        data={
            "payment": payment.to_dict(),
            "asaas_error": asaas_error,
        },
        message="Cobrança criada com sucesso.",
        status=201,
    )


# ------------------------------------------------------------------ #
#  POST /api/payments/bulk                                            #
# ------------------------------------------------------------------ #

@payments_bp.route("/bulk", methods=["POST"])
@jwt_required()
@trainer_required
def bulk_create(**kwargs):
    """
    Gera cobranças mensais para todos os alunos ativos sem cobrança no mês.
    Body: month=YYYY-MM (opcional, default = mês atual)
    """
    trainer = kwargs["current_trainer"]
    data = request.get_json(silent=True) or {}

    month_str = data.get("month")
    target_month = None

    if month_str:
        m_start, _ = _month_bounds(month_str)
        if not m_start:
            return _error("Formato de month inválido. Use YYYY-MM.", 422)
        target_month = m_start

    from app.services.payment_service import generate_monthly_charges
    result = generate_monthly_charges(trainer.id, target_month)

    msg = f"{result['created']} cobrança(s) gerada(s). {result['skipped']} pulada(s)."
    if result["errors"]:
        msg += f" {len(result['errors'])} erro(s) ao integrar com Asaas."

    return _success(data=result, message=msg)


# ------------------------------------------------------------------ #
#  GET /api/payments/preview-bulk                                     #
# ------------------------------------------------------------------ #

@payments_bp.route("/preview-bulk", methods=["GET"])
@jwt_required()
@trainer_required
def preview_bulk(**kwargs):
    """
    Retorna quantos alunos receberiam cobranças se /bulk fosse executado agora.
    Não grava nada. Usado para exibir o preview antes da confirmação.
    """
    trainer = kwargs["current_trainer"]
    month_str = request.args.get("month")

    today = date.today()
    if month_str:
        m_start, _ = _month_bounds(month_str)
        target_month = m_start or today.replace(day=1)
    else:
        target_month = today.replace(day=1)

    # Mês seguinte para delimitar a query
    if target_month.month == 12:
        next_month = date(target_month.year + 1, 1, 1)
    else:
        next_month = date(target_month.year, target_month.month + 1, 1)

    # Alunos ativos com mensalidade
    students = Student.query.filter_by(
        trainer_id=trainer.id,
        status="active",
        is_active=True,
    ).filter(Student.monthly_fee > 0).all()

    pending_count = 0
    for student in students:
        existing = Payment.query.filter(
            Payment.student_id == student.id,
            Payment.due_date >= target_month,
            Payment.due_date < next_month,
            Payment.status != "cancelled",
        ).first()
        if not existing:
            pending_count += 1

    month_name = target_month.strftime("%B de %Y")

    return _success(data={
        "month":         target_month.isoformat(),
        "month_label":   month_name,
        "pending_count": pending_count,
        "total_students": len(students),
    })


# ------------------------------------------------------------------ #
#  POST /api/payments/notify                                          #
# ------------------------------------------------------------------ #

@payments_bp.route("/notify", methods=["POST"])
@jwt_required()
@trainer_required
def notify_unpaid(**kwargs):
    """
    Envia mensagem de cobrança via WhatsApp (Evolution API) para todos os alunos
    com pagamento pendente ou inadimplente no mês informado.

    Não verifica se a mensagem já foi enviada antes — sempre reenvia.
    Requer que o trainer tenha pix_key cadastrada.

    Body (opcional): { "month": "YYYY-MM" }
    """
    from app.services.whatsapp_service import send_payment_reminder

    trainer   = kwargs["current_trainer"]
    data      = request.get_json(silent=True) or {}
    month_str = data.get("month")

    if not trainer.pix_key:
        return _error(
            "Chave PIX não cadastrada. Configure-a na página de Perfil antes de enviar cobranças.",
            422,
        )

    today = date.today()
    if month_str:
        m_start, _ = _month_bounds(month_str)
        target_month = m_start or today.replace(day=1)
    else:
        target_month = today.replace(day=1)

    if target_month.month == 12:
        next_month = date(target_month.year + 1, 1, 1)
    else:
        next_month = date(target_month.year, target_month.month + 1, 1)

    # Apenas inadimplentes (overdue) de alunos ativos e não cancelados
    # O scheduler cuida do lembrete no dia do vencimento (status=pending)
    pagamentos = (
        Payment.query
        .join(Student, Payment.student_id == Student.id)
        .filter(
            Payment.trainer_id == trainer.id,
            Payment.status     == "overdue",
            Student.is_active  == True,
            Student.status     == "active",
        )
        .all()
    )

    enviados  = 0
    ignorados = 0
    erros     = []

    for pag in pagamentos:
        aluno = db.session.get(Student, pag.student_id)
        if not aluno or not aluno.phone:
            ignorados += 1
            continue

        ok, err = send_payment_reminder(
            student_name  = aluno.name,
            student_phone = aluno.phone,
            trainer_name  = trainer.name,
            amount        = float(pag.amount),
            due_date      = pag.due_date,
            pix_key       = trainer.pix_key,
        )

        if ok:
            enviados += 1
        else:
            ignorados += 1
            erros.append({"aluno": aluno.name, "erro": err})

    msg = f"{enviados} mensagem(ns) enviada(s)."
    if ignorados:
        msg += f" {ignorados} ignorada(s) (sem telefone ou falha na API)."

    return _success(
        data={"enviados": enviados, "ignorados": ignorados, "erros": erros},
        message=msg,
    )


# ------------------------------------------------------------------ #
#  GET /api/payments/<id>                                             #
# ------------------------------------------------------------------ #

@payments_bp.route("/<payment_id>", methods=["GET"])
@jwt_required()
@trainer_required
def get_payment(payment_id, **kwargs):
    trainer = kwargs["current_trainer"]
    payment, err = _get_payment_or_404(payment_id, trainer.id)
    if err:
        return err
    return _success(data={"payment": payment.to_dict()})


# ------------------------------------------------------------------ #
#  POST /api/payments/<id>/mark-paid                                  #
# ------------------------------------------------------------------ #

@payments_bp.route("/<payment_id>/mark-paid", methods=["POST"])
@jwt_required()
@trainer_required
def mark_paid(payment_id, **kwargs):
    """
    Marca cobrança como paga manualmente.
    Body: payment_method (opcional), notes (opcional), paid_at (opcional)
    """
    trainer = kwargs["current_trainer"]
    payment, err = _get_payment_or_404(payment_id, trainer.id)
    if err:
        return err

    if payment.status == "cancelled":
        return _error("Não é possível marcar como paga uma cobrança cancelada.", 422)
    if payment.status == "paid":
        return _error("Esta cobrança já foi marcada como paga.", 422)

    data = request.get_json(silent=True) or {}

    method = (data.get("payment_method") or "").strip() or None
    if method and method not in VALID_METHODS:
        return _error(f"Método inválido. Use: {', '.join(sorted(VALID_METHODS))}.", 422)

    paid_at = datetime.now(timezone.utc)
    if data.get("paid_at"):
        try:
            paid_at = datetime.fromisoformat(data["paid_at"])
            if paid_at.tzinfo is None:
                paid_at = paid_at.replace(tzinfo=timezone.utc)
        except ValueError:
            return _error("paid_at inválido. Use ISO 8601.", 422)

    payment.status         = "paid"
    payment.paid_at        = paid_at
    payment.payment_method = method
    if data.get("notes"):
        payment.notes = data["notes"].strip() or None

    # Atualiza status do aluno para active se estava pending_payment
    if payment.student and payment.student.status == "pending_payment":
        # Verifica se ainda há outras cobranças em aberto
        other_overdue = Payment.query.filter(
            Payment.student_id == payment.student_id,
            Payment.status == "overdue",
            Payment.id != payment.id,
        ).count()
        if not other_overdue:
            payment.student.status = "active"

    db.session.commit()

    return _success(
        data={"payment": payment.to_dict()},
        message="Cobrança marcada como paga.",
    )


# ------------------------------------------------------------------ #
#  DELETE /api/payments/<id>                                          #
# ------------------------------------------------------------------ #

@payments_bp.route("/<payment_id>", methods=["DELETE"])
@jwt_required()
@trainer_required
def cancel_payment(payment_id, **kwargs):
    """Cancela cobrança (soft delete — status=cancelled)."""
    trainer = kwargs["current_trainer"]
    payment, err = _get_payment_or_404(payment_id, trainer.id)
    if err:
        return err

    if payment.status == "paid":
        return _error("Não é possível cancelar uma cobrança já paga.", 422)
    if payment.status == "cancelled":
        return _error("Esta cobrança já está cancelada.", 422)

    payment.status = "cancelled"
    db.session.commit()

    return _success(message="Cobrança cancelada.")


# ------------------------------------------------------------------ #
#  POST /api/payments/webhooks/asaas                                  #
# ------------------------------------------------------------------ #

@payments_bp.route("/webhooks/asaas", methods=["POST"])
def asaas_webhook():
    """
    Recebe notificações de pagamento do Asaas.
    Valida o token no header 'asaas-access-token' e atualiza o status.
    Documentação: https://docs.asaas.com/reference/webhook
    """
    # Valida token de segurança
    token = request.headers.get("asaas-access-token", "")
    expected = current_app.config.get("ASAAS_WEBHOOK_TOKEN", "")
    if expected and token != expected:
        return jsonify({"error": "Unauthorized"}), 401

    payload = request.get_json(silent=True)
    if not payload:
        return jsonify({"error": "Invalid payload"}), 400

    event   = payload.get("event", "")
    charge  = payload.get("payment", {})
    charge_id = charge.get("id")

    if not charge_id:
        return jsonify({"received": True}), 200

    payment = Payment.query.filter_by(asaas_charge_id=charge_id).first()
    if not payment:
        return jsonify({"received": True}), 200

    # Mapeamento de eventos Asaas → status interno
    event_map = {
        "PAYMENT_RECEIVED":           "paid",
        "PAYMENT_CONFIRMED":          "paid",
        "PAYMENT_OVERDUE":            "overdue",
        "PAYMENT_DELETED":            "cancelled",
        "PAYMENT_REFUNDED":           "cancelled",
        "PAYMENT_REFUND_IN_PROGRESS": "cancelled",
    }

    new_status = event_map.get(event)
    if new_status:
        payment.status = new_status
        if new_status == "paid":
            payment.paid_at = datetime.now(timezone.utc)
            payment.payment_method = payment.payment_method or "pix"
        db.session.commit()

    return jsonify({"received": True}), 200
