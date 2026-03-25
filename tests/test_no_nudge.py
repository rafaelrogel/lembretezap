import asyncio
import os
import sys
from pathlib import Path

# Adiciona o diretório raiz ao sys.path para importações
sys.path.append(str(Path(__file__).parent.parent))

from zapista.cron.service import CronService
from zapista.cron.types import CronSchedule, CronJob
from zapista.agent.tools.cron import CronTool
from backend.database import SessionLocal

async def test_one_time_no_nudge():
    print("Testing one-time reminder nudge prevention...")
    
    # Setup
    db_path = Path("test_cron.db")
    if db_path.exists():
        db_path.unlink()
    
    jobs_json = Path("test_jobs.json")
    if jobs_json.exists():
        jobs_json.unlink()
        
    service = CronService(jobs_json)
    tool = CronTool(cron_service=service)
    tool.set_context("whatsapp", "test_user")
    
    # 1. Simular adição de lembrete único via CronTool
    # Note: CronTool.execute(action="add") agora regula delete_after_run=True e SEM follow-up
    result = await tool._add_job(
        message="Não esquecer o teste",
        every_seconds=None,
        in_seconds=3600,
        cron_expr=None
    )
    
    jobs = service.list_jobs()
    assert len(jobs) == 1, f"Expected 1 job, got {len(jobs)}"
    job = jobs[0]
    
    # Verificar se delete_after_run está True
    assert job.delete_after_run is True, "One-time reminder should have delete_after_run=True"
    
    # Verificar se NÃO criou job de deadline_check (para lembretes únicos)
    deadline_jobs = [j for j in service.list_jobs(include_disabled=True) if getattr(j.payload, "kind", None) == "deadline_check"]
    assert len(deadline_jobs) == 0, "No deadline_check job should be created for one-time reminders"
    
    print("✓ One-time reminder configuration verified (fire-and-forget).")

    # 2. Testar se o CronService._execute_job desativa o job após 1 execução
    # se remind_again_max_count for atingido ou se for lembrete de follow-up órfão.
    
    print("Testing termination of legacy nudge loops...")
    
    # Simular um job de follow-up que "sobrou"
    followup_job = service.add_job(
        name="Follow-up órfão",
        schedule=CronSchedule(kind="at", at_ms=int(asyncio.get_event_loop().time() * 1000)),
        message="Ainda aqui?",
        to="test_user",
        channel="whatsapp",
        remind_again_max_count=0, # Limite atingido
        parent_job_id="some_old_id",
        delete_after_run=False # Simular estado antigo
    )
    
    # Executar o job
    await service._execute_job(followup_job)
    
    # O job deve ter sido removido agora (lógica de remoção de lembretes únicos 'at')
    updated_job = service.get_job(followup_job.id)
    assert updated_job is None, "Follow-up loop/one-time reminder should be removed after execution"
    
    print("✓ Legacy nudge loop termination verified.")

    # Cleanup
    if db_path.exists():
        db_path.unlink()
    if jobs_json.exists():
        jobs_json.unlink()

if __name__ == "__main__":
    asyncio.run(test_one_time_no_nudge())
