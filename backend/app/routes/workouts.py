"""
Blueprint de treinos — /api/workouts
Gestão de fichas e exercícios. Todas as rotas (exceto /public) exigem trainer autenticado.
"""
import uuid
from datetime import datetime, timezone
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from sqlalchemy import desc

from app.extensions import db
from app.models.workout import Workout, WorkoutExercise
from app.models.student import Student
from app.utils.decorators import trainer_required

workouts_bp = Blueprint("workouts", __name__, url_prefix="/api/workouts")

VALID_MUSCLE_GROUPS = {
    "peito", "costas", "ombro", "biceps", "triceps",
    "pernas", "abdomen", "cardio", "funcional", "outro",
}

VALID_CATEGORIES = {"A", "B", "C", "D", "E", "Cardio", "Funcional", "Fullbody", "Outro"}


# ------------------------------------------------------------------ #
#  Helpers                                                            #
# ------------------------------------------------------------------ #

def _ok(data=None, message="", status=200):
    return jsonify({"success": True, "data": data, "message": message}), status


def _err(message="Erro", status=400):
    return jsonify({"success": False, "data": None, "message": message}), status


def _get_workout_or_404(workout_id: str, trainer_id: str):
    """Garante que o treino existe e pertence ao trainer."""
    w = db.session.get(Workout, workout_id)
    if not w or w.trainer_id != trainer_id:
        return None, _err("Treino não encontrado.", 404)
    return w, None


def _next_position(workout_id: str) -> int:
    """Retorna a próxima posição disponível na ficha."""
    last = (
        WorkoutExercise.query
        .filter_by(workout_id=workout_id)
        .order_by(desc(WorkoutExercise.position))
        .first()
    )
    return (last.position + 1) if last else 1


# ------------------------------------------------------------------ #
#  GET /api/workouts/?student_id=X                                    #
# ------------------------------------------------------------------ #

@workouts_bp.route("/", methods=["GET"])
@jwt_required()
@trainer_required
def list_workouts(**kwargs):
    """Lista fichas de treino. Filtra por aluno e/ou status ativo."""
    trainer = kwargs["current_trainer"]

    student_id = request.args.get("student_id")
    active_only = request.args.get("active", "").lower() == "true"

    query = Workout.query.filter_by(trainer_id=trainer.id)

    if student_id:
        # Garante que o aluno pertence ao trainer
        student = db.session.get(Student, student_id)
        if not student or student.trainer_id != trainer.id:
            return _err("Aluno não encontrado.", 404)
        query = query.filter_by(student_id=student_id)

    if active_only:
        query = query.filter_by(is_active=True)

    workouts = query.order_by(desc(Workout.created_at)).all()
    return _ok(data={"workouts": [w.to_dict() for w in workouts]})


# ------------------------------------------------------------------ #
#  POST /api/workouts/                                                #
# ------------------------------------------------------------------ #

@workouts_bp.route("/", methods=["POST"])
@jwt_required()
@trainer_required
def create_workout(**kwargs):
    """Cria uma nova ficha de treino."""
    trainer = kwargs["current_trainer"]
    data = request.get_json(silent=True) or {}

    title = (data.get("title") or "").strip()
    if not title:
        return _err("O título da ficha é obrigatório.", 422)

    student_id = data.get("student_id")
    if not student_id:
        return _err("student_id é obrigatório.", 422)

    student = db.session.get(Student, student_id)
    if not student or student.trainer_id != trainer.id:
        return _err("Aluno não encontrado.", 404)

    # Parse datas opcionais
    def _parse_dt(val):
        if not val:
            return None
        try:
            return datetime.fromisoformat(val.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            return None

    workout = Workout(
        title=title,
        description=(data.get("description") or "").strip() or None,
        category=data.get("category") or None,
        student_id=student_id,
        trainer_id=trainer.id,
        is_active=data.get("is_active", True),
        starts_at=_parse_dt(data.get("starts_at")),
        ends_at=_parse_dt(data.get("ends_at")),
    )
    db.session.add(workout)
    db.session.commit()

    return _ok(
        data={"workout": workout.to_dict(include_exercises=True)},
        message="Ficha criada com sucesso!",
        status=201,
    )


# ------------------------------------------------------------------ #
#  GET /api/workouts/public/<workout_id>?token=<access_token>        #
# ------------------------------------------------------------------ #

@workouts_bp.route("/public/<workout_id>", methods=["GET"])
def public_workout(workout_id):
    """Endpoint público: aluno acessa o treino via access_token."""
    token = request.args.get("token", "")
    if not token:
        return _err("Token de acesso obrigatório.", 401)

    student = Student.query.filter_by(access_token=token).first()
    if not student or not student.is_active:
        return _err("Token inválido ou conta desativada.", 401)

    workout = db.session.get(Workout, workout_id)
    if not workout or workout.student_id != student.id:
        return _err("Treino não encontrado.", 404)

    # Registra último acesso do aluno — atualiza no máximo 1x a cada 5 minutos
    # para evitar writes contínuos no SQLite que acionam o Live Server em dev
    now = datetime.now(timezone.utc)
    last = student.last_access_at
    if last and last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    if not last or (now - last).total_seconds() > 300:
        student.last_access_at = now
        db.session.commit()

    data = workout.to_dict(include_exercises=True)
    data["student_name"] = student.name
    data["trainer_name"] = workout.trainer.name
    data["trainer_avatar"] = workout.trainer.avatar_url

    return _ok(data={"workout": data})


# ------------------------------------------------------------------ #
#  GET /api/workouts/<id>                                             #
# ------------------------------------------------------------------ #

@workouts_bp.route("/<workout_id>", methods=["GET"])
@jwt_required()
@trainer_required
def get_workout(workout_id, **kwargs):
    """Retorna ficha com todos os exercícios ordenados por position."""
    trainer = kwargs["current_trainer"]
    workout, err = _get_workout_or_404(workout_id, trainer.id)
    if err:
        return err
    return _ok(data={"workout": workout.to_dict(include_exercises=True)})


# ------------------------------------------------------------------ #
#  PATCH /api/workouts/<id>                                           #
# ------------------------------------------------------------------ #

@workouts_bp.route("/<workout_id>", methods=["PATCH"])
@jwt_required()
@trainer_required
def update_workout(workout_id, **kwargs):
    """Atualiza metadados da ficha (não altera exercícios)."""
    trainer = kwargs["current_trainer"]
    workout, err = _get_workout_or_404(workout_id, trainer.id)
    if err:
        return err

    data = request.get_json(silent=True) or {}

    for field in ("title", "description", "category", "is_active"):
        if field in data:
            val = data[field]
            if isinstance(val, str):
                val = val.strip() or None
            setattr(workout, field, val)

    for field in ("starts_at", "ends_at"):
        if field in data:
            raw = data[field]
            if raw:
                try:
                    setattr(workout, field, datetime.fromisoformat(raw.replace("Z", "+00:00")))
                except (ValueError, AttributeError):
                    return _err(f"Formato de data inválido para {field}.", 422)
            else:
                setattr(workout, field, None)

    workout.updated_at = datetime.now(timezone.utc)
    db.session.commit()
    return _ok(data={"workout": workout.to_dict()}, message="Ficha atualizada.")


# ------------------------------------------------------------------ #
#  DELETE /api/workouts/<id>                                          #
# ------------------------------------------------------------------ #

@workouts_bp.route("/<workout_id>", methods=["DELETE"])
@jwt_required()
@trainer_required
def delete_workout(workout_id, **kwargs):
    """Soft delete — marca is_active=False."""
    trainer = kwargs["current_trainer"]
    workout, err = _get_workout_or_404(workout_id, trainer.id)
    if err:
        return err

    workout.is_active = False
    workout.updated_at = datetime.now(timezone.utc)
    db.session.commit()
    return _ok(message="Ficha desativada.")


# ------------------------------------------------------------------ #
#  POST /api/workouts/<id>/duplicate                                  #
# ------------------------------------------------------------------ #

@workouts_bp.route("/<workout_id>/duplicate", methods=["POST"])
@jwt_required()
@trainer_required
def duplicate_workout(workout_id, **kwargs):
    """Duplica a ficha (com todos os exercícios) para o mesmo aluno ou outro."""
    trainer = kwargs["current_trainer"]
    source, err = _get_workout_or_404(workout_id, trainer.id)
    if err:
        return err

    data = request.get_json(silent=True) or {}
    target_student_id = data.get("student_id", source.student_id)

    # Valida aluno destino
    student = db.session.get(Student, target_student_id)
    if not student or student.trainer_id != trainer.id:
        return _err("Aluno destino não encontrado.", 404)

    new_title = data.get("title") or f"{source.title} (cópia)"

    new_workout = Workout(
        title=new_title,
        description=source.description,
        category=source.category,
        student_id=target_student_id,
        trainer_id=trainer.id,
        is_active=True,
    )
    db.session.add(new_workout)
    db.session.flush()  # gera id antes de adicionar exercícios

    for ex in source.exercises:
        new_ex = WorkoutExercise(
            workout_id=new_workout.id,
            exercise_name=ex.exercise_name,
            muscle_group=ex.muscle_group,
            sets=ex.sets,
            reps=ex.reps,
            load=ex.load,
            rest_seconds=ex.rest_seconds,
            technique_notes=ex.technique_notes,
            video_url=ex.video_url,
            position=ex.position,
            superset_group=ex.superset_group,
        )
        db.session.add(new_ex)

    db.session.commit()
    return _ok(
        data={"workout": new_workout.to_dict(include_exercises=True)},
        message="Ficha duplicada com sucesso!",
        status=201,
    )


# ------------------------------------------------------------------ #
#  POST /api/workouts/<id>/exercises                                  #
# ------------------------------------------------------------------ #

@workouts_bp.route("/<workout_id>/exercises", methods=["POST"])
@jwt_required()
@trainer_required
def add_exercise(workout_id, **kwargs):
    """Adiciona um exercício à ficha."""
    trainer = kwargs["current_trainer"]
    workout, err = _get_workout_or_404(workout_id, trainer.id)
    if err:
        return err

    data = request.get_json(silent=True) or {}
    name = (data.get("exercise_name") or "").strip()
    if not name:
        return _err("Nome do exercício é obrigatório.", 422)

    position = data.get("position") or _next_position(workout_id)

    exercise = WorkoutExercise(
        workout_id=workout_id,
        exercise_name=name,
        muscle_group=data.get("muscle_group") or None,
        sets=data.get("sets") or None,
        reps=str(data.get("reps") or "") or None,
        load=str(data.get("load") or "") or None,
        rest_seconds=data.get("rest_seconds") or None,
        technique_notes=(data.get("technique_notes") or "").strip() or None,
        video_url=(data.get("video_url") or "").strip() or None,
        position=position,
        superset_group=data.get("superset_group") or None,
    )
    db.session.add(exercise)
    workout.updated_at = datetime.now(timezone.utc)
    db.session.commit()

    return _ok(
        data={"exercise": exercise.to_dict()},
        message="Exercício adicionado.",
        status=201,
    )


# ------------------------------------------------------------------ #
#  PATCH /api/workouts/<id>/exercises/<ex_id>                         #
# ------------------------------------------------------------------ #

@workouts_bp.route("/<workout_id>/exercises/<exercise_id>", methods=["PATCH"])
@jwt_required()
@trainer_required
def update_exercise(workout_id, exercise_id, **kwargs):
    """Atualiza campos de um exercício."""
    trainer = kwargs["current_trainer"]
    workout, err = _get_workout_or_404(workout_id, trainer.id)
    if err:
        return err

    exercise = db.session.get(WorkoutExercise, exercise_id)
    if not exercise or exercise.workout_id != workout_id:
        return _err("Exercício não encontrado.", 404)

    data = request.get_json(silent=True) or {}

    updatable = {
        "exercise_name", "muscle_group", "sets", "reps",
        "load", "rest_seconds", "technique_notes", "video_url",
        "position", "superset_group",
    }
    for field in updatable:
        if field in data:
            val = data[field]
            if isinstance(val, str):
                val = val.strip() or None
            setattr(exercise, field, val)

    workout.updated_at = datetime.now(timezone.utc)
    db.session.commit()
    return _ok(data={"exercise": exercise.to_dict()})


# ------------------------------------------------------------------ #
#  DELETE /api/workouts/<id>/exercises/<ex_id>                        #
# ------------------------------------------------------------------ #

@workouts_bp.route("/<workout_id>/exercises/<exercise_id>", methods=["DELETE"])
@jwt_required()
@trainer_required
def delete_exercise(workout_id, exercise_id, **kwargs):
    """Remove um exercício da ficha."""
    trainer = kwargs["current_trainer"]
    workout, err = _get_workout_or_404(workout_id, trainer.id)
    if err:
        return err

    exercise = db.session.get(WorkoutExercise, exercise_id)
    if not exercise or exercise.workout_id != workout_id:
        return _err("Exercício não encontrado.", 404)

    db.session.delete(exercise)
    workout.updated_at = datetime.now(timezone.utc)
    db.session.commit()
    return _ok(message="Exercício removido.")


# ------------------------------------------------------------------ #
#  POST /api/workouts/<id>/exercises/reorder                          #
# ------------------------------------------------------------------ #

@workouts_bp.route("/<workout_id>/exercises/reorder", methods=["POST"])
@jwt_required()
@trainer_required
def reorder_exercises(workout_id, **kwargs):
    """
    Atualiza posições em bulk.
    Body: [{"id": "uuid", "position": 1}, ...]
    """
    trainer = kwargs["current_trainer"]
    workout, err = _get_workout_or_404(workout_id, trainer.id)
    if err:
        return err

    items = request.get_json(silent=True) or []
    if not isinstance(items, list):
        return _err("Envie um array de {id, position}.", 422)

    for item in items:
        ex_id = item.get("id")
        pos = item.get("position")
        if not ex_id or pos is None:
            continue
        ex = db.session.get(WorkoutExercise, ex_id)
        if ex and ex.workout_id == workout_id:
            ex.position = int(pos)

    workout.updated_at = datetime.now(timezone.utc)
    db.session.commit()
    return _ok(message="Ordem atualizada.")
