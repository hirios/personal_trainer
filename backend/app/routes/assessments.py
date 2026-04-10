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
