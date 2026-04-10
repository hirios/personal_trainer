"""
Model de avaliação física — Assessment.
Cada avaliação registra composição corporal e circunferências de um aluno
em uma data específica. O IMC é calculado automaticamente a partir de
peso e altura.
"""
import uuid
from datetime import datetime, timezone
from app.extensions import db


def _uuid_str() -> str:
    return str(uuid.uuid4())


class Assessment(db.Model):
    """
    Avaliação física de um aluno realizada pelo trainer.
    Campos de medida são opcionais — o trainer preenche os que avaliou.
    """

    __tablename__ = "assessments"

    id = db.Column(db.String(36), primary_key=True, default=_uuid_str)
    student_id = db.Column(
        db.String(36), db.ForeignKey("students.id"), nullable=False, index=True
    )
    trainer_id = db.Column(
        db.String(36), db.ForeignKey("trainers.id"), nullable=False, index=True
    )

    # Data da avaliação (apenas data, sem hora)
    date = db.Column(db.Date, nullable=False)

    # --- Composição corporal ---
    weight = db.Column(db.Float, nullable=True, comment="Peso em kg")
    height = db.Column(db.Float, nullable=True, comment="Altura em cm")
    body_fat = db.Column(db.Float, nullable=True, comment="Percentual de gordura corporal")
    muscle_mass = db.Column(db.Float, nullable=True, comment="Massa muscular em kg")
    bmi = db.Column(db.Float, nullable=True, comment="IMC calculado automaticamente")

    # --- Circunferências (todas em cm) ---
    chest = db.Column(db.Float, nullable=True)
    waist = db.Column(db.Float, nullable=True)
    hip = db.Column(db.Float, nullable=True)
    right_arm = db.Column(db.Float, nullable=True)
    left_arm = db.Column(db.Float, nullable=True)
    right_thigh = db.Column(db.Float, nullable=True)
    left_thigh = db.Column(db.Float, nullable=True)
    right_calf = db.Column(db.Float, nullable=True)
    left_calf = db.Column(db.Float, nullable=True)
    abdomen = db.Column(db.Float, nullable=True)

    # --- Observações e fotos ---
    notes = db.Column(db.Text, nullable=True)
    # Array JSON de URLs relativas: ["uploads/assessments/<id>/foto.jpg", ...]
    photo_urls = db.Column(db.JSON, nullable=True, default=list)

    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # --- Relacionamentos ---
    student = db.relationship("Student", foreign_keys=[student_id], lazy="select")
    trainer = db.relationship("Trainer", foreign_keys=[trainer_id], lazy="select")

    # --- Cálculo de IMC ---
    @staticmethod
    def calculate_bmi(weight_kg: float, height_cm: float):
        """Calcula IMC a partir de peso (kg) e altura (cm). Retorna None se inválido."""
        try:
            if weight_kg and height_cm and height_cm > 0:
                h_m = height_cm / 100.0
                return round(weight_kg / (h_m ** 2), 1)
        except (TypeError, ZeroDivisionError):
            pass
        return None

    # --- Serialização ---
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "student_id": self.student_id,
            "trainer_id": self.trainer_id,
            "date": self.date.isoformat() if self.date else None,
            "weight": self.weight,
            "height": self.height,
            "body_fat": self.body_fat,
            "muscle_mass": self.muscle_mass,
            "bmi": self.bmi,
            "chest": self.chest,
            "waist": self.waist,
            "hip": self.hip,
            "right_arm": self.right_arm,
            "left_arm": self.left_arm,
            "right_thigh": self.right_thigh,
            "left_thigh": self.left_thigh,
            "right_calf": self.right_calf,
            "left_calf": self.left_calf,
            "abdomen": self.abdomen,
            "notes": self.notes,
            "photo_urls": self.photo_urls or [],
            "created_at": self.created_at.isoformat(),
        }

    def __repr__(self) -> str:
        return f"<Assessment student={self.student_id} date={self.date}>"
