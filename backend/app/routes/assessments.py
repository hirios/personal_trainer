"""
Blueprint de avaliações físicas — /api/assessments
Gestão do histórico de avaliações de cada aluno.
Todas as rotas exigem trainer autenticado.
"""
import os
from datetime import date as date_type
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from sqlalchemy import desc

from app.extensions import db
from app.models.assessment import Assessment
from app.models.assessment_request import AssessmentRequest
from app.models.student import Student
from app.utils.decorators import trainer_required

assessments_bp = Blueprint("assessments", __name__, url_prefix="/api/assessments")


# ------------------------------------------------------------------ #
#  Helpers                                                            #

def _uploads_root() -> str:
    """Caminho absoluto da pasta raiz de uploads (mesma lógica de uploads.py)."""
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "uploads")


def _delete_photo_files(urls: list) -> None:
    """Remove arquivos de foto do disco. Falha silenciosa por arquivo."""
    root = _uploads_root()
    for url in (urls or []):
        if not url:
            continue
        # Protege contra path traversal antes de apagar
        abs_path = os.path.realpath(os.path.join(root, url))
        if abs_path.startswith(os.path.realpath(root)):
            try:
                os.remove(abs_path)
            except OSError:
                pass  # arquivo já removido ou inexistente — ignora
# ------------------------------------------------------------------ #

def _ok(data=None, message="", status=200):
    return jsonify({"success": True, "data": data, "message": message}), status


def _err(message="Erro", status=400):
    return jsonify({"success": False, "data": None, "message": message}), status


def _get_assessment_or_404(assessment_id: str, trainer_id: str):
    """Garante que a avaliação existe e pertence ao trainer."""
    a = db.session.get(Assessment, assessment_id)
    if not a or a.trainer_id != trainer_id:
        return None, _err("Avaliação não encontrada.", 404)
    return a, None


def _parse_float(value):
    """Converte valor para float, retornando None se inválido."""
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _apply_fields(assessment: Assessment, data: dict) -> None:
    """Aplica campos do payload no objeto Assessment."""
    float_fields = [
        "weight", "height", "body_fat", "muscle_mass",
        "chest", "waist", "hip",
        "right_arm", "left_arm",
        "right_thigh", "left_thigh",
        "right_calf", "left_calf",
        "abdomen",
    ]
    for field in float_fields:
        if field in data:
            setattr(assessment, field, _parse_float(data[field]))

    if "notes" in data:
        assessment.notes = data["notes"] or None

    if "photo_urls" in data:
        urls = data["photo_urls"]
        assessment.photo_urls = urls if isinstance(urls, list) else []

    # Recalcula IMC se peso ou altura foram alterados
    if assessment.weight and assessment.height:
        assessment.bmi = Assessment.calculate_bmi(assessment.weight, assessment.height)
    else:
        assessment.bmi = None


# ------------------------------------------------------------------ #
#  GET /api/assessments/?student_id=X                                #
# ------------------------------------------------------------------ #

@assessments_bp.route("/", methods=["GET"])
@jwt_required()
@trainer_required
def list_assessments(**kwargs):
    """Lista histórico de avaliações de um aluno, ordenado por data desc."""
    trainer = kwargs["current_trainer"]
    student_id = request.args.get("student_id")

    if not student_id:
        return _err("Parâmetro student_id é obrigatório.", 400)

    # Valida que o aluno pertence ao trainer
    student = Student.query.filter_by(
        id=student_id, trainer_id=trainer.id
    ).first()
    if not student:
        return _err("Aluno não encontrado.", 404)

    assessments = (
        Assessment.query
        .filter_by(student_id=student_id, trainer_id=trainer.id)
        .order_by(desc(Assessment.date))
        .all()
    )

    return _ok(data={"assessments": [a.to_dict() for a in assessments]})


# ------------------------------------------------------------------ #
#  POST /api/assessments/                                            #
# ------------------------------------------------------------------ #

@assessments_bp.route("/", methods=["POST"])
@jwt_required()
@trainer_required
def create_assessment(**kwargs):
    """Cria nova avaliação física. BMI calculado automaticamente."""
    trainer = kwargs["current_trainer"]
    data = request.get_json(silent=True) or {}

    student_id = data.get("student_id", "").strip()
    date_str   = data.get("date", "").strip()

    if not student_id:
        return _err("Campo student_id é obrigatório.")
    if not date_str:
        return _err("Campo date é obrigatório.")

    # Valida que o aluno pertence ao trainer
    student = Student.query.filter_by(
        id=student_id, trainer_id=trainer.id
    ).first()
    if not student:
        return _err("Aluno não encontrado.", 404)

    # Converte data
    try:
        assessment_date = date_type.fromisoformat(date_str)
    except ValueError:
        return _err("Formato de data inválido. Use YYYY-MM-DD.")

    assessment = Assessment(
        student_id=student_id,
        trainer_id=trainer.id,
        date=assessment_date,
    )
    _apply_fields(assessment, data)
    db.session.add(assessment)
    db.session.commit()

    return _ok(
        data={"assessment": assessment.to_dict()},
        message="Avaliação registrada com sucesso.",
        status=201,
    )


# ------------------------------------------------------------------ #
#  GET /api/assessments/<id>                                         #
# ------------------------------------------------------------------ #

@assessments_bp.route("/<assessment_id>", methods=["GET"])
@jwt_required()
@trainer_required
def get_assessment(assessment_id, **kwargs):
    """Retorna detalhes de uma avaliação."""
    trainer = kwargs["current_trainer"]
    assessment, err = _get_assessment_or_404(assessment_id, trainer.id)
    if err:
        return err

    return _ok(data={"assessment": assessment.to_dict()})


# ------------------------------------------------------------------ #
#  PATCH /api/assessments/<id>                                       #
# ------------------------------------------------------------------ #

@assessments_bp.route("/<assessment_id>", methods=["PATCH"])
@jwt_required()
@trainer_required
def update_assessment(assessment_id, **kwargs):
    """Corrige campos de uma avaliação existente."""
    trainer = kwargs["current_trainer"]
    assessment, err = _get_assessment_or_404(assessment_id, trainer.id)
    if err:
        return err

    data = request.get_json(silent=True) or {}

    # Atualiza data se enviada
    if "date" in data:
        try:
            assessment.date = date_type.fromisoformat(data["date"])
        except ValueError:
            return _err("Formato de data inválido. Use YYYY-MM-DD.")

    # Remove do disco as fotos que saíram da lista
    if "photo_urls" in data:
        old_urls = set(assessment.photo_urls or [])
        new_urls = set(data["photo_urls"] if isinstance(data["photo_urls"], list) else [])
        removed  = old_urls - new_urls
        _delete_photo_files(list(removed))

    _apply_fields(assessment, data)
    db.session.commit()

    return _ok(
        data={"assessment": assessment.to_dict()},
        message="Avaliação atualizada com sucesso.",
    )


# ------------------------------------------------------------------ #
#  DELETE /api/assessments/<id>                                      #
# ------------------------------------------------------------------ #

@assessments_bp.route("/<assessment_id>", methods=["DELETE"])
@jwt_required()
@trainer_required
def delete_assessment(assessment_id, **kwargs):
    """Exclui uma avaliação."""
    trainer = kwargs["current_trainer"]
    assessment, err = _get_assessment_or_404(assessment_id, trainer.id)
    if err:
        return err

    # Remove todas as fotos do disco antes de deletar o registro
    _delete_photo_files(assessment.photo_urls or [])

    db.session.delete(assessment)
    db.session.commit()

    return _ok(message="Avaliação excluída.")


# ------------------------------------------------------------------ #
#  GET /api/assessments/progress/<student_id>                        #
# ------------------------------------------------------------------ #

@assessments_bp.route("/progress/<student_id>", methods=["GET"])
@jwt_required()
@trainer_required
def get_progress(student_id, **kwargs):
    """
    Retorna série temporal para gráficos Chart.js.
    Formato: [{date, weight, body_fat, waist, hip, chest, abdomen,
               right_arm, left_arm, right_thigh, left_thigh,
               right_calf, left_calf, muscle_mass, bmi}, ...]
    Ordenado por data ascendente (mais antigo primeiro).
    """
    trainer = kwargs["current_trainer"]

    student = Student.query.filter_by(
        id=student_id, trainer_id=trainer.id
    ).first()
    if not student:
        return _err("Aluno não encontrado.", 404)

    assessments = (
        Assessment.query
        .filter_by(student_id=student_id, trainer_id=trainer.id)
        .order_by(Assessment.date)
        .all()
    )

    series = [
        {
            "date":        a.date.isoformat(),
            "weight":      a.weight,
            "body_fat":    a.body_fat,
            "muscle_mass": a.muscle_mass,
            "bmi":         a.bmi,
            "chest":       a.chest,
            "waist":       a.waist,
            "hip":         a.hip,
            "abdomen":     a.abdomen,
            "right_arm":   a.right_arm,
            "left_arm":    a.left_arm,
            "right_thigh": a.right_thigh,
            "left_thigh":  a.left_thigh,
            "right_calf":  a.right_calf,
            "left_calf":   a.left_calf,
        }
        for a in assessments
    ]

    # Resumo automático (primeira vs última avaliação)
    summary = None
    if len(assessments) >= 2:
        first = assessments[0]
        last  = assessments[-1]
        days  = (last.date - first.date).days
        summary = _build_summary(student.name, first, last, days)

    return _ok(data={"series": series, "summary": summary, "count": len(assessments)})


def _build_summary(name: str, first: Assessment, last: Assessment, days: int) -> str:
    """Gera texto de resumo de evolução em linguagem natural."""
    parts = []
    first_name = name.split()[0]

    if first.weight and last.weight:
        diff = round(last.weight - first.weight, 1)
        if diff < 0:
            parts.append(f"perdeu {abs(diff)}kg")
        elif diff > 0:
            parts.append(f"ganhou {diff}kg")

    if first.waist and last.waist:
        diff = round(last.waist - first.waist, 1)
        if diff < 0:
            parts.append(f"{abs(diff)}cm na cintura")
        elif diff > 0:
            parts.append(f"aumentou {diff}cm na cintura")

    if first.body_fat and last.body_fat:
        parts.append(
            f"reduziu gordura corporal de {first.body_fat}% para {last.body_fat}%"
        )

    if not parts:
        return None

    period = f"Em {days} dias" if days > 0 else "Nesta avaliação"
    return f"{period}, {first_name} " + ", ".join(parts) + "."


# ------------------------------------------------------------------ #
#  GET /api/assessments/public   (público — aluno consulta própria evolução)
# ------------------------------------------------------------------ #

@assessments_bp.route("/public", methods=["GET"])
def get_public_assessments():
    """
    Endpoint público — aluno consulta seu próprio histórico de avaliações.
    Query param: access_token (obrigatório)
    Retorna: série temporal + resumo + lista de avaliações (sem notas internas).
    """
    access_token = (request.args.get("access_token") or "").strip()
    if not access_token:
        return _err("access_token é obrigatório.", 422)

    student = Student.query.filter_by(access_token=access_token).first()
    if not student or not student.is_active:
        return _err("Link de acesso inválido ou expirado.", 404)

    assessments = (
        Assessment.query
        .filter_by(student_id=student.id, trainer_id=student.trainer_id)
        .order_by(Assessment.date)
        .all()
    )

    series = [
        {
            "date":        a.date.isoformat(),
            "weight":      a.weight,
            "body_fat":    a.body_fat,
            "muscle_mass": a.muscle_mass,
            "bmi":         a.bmi,
            "chest":       a.chest,
            "waist":       a.waist,
            "hip":         a.hip,
            "abdomen":     a.abdomen,
            "right_arm":   a.right_arm,
            "left_arm":    a.left_arm,
            "right_thigh": a.right_thigh,
            "left_thigh":  a.left_thigh,
            "right_calf":  a.right_calf,
            "left_calf":   a.left_calf,
            "photo_urls":  a.photo_urls or [],
            "notes":       a.notes,
        }
        for a in assessments
    ]

    summary = None
    if len(assessments) >= 2:
        first = assessments[0]
        last  = assessments[-1]
        days  = (last.date - first.date).days
        summary = _build_summary(student.name, first, last, days)

    return _ok(data={
        "series":  series,
        "summary": summary,
        "count":   len(assessments),
    })


# ================================================================== #
#  SOLICITAÇÕES DE AVALIAÇÃO — aluno envia, trainer aprova            #
# ================================================================== #

def _parse_float_req(value):
    """Converte para float ou None."""
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


# ------------------------------------------------------------------ #
#  POST /api/assessments/public/request  (público — aluno envia)      #
# ------------------------------------------------------------------ #

@assessments_bp.route("/public/request", methods=["POST"])
def create_assessment_request():
    """
    Aluno envia solicitação de avaliação com suas medidas.
    Só é permitida uma solicitação pendente por vez.
    Body: { access_token, date, weight, height, ... }
    """
    data = request.get_json(silent=True) or {}
    access_token = (data.get("access_token") or "").strip()
    if not access_token:
        return _err("access_token é obrigatório.", 422)

    student = Student.query.filter_by(access_token=access_token).first()
    if not student or not student.is_active:
        return _err("Link de acesso inválido ou expirado.", 404)

    # Verifica se já existe uma solicitação pendente
    existing = AssessmentRequest.query.filter_by(
        student_id=student.id, status="pending"
    ).first()
    if existing:
        return _err(
            "Você já tem uma solicitação pendente. Aguarde a análise do seu personal trainer ou cancele-a antes de enviar outra.",
            409,
        )

    date_str = (data.get("date") or "").strip()
    if not date_str:
        return _err("Campo date é obrigatório.", 422)
    try:
        req_date = date_type.fromisoformat(date_str)
    except ValueError:
        return _err("Formato de data inválido. Use YYYY-MM-DD.", 422)

    req = AssessmentRequest(
        student_id=student.id,
        trainer_id=student.trainer_id,
        date=req_date,
        weight=      _parse_float_req(data.get("weight")),
        height=      _parse_float_req(data.get("height")),
        body_fat=    _parse_float_req(data.get("body_fat")),
        muscle_mass= _parse_float_req(data.get("muscle_mass")),
        chest=       _parse_float_req(data.get("chest")),
        waist=       _parse_float_req(data.get("waist")),
        hip=         _parse_float_req(data.get("hip")),
        abdomen=     _parse_float_req(data.get("abdomen")),
        right_arm=   _parse_float_req(data.get("right_arm")),
        left_arm=    _parse_float_req(data.get("left_arm")),
        right_thigh= _parse_float_req(data.get("right_thigh")),
        left_thigh=  _parse_float_req(data.get("left_thigh")),
        right_calf=  _parse_float_req(data.get("right_calf")),
        left_calf=   _parse_float_req(data.get("left_calf")),
        notes=       (data.get("notes") or "").strip() or None,
        photo_urls=  [u for u in (data.get("photo_urls") or []) if isinstance(u, str) and u] or None,
    )
    db.session.add(req)
    db.session.commit()

    return _ok(
        data={"request": req.to_dict()},
        message="Solicitação enviada! Aguarde a aprovação do seu personal trainer.",
        status=201,
    )


# ------------------------------------------------------------------ #
#  DELETE /api/assessments/public/request  (público — aluno cancela)  #
# ------------------------------------------------------------------ #

@assessments_bp.route("/public/request", methods=["DELETE"])
def cancel_assessment_request():
    """
    Aluno cancela sua solicitação pendente.
    Body: { access_token }
    """
    data = request.get_json(silent=True) or {}
    access_token = (data.get("access_token") or "").strip()
    if not access_token:
        return _err("access_token é obrigatório.", 422)

    student = Student.query.filter_by(access_token=access_token).first()
    if not student or not student.is_active:
        return _err("Link de acesso inválido ou expirado.", 404)

    req = AssessmentRequest.query.filter_by(
        student_id=student.id, status="pending"
    ).first()
    if not req:
        return _err("Nenhuma solicitação pendente encontrada.", 404)

    req.status = "cancelled"
    from datetime import datetime, timezone as _tz
    req.reviewed_at = datetime.now(_tz.utc)
    db.session.commit()

    return _ok(message="Solicitação cancelada.")


# ------------------------------------------------------------------ #
#  GET /api/assessments/public/request  (público — aluno consulta)    #
# ------------------------------------------------------------------ #

@assessments_bp.route("/public/request", methods=["GET"])
def get_pending_request():
    """
    Aluno consulta sua solicitação pendente ou mais recente.
    Query param: access_token
    """
    access_token = (request.args.get("access_token") or "").strip()
    if not access_token:
        return _err("access_token é obrigatório.", 422)

    student = Student.query.filter_by(access_token=access_token).first()
    if not student or not student.is_active:
        return _err("Link de acesso inválido ou expirado.", 404)

    # Retorna a solicitação mais recente (pendente ou não)
    req = AssessmentRequest.query.filter_by(
        student_id=student.id,
    ).order_by(AssessmentRequest.created_at.desc()).first()

    return _ok(data={"request": req.to_dict() if req else None})


# ------------------------------------------------------------------ #
#  GET /api/assessments/requests  (trainer — lista pendentes)         #
# ------------------------------------------------------------------ #

@assessments_bp.route("/requests", methods=["GET"])
@jwt_required()
@trainer_required
def list_assessment_requests(**kwargs):
    """Lista solicitações dos alunos para o trainer. Filtra por status e opcionalmente por aluno."""
    trainer = kwargs["current_trainer"]

    status_filter = request.args.get("status", "pending")
    student_id    = request.args.get("student_id", "").strip() or None

    query = AssessmentRequest.query.filter_by(trainer_id=trainer.id, status=status_filter)
    if student_id:
        query = query.filter_by(student_id=student_id)

    requests_list = (
        query
        .order_by(AssessmentRequest.created_at.desc())
        .limit(50)
        .all()
    )

    return _ok(data={
        "requests": [r.to_dict() for r in requests_list],
        "count": len(requests_list),
    })


# ------------------------------------------------------------------ #
#  POST /api/assessments/requests/<id>/approve  (trainer)             #
# ------------------------------------------------------------------ #

@assessments_bp.route("/requests/<req_id>/approve", methods=["POST"])
@jwt_required()
@trainer_required
def approve_assessment_request(req_id, **kwargs):
    """
    Trainer aprova a solicitação: cria avaliação oficial com os dados do aluno.
    """
    trainer = kwargs["current_trainer"]

    req = AssessmentRequest.query.filter_by(id=req_id, trainer_id=trainer.id).first()
    if not req:
        return _err("Solicitação não encontrada.", 404)
    if req.status != "pending":
        return _err("Esta solicitação já foi processada.", 422)

    from datetime import datetime, timezone as _tz
    now = datetime.now(_tz.utc)

    # Cria a avaliação oficial
    assessment = Assessment(
        student_id=req.student_id,
        trainer_id=trainer.id,
        date=req.date,
        weight=      float(req.weight)      if req.weight      else None,
        height=      float(req.height)      if req.height      else None,
        body_fat=    float(req.body_fat)    if req.body_fat    else None,
        muscle_mass= float(req.muscle_mass) if req.muscle_mass else None,
        chest=       float(req.chest)       if req.chest       else None,
        waist=       float(req.waist)       if req.waist       else None,
        hip=         float(req.hip)         if req.hip         else None,
        abdomen=     float(req.abdomen)     if req.abdomen     else None,
        right_arm=   float(req.right_arm)   if req.right_arm   else None,
        left_arm=    float(req.left_arm)    if req.left_arm    else None,
        right_thigh= float(req.right_thigh) if req.right_thigh else None,
        left_thigh=  float(req.left_thigh)  if req.left_thigh  else None,
        right_calf=  float(req.right_calf)  if req.right_calf  else None,
        left_calf=   float(req.left_calf)   if req.left_calf   else None,
        notes=req.notes,
        photo_urls=list(req.photo_urls or []),
    )
    # Calcula IMC
    if assessment.weight and assessment.height:
        assessment.bmi = Assessment.calculate_bmi(assessment.weight, assessment.height)

    db.session.add(assessment)

    req.status = "approved"
    req.reviewed_at = now
    db.session.commit()

    return _ok(
        data={"assessment": assessment.to_dict(), "request": req.to_dict()},
        message="Solicitação aprovada e avaliação registrada.",
    )


# ------------------------------------------------------------------ #
#  POST /api/assessments/requests/<id>/reject  (trainer)              #
# ------------------------------------------------------------------ #

@assessments_bp.route("/requests/<req_id>/reject", methods=["POST"])
@jwt_required()
@trainer_required
def reject_assessment_request(req_id, **kwargs):
    """Trainer rejeita uma solicitação com motivo opcional."""
    trainer = kwargs["current_trainer"]

    req = AssessmentRequest.query.filter_by(id=req_id, trainer_id=trainer.id).first()
    if not req:
        return _err("Solicitação não encontrada.", 404)
    if req.status != "pending":
        return _err("Esta solicitação já foi processada.", 422)

    data = request.get_json(silent=True) or {}
    from datetime import datetime, timezone as _tz
    req.status = "rejected"
    req.reviewed_at = datetime.now(_tz.utc)
    req.rejection_reason = (data.get("reason") or "").strip() or None
    db.session.commit()

    return _ok(
        data={"request": req.to_dict()},
        message="Solicitação rejeitada.",
    )
