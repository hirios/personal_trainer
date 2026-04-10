"""
Models de treino — Workout e WorkoutExercise.
Workout representa uma ficha de treino; WorkoutExercise são os exercícios da ficha.
"""
import uuid
from datetime import datetime, timezone
from app.extensions import db


def _uuid_str() -> str:
    return str(uuid.uuid4())


class Workout(db.Model):
    """
    Ficha de treino criada pelo trainer para um aluno.
    Uma ficha pode ter múltiplos exercícios ordenados por `position`.
    """

    __tablename__ = "workouts"

    id = db.Column(db.String(36), primary_key=True, default=_uuid_str)
    student_id = db.Column(
        db.String(36), db.ForeignKey("students.id"), nullable=False, index=True
    )
    trainer_id = db.Column(
        db.String(36), db.ForeignKey("trainers.id"), nullable=False, index=True
    )

    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    category = db.Column(
        db.String(50),
        nullable=True,
        comment="ex: A, B, C, D, Cardio, Funcional, Fullbody",
    )

    is_active = db.Column(db.Boolean, default=True, nullable=False)
    starts_at = db.Column(db.DateTime(timezone=True), nullable=True)
    ends_at = db.Column(db.DateTime(timezone=True), nullable=True)

    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # --- Relacionamentos ---
    exercises = db.relationship(
        "WorkoutExercise",
        back_populates="workout",
        cascade="all, delete-orphan",
        order_by="WorkoutExercise.position",
        lazy="select",
    )
    student = db.relationship("Student", foreign_keys=[student_id], lazy="select")
    trainer = db.relationship("Trainer", foreign_keys=[trainer_id], lazy="select")

    # --- Serialização ---
    def to_dict(self, include_exercises: bool = False) -> dict:
        data = {
            "id": self.id,
            "student_id": self.student_id,
            "trainer_id": self.trainer_id,
            "title": self.title,
            "description": self.description,
            "category": self.category,
            "is_active": self.is_active,
            "starts_at": self.starts_at.isoformat() if self.starts_at else None,
            "ends_at": self.ends_at.isoformat() if self.ends_at else None,
            "exercise_count": len(self.exercises),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
        if include_exercises:
            data["exercises"] = [e.to_dict() for e in self.exercises]
        return data

    def __repr__(self) -> str:
        return f"<Workout '{self.title}' student={self.student_id}>"


class WorkoutExercise(db.Model):
    """
    Exercício dentro de uma ficha de treino.
    `position` define a ordem de exibição (1-based).
    `superset_group` agrupa exercícios em supersets (mesmo número = mesmo superset).
    """

    __tablename__ = "workout_exercises"

    id = db.Column(db.String(36), primary_key=True, default=_uuid_str)
    workout_id = db.Column(
        db.String(36), db.ForeignKey("workouts.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    exercise_name = db.Column(db.String(200), nullable=False)
    muscle_group = db.Column(
        db.String(50),
        nullable=True,
        comment="peito | costas | ombro | biceps | triceps | pernas | abdomen | cardio | funcional",
    )

    sets = db.Column(db.Integer, nullable=True, comment="Número de séries")
    reps = db.Column(db.String(20), nullable=True, comment="Repetições: '12', '8-12', 'até a falha'")
    load = db.Column(db.String(30), nullable=True, comment="Carga: '20kg', '50%', 'corporal'")
    rest_seconds = db.Column(db.Integer, nullable=True, comment="Descanso em segundos")

    technique_notes = db.Column(db.Text, nullable=True)
    video_url = db.Column(db.String(500), nullable=True)

    position = db.Column(db.Integer, nullable=False, default=1)
    superset_group = db.Column(
        db.Integer,
        nullable=True,
        comment="Exercícios com mesmo valor são exibidos como superset",
    )

    # --- Relacionamentos ---
    workout = db.relationship("Workout", back_populates="exercises")

    # --- Serialização ---
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "workout_id": self.workout_id,
            "exercise_name": self.exercise_name,
            "muscle_group": self.muscle_group,
            "sets": self.sets,
            "reps": self.reps,
            "load": self.load,
            "rest_seconds": self.rest_seconds,
            "technique_notes": self.technique_notes,
            "video_url": self.video_url,
            "position": self.position,
            "superset_group": self.superset_group,
        }

    def __repr__(self) -> str:
        return f"<WorkoutExercise pos={self.position} '{self.exercise_name}'>"
