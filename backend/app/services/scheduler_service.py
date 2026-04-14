"""
Serviço de tarefas agendadas do FitFlow Pro.

Jobs registrados:
  - cobrar_vencimentos_hoje  → 10:00 todos os dias
    Para cada trainer com alunos cujo payment_day == hoje:
      Se o trainer tiver pix_key configurada E o aluno tiver telefone,
      envia mensagem de cobrança via WhatsApp (Evolution API).
"""
import logging
from datetime import date

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

# Instância global — inicializada uma única vez por _init_scheduler()
_scheduler: BackgroundScheduler | None = None


# ------------------------------------------------------------------ #
#  Job: cobrança por vencimento                                       #
# ------------------------------------------------------------------ #

def _job_cobrar_vencimentos(app):
    """
    Roda às 10:00. Para cada trainer, verifica quais alunos vencem hoje e
    envia o lembrete via WhatsApp se o trainer tiver chave PIX cadastrada.
    """
    from app.extensions import db
    from app.models.trainer import Trainer
    from app.models.student import Student
    from app.models.payment import Payment
    from app.services.whatsapp_service import send_payment_reminder

    with app.app_context():
        hoje = date.today()
        logger.info("[Scheduler] Iniciando job cobrar_vencimentos para %s", hoje)

        # Carrega todos os trainers com pix_key configurada
        trainers = Trainer.query.filter(
            Trainer.pix_key.isnot(None),
            Trainer.pix_key != "",
            Trainer.is_active == True,
        ).all()

        enviados  = 0
        ignorados = 0
        erros     = 0

        for trainer in trainers:
            # Alunos ativos deste trainer cujo dia de vencimento é hoje
            alunos = Student.query.filter(
                Student.trainer_id  == trainer.id,
                Student.status      == "active",
                Student.is_active   == True,
                Student.payment_day == hoje.day,
                Student.monthly_fee > 0,
            ).all()

            for aluno in alunos:
                if not aluno.phone:
                    ignorados += 1
                    continue

                # Busca (ou cria) o Payment do mês atual para este aluno
                inicio_mes = hoje.replace(day=1)
                try:
                    proximo_mes = inicio_mes.replace(month=inicio_mes.month % 12 + 1)
                    if inicio_mes.month == 12:
                        proximo_mes = inicio_mes.replace(year=inicio_mes.year + 1, month=1)
                except ValueError:
                    proximo_mes = inicio_mes.replace(year=inicio_mes.year + 1, month=1)

                pagamento = Payment.query.filter(
                    Payment.student_id == aluno.id,
                    Payment.trainer_id == trainer.id,
                    Payment.due_date   >= inicio_mes,
                    Payment.due_date   <  proximo_mes,
                    Payment.status.in_(["pending", "overdue"]),
                ).first()

                # Se não existir pagamento pendente, não envia
                if not pagamento:
                    ignorados += 1
                    continue

                ok, err = send_payment_reminder(
                    student_name  = aluno.name,
                    student_phone = aluno.phone,
                    trainer_name  = trainer.name,
                    amount        = float(aluno.monthly_fee),
                    due_date      = pagamento.due_date,
                    pix_key       = trainer.pix_key,
                )

                if ok:
                    enviados += 1
                    logger.info(
                        "[Scheduler] Cobrança enviada → aluno=%s trainer=%s",
                        aluno.name, trainer.name,
                    )
                else:
                    erros += 1
                    logger.warning(
                        "[Scheduler] Falha ao enviar cobrança → aluno=%s erro=%s",
                        aluno.name, err,
                    )

        logger.info(
            "[Scheduler] cobrar_vencimentos concluído: enviados=%d ignorados=%d erros=%d",
            enviados, ignorados, erros,
        )


# ------------------------------------------------------------------ #
#  init_scheduler                                                     #
# ------------------------------------------------------------------ #

def init_scheduler(app) -> None:
    """
    Registra e inicia o scheduler com os jobs do FitFlow Pro.
    Deve ser chamado uma única vez em create_app(), fora do modo TESTING.
    """
    global _scheduler

    if _scheduler is not None:
        return  # evita registro duplicado em hot-reload do Flask dev server

    _scheduler = BackgroundScheduler(timezone="America/Sao_Paulo")

    # Job de cobrança: todo dia às 10:00 (horário de Brasília)
    _scheduler.add_job(
        func     = _job_cobrar_vencimentos,
        trigger  = CronTrigger(hour=10, minute=0, timezone="America/Sao_Paulo"),
        args     = [app],
        id       = "cobrar_vencimentos_hoje",
        name     = "Cobrança WhatsApp — vencimentos do dia",
        replace_existing = True,
    )

    _scheduler.start()
    logger.info("[Scheduler] APScheduler iniciado. Jobs: %s", [j.id for j in _scheduler.get_jobs()])
