"""
Blueprint de IA — /api/ai
Geração de fichas de treino via Anthropic Claude API.
"""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required

from app.extensions import db, limiter
from app.models.student import Student
from app.utils.decorators import trainer_required

ai_bp = Blueprint("ai", __name__, url_prefix="/api/ai")


def _ok(data=None, message="", status=200):
    return jsonify({"success": True, "data": data, "message": message}), status


def _err(message="Erro", status=400):
    return jsonify({"success": False, "data": None, "message": message}), status


# ------------------------------------------------------------------ #
#  POST /api/ai/generate-workout                                      #
# ------------------------------------------------------------------ #

@ai_bp.route("/generate-workout", methods=["POST"])
@jwt_required()
@trainer_required
@limiter.limit("20 per hour")
def generate_workout(**kwargs):
    """
    Gera uma sugestão de ficha de treino via Claude.
    Retorna lista de exercícios no formato WorkoutExercise.
    """
    import os
    import json

    trainer = kwargs["current_trainer"]
    data = request.get_json(silent=True) or {}

    student_id  = data.get("student_id")
    context     = (data.get("context") or "").strip()
    equipments  = data.get("equipments", [])
    category    = data.get("category", "A")

    # Carrega dados do aluno para contextualizar a IA
    student_info = ""
    if student_id:
        student = db.session.get(Student, student_id)
        if student and student.trainer_id == trainer.id:
            student_info = (
                f"Aluno: {student.name}\n"
                f"Objetivo: {student.objective or 'não informado'}\n"
                f"Observações de saúde: {student.health_notes or 'nenhuma'}\n"
            )

    equipment_str = ", ".join(equipments) if equipments else "equipamentos de academia completa"

    prompt = f"""Você é um personal trainer especializado. Crie uma ficha de treino completa.

{student_info}Equipamentos disponíveis: {equipment_str}
Categoria da ficha: {category}
{f"Contexto adicional do trainer: {context}" if context else ""}

Gere uma ficha com 6 a 10 exercícios. Responda APENAS com um JSON válido no seguinte formato:
{{
  "title": "Nome da ficha",
  "exercises": [
    {{
      "exercise_name": "Nome do exercício",
      "muscle_group": "peito|costas|ombro|biceps|triceps|pernas|abdomen|cardio|funcional",
      "sets": 3,
      "reps": "12",
      "load": "sugerido pelo aluno",
      "rest_seconds": 60,
      "technique_notes": "Dica técnica breve",
      "superset_group": null
    }}
  ]
}}

Retorne apenas o JSON, sem texto adicional."""

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return _err("ANTHROPIC_API_KEY não configurada no servidor.", 503)

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)

        message = client.messages.create(
            model="claude-haiku-4-5-20251001",  # modelo rápido e barato para geração de treinos
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )

        raw = message.content[0].text.strip()

        # Remove markdown code blocks se presentes
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]

        result = json.loads(raw)

        # Normaliza e valida
        exercises = []
        for i, ex in enumerate(result.get("exercises", []), start=1):
            exercises.append({
                "exercise_name": str(ex.get("exercise_name", "Exercício")).strip(),
                "muscle_group":  ex.get("muscle_group") or None,
                "sets":          int(ex["sets"]) if ex.get("sets") else None,
                "reps":          str(ex.get("reps", "")) or None,
                "load":          str(ex.get("load", "")) or None,
                "rest_seconds":  int(ex["rest_seconds"]) if ex.get("rest_seconds") else 60,
                "technique_notes": ex.get("technique_notes") or None,
                "video_url":     None,
                "position":      i,
                "superset_group": ex.get("superset_group") or None,
            })

        return _ok(data={
            "title": result.get("title", f"Ficha {category}"),
            "exercises": exercises,
        })

    except json.JSONDecodeError:
        return _err("A IA retornou um formato inesperado. Tente novamente.", 502)
    except Exception as e:
        return _err(f"Erro ao chamar a IA: {str(e)}", 502)
