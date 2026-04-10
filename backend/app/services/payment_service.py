"""
Serviço de pagamentos — integração com a API do Asaas.
Todas as funções retornam (data, error_message).
Se error_message não for None, data é None.

Documentação Asaas: https://docs.asaas.com/
Endpoints usados:
  POST /customers        — cadastra cliente
  POST /payments         — cria cobrança Pix
  GET  /payments/{id}/pixQrCode — busca QR code
"""
import requests
from datetime import date, datetime, timezone
from flask import current_app

from app.extensions import db
from app.models.student import Student
from app.models.payment import Payment


# ------------------------------------------------------------------ #
#  Helpers internos                                                   #
# ------------------------------------------------------------------ #

def _headers() -> dict:
    """Monta os headers padrão para chamadas à API do Asaas."""
    api_key = current_app.config.get("ASAAS_API_KEY", "")
    return {
        "Content-Type": "application/json",
        "access_token": api_key,
    }


def _base_url() -> str:
    return current_app.config.get("ASAAS_BASE_URL", "https://sandbox.asaas.com/api/v3")


def _asaas_post(path: str, payload: dict) -> tuple[dict | None, str | None]:
    """POST genérico para o Asaas. Retorna (response_data, error)."""
    try:
        resp = requests.post(
            f"{_base_url()}{path}",
            json=payload,
            headers=_headers(),
            timeout=15,
        )
        data = resp.json()
        if resp.status_code >= 400:
            errors = data.get("errors", [])
            msg = errors[0].get("description", "Erro na API do Asaas.") if errors else "Erro na API do Asaas."
            return None, msg
        return data, None
    except requests.exceptions.Timeout:
        return None, "Timeout na comunicação com o Asaas."
    except requests.exceptions.RequestException as e:
        return None, f"Erro de rede: {str(e)}"
    except Exception as e:
        return None, f"Erro inesperado: {str(e)}"


def _asaas_get(path: str) -> tuple[dict | None, str | None]:
    """GET genérico para o Asaas."""
    try:
        resp = requests.get(
            f"{_base_url()}{path}",
            headers=_headers(),
            timeout=15,
        )
        data = resp.json()
        if resp.status_code >= 400:
            errors = data.get("errors", [])
            msg = errors[0].get("description", "Erro na API do Asaas.") if errors else "Erro na API do Asaas."
            return None, msg
        return data, None
    except requests.exceptions.Timeout:
        return None, "Timeout na comunicação com o Asaas."
    except requests.exceptions.RequestException as e:
        return None, f"Erro de rede: {str(e)}"
    except Exception as e:
        return None, f"Erro inesperado: {str(e)}"


# ------------------------------------------------------------------ #
#  create_customer                                                    #
# ------------------------------------------------------------------ #

def create_customer(student: Student) -> tuple[str | None, str | None]:
    """
    Cadastra o aluno como cliente no Asaas.
    Se já tiver asaas_customer_id, retorna o existente sem nova chamada.
    Retorna (asaas_customer_id, error).
    """
    if student.asaas_customer_id:
        return student.asaas_customer_id, None

    # CPF é opcional no cadastro
    payload = {
        "name": student.name,
        "email": student.email,
        "mobilePhone": (student.phone or "").replace(" ", "").replace("-", ""),
        "externalReference": student.id,
    }

    data, err = _asaas_post("/customers", payload)
    if err:
        return None, err

    customer_id = data.get("id")
    if not customer_id:
        return None, "Asaas não retornou ID do cliente."

    # Persiste no aluno
    student.asaas_customer_id = customer_id
    db.session.flush()  # não faz commit aqui — deixa para o caller

    return customer_id, None


# ------------------------------------------------------------------ #
#  create_pix_charge                                                  #
# ------------------------------------------------------------------ #

def create_pix_charge(
    payment: Payment,
    student: Student,
) -> tuple[bool, str | None]:
    """
    Cria cobrança Pix no Asaas para um Payment já salvo no banco.
    Preenche payment.asaas_charge_id, pix_qr_code e pix_copy_paste.
    Retorna (sucesso, error).
    """
    # Garante que o cliente existe no Asaas
    customer_id, err = create_customer(student)
    if err:
        return False, f"Erro ao criar cliente no Asaas: {err}"

    payload = {
        "customer": customer_id,
        "billingType": "PIX",
        "value": float(payment.amount),
        "dueDate": payment.due_date.isoformat(),
        "description": f"Mensalidade FitFlow Pro — {payment.due_date.strftime('%m/%Y')}",
        "externalReference": payment.id,
    }

    data, err = _asaas_post("/payments", payload)
    if err:
        return False, err

    charge_id = data.get("id")
    if not charge_id:
        return False, "Asaas não retornou ID da cobrança."

    payment.asaas_charge_id = charge_id

    # Busca QR code Pix
    qr_data, qr_err = _asaas_get(f"/payments/{charge_id}/pixQrCode")
    if not qr_err and qr_data:
        payment.pix_qr_code    = qr_data.get("encodedImage")
        payment.pix_copy_paste = qr_data.get("payload")

    return True, None


# ------------------------------------------------------------------ #
#  generate_monthly_charges                                           #
# ------------------------------------------------------------------ #

def generate_monthly_charges(trainer_id: str, target_month: date | None = None) -> dict:
    """
    Gera cobranças mensais para todos os alunos ativos do trainer
    que ainda não têm cobrança no mês alvo (default = mês atual).

    Retorna: {"created": N, "skipped": N, "errors": [{"student": name, "error": msg}]}
    """
    from app.models.trainer import Trainer

    if target_month is None:
        today = date.today()
        target_month = today.replace(day=1)

    trainer = db.session.get(Trainer, trainer_id)
    if not trainer:
        return {"created": 0, "skipped": 0, "errors": [{"student": "—", "error": "Trainer não encontrado."}]}

    # Alunos ativos com mensalidade configurada
    students = Student.query.filter_by(
        trainer_id=trainer_id,
        status="active",
        is_active=True,
    ).all()

    created = 0
    skipped = 0
    errors  = []

    for student in students:
        if not student.monthly_fee or float(student.monthly_fee) <= 0:
            skipped += 1
            continue

        # Calcula vencimento: dia configurado no aluno ou dia 10
        payment_day = student.payment_day or 10
        try:
            due = target_month.replace(day=payment_day)
        except ValueError:
            # Dia inválido para o mês (ex: 31 em fevereiro) → último dia
            import calendar
            last_day = calendar.monthrange(target_month.year, target_month.month)[1]
            due = target_month.replace(day=last_day)

        # Verifica se já existe cobrança ativa neste mês para este aluno
        existing = Payment.query.filter(
            Payment.student_id == student.id,
            Payment.trainer_id == trainer_id,
            Payment.due_date >= target_month,
            Payment.due_date < target_month.replace(month=target_month.month % 12 + 1)
            if target_month.month < 12
            else Payment.due_date < target_month.replace(year=target_month.year + 1, month=1),
            Payment.status != "cancelled",
        ).first()

        if existing:
            skipped += 1
            continue

        # Cria o Payment no banco
        payment = Payment(
            student_id=student.id,
            trainer_id=trainer_id,
            amount=student.monthly_fee,
            due_date=due,
            status="pending",
        )
        db.session.add(payment)
        db.session.flush()  # gera o ID antes de chamar o Asaas

        # Tenta criar cobrança Pix no Asaas (falha silenciosa — cobrança fica só no banco)
        api_key = current_app.config.get("ASAAS_API_KEY", "")
        if api_key:
            ok, err = create_pix_charge(payment, student)
            if not ok:
                errors.append({"student": student.name, "error": err})

        created += 1

    db.session.commit()

    return {"created": created, "skipped": skipped, "errors": errors}


# ------------------------------------------------------------------ #
#  update_overdue_payments                                            #
# ------------------------------------------------------------------ #

def update_overdue_payments(trainer_id: str) -> int:
    """
    Marca como 'overdue' todos os pagamentos pending cujo due_date já passou.
    Retorna a quantidade de pagamentos atualizados.
    """
    today = date.today()
    updated = (
        Payment.query
        .filter(
            Payment.trainer_id == trainer_id,
            Payment.status == "pending",
            Payment.due_date < today,
        )
        .update({"status": "overdue"}, synchronize_session=False)
    )
    db.session.commit()
    return updated
