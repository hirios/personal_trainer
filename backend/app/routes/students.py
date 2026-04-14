"""
Blueprint de gestão de alunos — /api/students
Todas as rotas (exceto /public/<access_token>) exigem trainer autenticado.
"""
from datetime import datetime, timezone, date
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required
from flask_mail import Message
from sqlalchemy import desc, nullslast, or_

from app.extensions import db, mail
from app.models.user import User
from app.models.student import Student
from app.models.workout import Workout
from app.utils.decorators import trainer_required

students_bp = Blueprint("students", __name__, url_prefix="/api/students")

# Objetivos válidos
VALID_OBJECTIVES = {
    "emagrecimento", "hipertrofia", "condicionamento", "saude", "reabilitacao"
}

# Modalidades válidas
VALID_MODALITIES = {"presencial", "online", "hibrido"}


# ------------------------------------------------------------------ #
#  Helpers                                                            #
# ------------------------------------------------------------------ #

def _success(data=None, message="", status=200):
    return jsonify({"success": True, "data": data, "message": message}), status


def _error(message="Erro", status=400, data=None):
    return jsonify({"success": False, "data": data, "message": message}), status


def _get_student_or_404(student_id: str, trainer_id: str):
    """Busca o aluno garantindo que pertence ao trainer. Retorna (student, None) ou (None, response)."""
    student = db.session.get(Student, student_id)
    if not student or student.trainer_id != trainer_id:
        return None, _error("Aluno não encontrado.", 404)
    return student, None


def _calculate_engagement(student: Student) -> tuple[int, dict]:
    """
    Calcula o score de engajamento do aluno (0–100).
    Critérios:
      - Pagamento em dia (status=active): 40 pts
      - Acessou nos últimos 7 dias: 35 pts / últimos 14 dias: 18 pts
      - Possui treino ativo (Módulo 3): 25 pts — placeholder por ora
    """
    score = 0
    details: dict = {}

    # Critério 1 — pagamento
    payment_ok = student.status == "active"
    if payment_ok:
        score += 40
    details["payment_ok"] = payment_ok
    details["payment_status"] = student.status

    # Critério 2 — último acesso
    # SQLite armazena datetimes sem fuso; normaliza para UTC antes de subtrair
    days_since_access = None
    if student.last_access_at:
        last_access = student.last_access_at
        if last_access.tzinfo is None:
            last_access = last_access.replace(tzinfo=timezone.utc)
        delta = datetime.now(timezone.utc) - last_access
        days_since_access = delta.days
        if days_since_access <= 7:
            score += 35
        elif days_since_access <= 14:
            score += 18
    details["days_since_access"] = days_since_access
    details["last_access_at"] = (
        student.last_access_at.isoformat() if student.last_access_at else None
    )

    # Critério 3 — treino ativo (implementado no Módulo 3)
    details["has_active_workout"] = False
    details["active_workouts"] = 0

    level = "baixo"
    if score >= 75:
        level = "alto"
    elif score >= 45:
        level = "medio"

    return score, level, details


def _send_welcome_email(student: Student, trainer_name: str, access_url: str) -> None:
    """Envia e-mail de boas-vindas ao aluno. Falha silenciosa se email não configurado."""
    try:
        msg = Message(
            subject=f"Bem-vindo à plataforma de {trainer_name}!",
            recipients=[student.email],
            html=f"""
            <div style="font-family:sans-serif;max-width:560px;margin:0 auto;">
              <h2 style="color:#22C55E;">Olá, {student.name.split()[0]}! 👋</h2>
              <p>Seu personal trainer <strong>{trainer_name}</strong> acabou de te cadastrar no FitFlow Pro.</p>
              <p>Acesse sua área de aluno pelo link abaixo para acompanhar seus treinos e evolução:</p>
              <a href="{access_url}"
                 style="display:inline-block;padding:12px 24px;background:#22C55E;color:#fff;
                        border-radius:10px;text-decoration:none;font-weight:bold;margin:16px 0;">
                Acessar minha área
              </a>
              <p style="color:#64748B;font-size:13px;">
                Guarde este link — ele é o seu acesso exclusivo e não precisa de senha.
              </p>
            </div>
            """,
        )
        mail.send(msg)
    except Exception:
        # Não falha a requisição se o e-mail não for enviado
        pass


# ------------------------------------------------------------------ #
#  GET /api/students/                                                 #
# ------------------------------------------------------------------ #

@students_bp.route("/", methods=["GET"])
@jwt_required()
@trainer_required
def list_students(**kwargs):
    """
    Lista alunos do trainer com filtros, busca e paginação.
    Query params: status, objective, search, overdue, no_workout, sort, page, per_page
    """
    trainer = kwargs["current_trainer"]

    # Parâmetros
    status       = request.args.get("status")
    objective    = request.args.get("objective")
    search       = request.args.get("search", "").strip()
    overdue      = request.args.get("overdue", "false").lower() == "true"
    sort_by      = request.args.get("sort", "name")
    page         = max(1, int(request.args.get("page", 1)))
    per_page     = min(100, max(1, int(request.args.get("per_page", 20))))

    query = Student.query.filter_by(trainer_id=trainer.id)

    # Filtros
    if overdue:
        query = query.filter(Student.status == "pending_payment")
    elif status:
        query = query.filter(Student.status == status)

    if objective:
        query = query.filter(Student.objective == objective)

    if search:
        term = f"%{search}%"
        query = query.filter(
            or_(
                Student.name.ilike(term),
                Student.email.ilike(term),
                Student.phone.ilike(term),
            )
        )

    # Ordenação
    if sort_by == "last_access":
        query = query.order_by(nullslast(desc(Student.last_access_at)))
    elif sort_by == "created_at":
        query = query.order_by(desc(Student.created_at))
    else:
        query = query.order_by(Student.name.asc())

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return _success(
        data={
            "students": [s.to_dict() for s in pagination.items],
            "pagination": {
                "page": pagination.page,
                "per_page": pagination.per_page,
                "total": pagination.total,
                "pages": pagination.pages,
                "has_next": pagination.has_next,
                "has_prev": pagination.has_prev,
            },
        }
    )


# ------------------------------------------------------------------ #
#  POST /api/students/                                                #
# ------------------------------------------------------------------ #

@students_bp.route("/", methods=["POST"])
@jwt_required()
@trainer_required
def create_student(**kwargs):
    """Cadastra um novo aluno vinculado ao trainer autenticado."""
    trainer = kwargs["current_trainer"]
    data = request.get_json(silent=True)

    if not data:
        return _error("Corpo da requisição inválido.", 400)

    # Campos obrigatórios
    name  = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip().lower()

    if not name:
        return _error("O nome do aluno é obrigatório.", 422)
    if not email:
        return _error("O e-mail do aluno é obrigatório.", 422)

    # E-mail duplicado (global — o mesmo email não pode ser de dois usuários)
    if User.query.filter_by(email=email).first():
        return _error("Este e-mail já está cadastrado no sistema.", 409)

    # Campos opcionais
    phone          = (data.get("phone") or "").strip() or None
    birth_date_str = (data.get("birth_date") or "").strip() or None
    gender         = data.get("gender") or None
    objective      = data.get("objective") or None
    health_notes   = data.get("health_notes") or None
    monthly_fee    = data.get("monthly_fee")
    payment_day    = data.get("payment_day")
    modality       = data.get("modality", "presencial")
    internal_notes = data.get("internal_notes") or None

    # Parse data de nascimento
    birth_date = None
    if birth_date_str:
        try:
            birth_date = date.fromisoformat(birth_date_str)
        except ValueError:
            return _error("Formato de data de nascimento inválido. Use YYYY-MM-DD.", 422)

    # Valida payment_day
    if payment_day is not None:
        try:
            payment_day = int(payment_day)
            if not 1 <= payment_day <= 28:
                raise ValueError
        except (ValueError, TypeError):
            return _error("Dia de vencimento deve ser entre 1 e 28.", 422)

    # Cria o aluno — senha temporária (aluno acessa via access_token, não senha)
    import secrets
    temp_password = secrets.token_urlsafe(16)

    student = Student(
        name=name,
        email=email,
        phone=phone,
        role="student",
        birth_date=birth_date,
        gender=gender,
        objective=objective,
        health_notes=health_notes,
        status="active",
        monthly_fee=monthly_fee,
        payment_day=payment_day,
        modality=modality,
        internal_notes=internal_notes,
        trainer_id=trainer.id,
    )
    student.set_password(temp_password)

    db.session.add(student)
    db.session.commit()

    # Monta URL de acesso do aluno usando o frontend configurado
    base_url = current_app.config.get("FRONTEND_BASE_URL", "").rstrip("/")
    access_url = f"{base_url}/frontend/student/index.html?token={student.access_token}"

    # Envia e-mail de boas-vindas (assíncrono implícito via best-effort)
    _send_welcome_email(student, trainer.name, access_url)

    result = student.to_dict_with_token()
    result["access_url"] = access_url

    return _success(
        data={"student": result},
        message=f"Aluno {student.name} cadastrado com sucesso!",
        status=201,
    )


# ------------------------------------------------------------------ #
#  GET /api/students/public/<access_token>                           #
# ------------------------------------------------------------------ #

@students_bp.route("/public/<access_token>", methods=["GET"])
def student_public_profile(access_token):
    """
    Endpoint público (sem auth JWT) para a área do aluno.
    Registra o último acesso e retorna dados básicos + treinos ativos.
    """
    student = Student.query.filter_by(access_token=access_token).first()
    if not student or not student.is_active:
        return _error("Link de acesso inválido ou expirado.", 404)

    # Atualiza último acesso
    student.last_access_at = datetime.now(timezone.utc)
    db.session.commit()

    # Dados públicos — sem informações sensíveis
    public_data = {
        "id": student.id,
        "name": student.name,
        "avatar_url": student.avatar_url,
        "objective": student.objective,
        "trainer": {
            "name": student.trainer.name,
            "avatar_url": student.trainer.avatar_url,
            "bio": student.trainer.bio,
        },
        "active_workouts": [
            {
                "id": w.id,
                "title": w.title,
                "category": w.category,
                "exercise_count": len(w.exercises),
                "updated_at": w.updated_at.isoformat() if w.updated_at else None,
            }
            for w in Workout.query.filter_by(
                student_id=student.id, is_active=True
            ).order_by(Workout.created_at.desc()).all()
        ],
    }

    return _success(data={"student": public_data})


# ------------------------------------------------------------------ #
#  GET /api/students/<id>                                             #
# ------------------------------------------------------------------ #

@students_bp.route("/<student_id>", methods=["GET"])
@jwt_required()
@trainer_required
def get_student(student_id, **kwargs):
    """Retorna perfil completo do aluno."""
    trainer = kwargs["current_trainer"]
    student, err = _get_student_or_404(student_id, trainer.id)
    if err:
        return err

    data = student.to_dict_with_token()

    # Campos de módulos futuros retornados como null por ora
    data["last_workout"] = None    # Módulo 3
    data["last_assessment"] = None # Módulo 4
    data["next_payment"] = None    # Módulo 6

    # URL de acesso do aluno usando o frontend configurado
    base_url = current_app.config.get("FRONTEND_BASE_URL", "").rstrip("/")
    data["access_url"] = f"{base_url}/frontend/student/index.html?token={student.access_token}"

    return _success(data={"student": data})


# ------------------------------------------------------------------ #
#  PATCH /api/students/<id>                                           #
# ------------------------------------------------------------------ #

@students_bp.route("/<student_id>", methods=["PATCH"])
@jwt_required()
@trainer_required
def update_student(student_id, **kwargs):
    """Atualiza dados do aluno. Apenas campos enviados são alterados."""
    trainer = kwargs["current_trainer"]
    student, err = _get_student_or_404(student_id, trainer.id)
    if err:
        return err

    data = request.get_json(silent=True)
    if not data:
        return _error("Corpo da requisição inválido.", 400)

    # Campos atualizáveis
    updatable_fields = {
        "name", "phone", "gender", "objective", "health_notes",
        "status", "monthly_fee", "payment_day", "modality",
        "internal_notes", "avatar_url",
    }

    VALID_STATUSES = {"active", "inactive", "pending_payment"}

    for field in updatable_fields:
        if field in data:
            value = data[field]
            # Normaliza strings vazias para None
            if isinstance(value, str) and value.strip() == "":
                value = None
            # Valida status
            if field == "status" and value not in VALID_STATUSES:
                return _error(
                    f"Status inválido. Use: {sorted(VALID_STATUSES)}.", 422
                )
            setattr(student, field, value)
            # Sincroniza is_active com status para bloquear acesso público
            if field == "status":
                student.is_active = (value != "inactive")

    # Data de nascimento precisa de parse
    if "birth_date" in data:
        birth_str = data["birth_date"]
        if birth_str:
            try:
                student.birth_date = date.fromisoformat(birth_str)
            except ValueError:
                return _error("Formato de data de nascimento inválido. Use YYYY-MM-DD.", 422)
        else:
            student.birth_date = None

    # E-mail — verifica duplicata se for alterado
    if "email" in data:
        new_email = (data["email"] or "").strip().lower()
        if new_email and new_email != student.email:
            if User.query.filter_by(email=new_email).first():
                return _error("Este e-mail já está em uso.", 409)
            student.email = new_email

    # Valida payment_day se fornecido
    if "payment_day" in data and data["payment_day"] is not None:
        try:
            pd = int(data["payment_day"])
            if not 1 <= pd <= 28:
                raise ValueError
            student.payment_day = pd
        except (ValueError, TypeError):
            return _error("Dia de vencimento deve ser entre 1 e 28.", 422)

    db.session.commit()

    return _success(
        data={"student": student.to_dict()},
        message="Dados do aluno atualizados com sucesso.",
    )


# ------------------------------------------------------------------ #
#  DELETE /api/students/<id>                                          #
# ------------------------------------------------------------------ #

@students_bp.route("/<student_id>", methods=["DELETE"])
@jwt_required()
@trainer_required
def deactivate_student(student_id, **kwargs):
    """
    Desativa o aluno (soft delete).
    O registro é mantido para histórico; apenas is_active=False e status=inactive.
    """
    trainer = kwargs["current_trainer"]
    student, err = _get_student_or_404(student_id, trainer.id)
    if err:
        return err

    student.is_active = False
    student.status = "inactive"
    db.session.commit()

    return _success(message=f"Aluno {student.name} desativado com sucesso.")


# ------------------------------------------------------------------ #
#  GET /api/students/<id>/engagement                                  #
# ------------------------------------------------------------------ #

@students_bp.route("/<student_id>/engagement", methods=["GET"])
@jwt_required()
@trainer_required
def get_engagement(student_id, **kwargs):
    """Retorna o score de engajamento do aluno e seus componentes."""
    trainer = kwargs["current_trainer"]
    student, err = _get_student_or_404(student_id, trainer.id)
    if err:
        return err

    score, level, details = _calculate_engagement(student)

    return _success(
        data={
            "score": score,
            "level": level,   # baixo | medio | alto
            "details": details,
        }
    )
