"""
Exporta todos os models para que o Flask-Migrate os detecte automaticamente.
Importe sempre de app.models, nunca diretamente dos submódulos.
"""
from .user import User
from .trainer import Trainer
from .student import Student
from .workout import Workout, WorkoutExercise
from .appointment import Appointment
from .payment import Payment

__all__ = ["User", "Trainer", "Student", "Workout", "WorkoutExercise", "Appointment", "Payment"]
