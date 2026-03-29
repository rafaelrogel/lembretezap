"""Intercept NLP commands if they look like conversational replies to recent AI questions."""

from backend.handler_context import HandlerContext

def _is_relevant_question(msg_content: str) -> bool:
    """Check if the bot's message is a question about reminders/events/agenda."""
    if not msg_content or "?" not in msg_content:
        return False
        
    lower = msg_content.lower()
    
    # Check for relevant keywords in the question
    # "Quer lembrete 15 min antes também?" -> matches lembrete and antes
    # "¿Quieres un recordatorio?"
    keywords = ["lembrete", "antes", "recordatorio", "remind", "reminder", "agenda", "evento", "aviso", "avisar"]
    return any(kw in lower for kw in keywords)

def _is_reply_intent(user_content: str) -> bool:
    """Check if the user's message is likely a reply rather than a standalone command."""
    if not user_content:
        return False
        
    lower = user_content.lower().strip()
    
    # If it starts with a strict slash command, it's not a conversational reply
    if user_content.strip().startswith("/"):
        # Exception: some users might type /lembrete thinking they need it, 
        # but if it contains "antes" or "minutos" we should probably still consider it a contextual reply.
        # But to be safe, exact commands usually break conversational flow.
        return False

    # Positive conversational signals for reminder follow-ups
    reply_signals = [
        "antes", "minutos", "horas", "dias", "sim", "não", "yes", "no", 
        "si", "quero", "quiero", "i want", "pode ser", "por favor"
    ]
    return any(sig in lower for sig in reply_signals)

async def is_conversational_reply(ctx: HandlerContext, content: str) -> bool:
    """
    Returns True if the user is replying to a recent AI question about reminders.
    This signal tells the router to bypass rigid regex handlers and fallback to the LLM agent.
    """
    if not ctx.session_manager:
        return False
        
    try:
        session_key = f"{ctx.channel}:{ctx.chat_id}"
        session = ctx.session_manager.get_or_create(session_key)
        history = session.messages or []
        
        # Look for the last message from the assistant in the last 5 messages
        last_assistant_msg = None
        for msg in reversed(history[-5:]):
            if msg.get("role") == "assistant":
                last_assistant_msg = msg.get("content", "")
                break
                
        if _is_relevant_question(last_assistant_msg) and _is_reply_intent(content):
            return True
            
    except Exception as e:
        from backend.logger import get_logger
        logger = get_logger(__name__)
        logger.debug("conversational_reply_check_failed", extra={"extra": {"error": str(e)}})
        
    return False
