"""
Serviço de WhatsApp via Evolution API.

Documentação: https://doc.evolution-api.com/
Endpoint principal: POST /message/sendText/{instance}

Variáveis de ambiente necessárias:
  EVOLUTION_API_URL   — URL base da instância Evolution (ex: https://evo.seudominio.com)
  EVOLUTION_API_KEY   — API key global
  EVOLUTION_INSTANCE  — nome da instância WhatsApp conectada
"""
import re
import requests
from flask import current_app


# ------------------------------------------------------------------ #
#  Helpers internos                                                   #
# ------------------------------------------------------------------ #

def _config() -> tuple[str, str, str]:
    """Retorna (base_url, api_key, instance). Levanta ValueError se não configurado."""
    url      = current_app.config.get("EVOLUTION_API_URL", "").rstrip("/")
    api_key  = current_app.config.get("EVOLUTION_API_KEY", "")
    instance = current_app.config.get("EVOLUTION_INSTANCE", "")
    if not url or not api_key or not instance:
        raise ValueError(
            "Evolution API não configurada. "
            "Defina EVOLUTION_API_URL, EVOLUTION_API_KEY e EVOLUTION_INSTANCE no .env"
        )
    return url, api_key, instance


def _normalizar_telefone(phone: str) -> str:
    """
    Normaliza o número para o formato E.164 sem '+', ex: 5511999998888.
    Assume números brasileiros quando não há código de país.
    """
    digits = re.sub(r"\D", "", phone)
    if len(digits) <= 11:          # sem DDI → adiciona 55 (Brasil)
        digits = "55" + digits
    return digits


# ------------------------------------------------------------------ #
#  send_text_message                                                  #
# ------------------------------------------------------------------ #

def send_text_message(phone: str, text: str) -> tuple[bool, str | None]:
    """
    Envia mensagem de texto via Evolution API.

    Args:
        phone: telefone do destinatário (qualquer formato — será normalizado)
        text:  texto a enviar

    Returns:
        (True, None) em caso de sucesso
        (False, "mensagem de erro") em caso de falha
    """
    try:
        base_url, api_key, instance = _config()
    except ValueError as e:
        return False, str(e)

    numero = _normalizar_telefone(phone)
    url    = f"{base_url}/message/sendText/{instance}"

    payload = {
        "number":  numero,
        "text":    text,
        "delay":   1200,   # delay em ms para parecer mais natural
    }

    try:
        resp = requests.post(
            url,
            json=payload,
            headers={
                "Content-Type": "application/json",
                "apikey": api_key,
            },
            timeout=15,
        )
        data = resp.json() if resp.content else {}

        if resp.status_code >= 400:
            msg = data.get("message") or data.get("error") or "Erro na Evolution API."
            # Trata lista de mensagens
            if isinstance(msg, list):
                msg = "; ".join(str(m) for m in msg)
            return False, msg

        return True, None

    except requests.exceptions.Timeout:
        return False, "Timeout na comunicação com a Evolution API."
    except requests.exceptions.RequestException as e:
        return False, f"Erro de rede: {str(e)}"
    except Exception as e:
        return False, f"Erro inesperado: {str(e)}"


# ------------------------------------------------------------------ #
#  send_payment_reminder                                              #
# ------------------------------------------------------------------ #

def send_payment_reminder(
    student_name: str,
    student_phone: str,
    trainer_name: str,
    amount: float,
    due_date,            # date object
    pix_key: str,
) -> tuple[bool, str | None]:
    """
    Envia lembrete de cobrança formatado para o aluno com a chave PIX do trainer.

    Args:
        student_name:   nome do aluno
        student_phone:  telefone do aluno
        trainer_name:   nome do personal trainer
        amount:         valor da mensalidade em BRL
        due_date:       data de vencimento (date)
        pix_key:        chave PIX do trainer (CPF, CNPJ, email, telefone ou chave aleatória)

    Returns:
        (True, None) em caso de sucesso
        (False, "mensagem de erro") em caso de falha
    """
    valor_fmt    = f"R$ {amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    venc_fmt     = due_date.strftime("%d/%m/%Y")
    primeiro_nome = student_name.strip().split()[0]

    mensagem = (
        f"Olá, {primeiro_nome}! 👋\n\n"
        f"Aqui é o(a) *{trainer_name}*. Passando para lembrar que a sua mensalidade "
        f"de *{valor_fmt}* vence hoje, *{venc_fmt}*. 💪\n\n"
        f"Você pode pagar via *PIX*:\n"
        f"🔑 *Chave PIX:* `{pix_key}`\n\n"
        f"Qualquer dúvida, é só chamar. Obrigado(a)! 🙏"
    )

    return send_text_message(student_phone, mensagem)
