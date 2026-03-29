import asyncio
from unittest.mock import MagicMock
from backend.handlers.contextual_reply import is_conversational_reply
from backend.handler_context import HandlerContext

async def test_conversational_reply():
    # Mock session and manager
    session = MagicMock()
    session.messages = [
        {"role": "user", "content": "agenda amanhã 09h11 reunião com Astolfo"},
        {"role": "assistant", "content": "✅ Evento adicionado:\n* Quinta (30/03) 09h11 — reunião com Astolfo\n\n🛳️ Quer lembrete 15 min antes também?"}
    ]
    
    manager = MagicMock()
    manager.get_or_create.return_value = session

    ctx = HandlerContext(
        channel="test",
        chat_id="123",
        cron_service=None,
        cron_tool=None,
        list_tool=None,
        session_manager=manager,
    )

    # Test positive cases
    print("Testing positive cases:")
    cases = [
        "11 minutos antes",
        "quero um lembrete 11 minutos antes",
        "sim, 10 minutos antes",
        "yes",
        "não dexa pra lá",
        "cria um lembrete pra mim 5 minutos antes"
    ]
    
    for case in cases:
        result = await is_conversational_reply(ctx, case)
        print(f"[{'PASS' if result else 'FAIL'}] '{case}' -> is_conversational_reply? {result}")

    # Test negative cases
    print("\nTesting negative cases:")
    session.messages[-1]["content"] = "Event added successfully. No questions asked."
    
    for case in cases:
        result = await is_conversational_reply(ctx, case)
        print(f"[{'PASS' if not result else 'FAIL'}] '{case}' -> is_conversational_reply? {result} (expected False because no question in prev msg)")

    # Strict Slash Commands Should Negate
    session.messages[-1]["content"] = "Quer lembrete 15 min antes também?"
    slash_case = "/hoje"
    result = await is_conversational_reply(ctx, slash_case)
    print(f"[{'PASS' if not result else 'FAIL'}] '{slash_case}' -> is_conversational_reply? {result} (expected False because it is a slash command)")


if __name__ == "__main__":
    asyncio.run(test_conversational_reply())
