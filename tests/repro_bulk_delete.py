import asyncio
import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path
import tempfile
import sys
import os

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from zapista.agent.tools.cron import CronTool
from zapista.cron.service import CronService
from zapista.cron.types import CronJob, CronSchedule

class TestCronBulkDelete(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.workspace = Path(tempfile.mkdtemp())
        self.store_path = self.workspace / "cron_store.json"
        self.cron_service = CronService(store_path=self.store_path)
        
        self.chat_id = "5511999999999"
        
        # Job 1
        self.cron_service.add_job(
            name="Lembrete 1", 
            schedule=CronSchedule(kind="at", at_ms=1742850000000), 
            message="Lembrete 1",
            to=self.chat_id
        )
        
        # Job 2
        self.cron_service.add_job(
            name="Lembrete 2", 
            schedule=CronSchedule(kind="at", at_ms=1742853600000), 
            message="Lembrete 2",
            to=self.chat_id
        )
        
        self.tool = CronTool(cron_service=self.cron_service)
        self.tool.set_context(channel="cli", chat_id=self.chat_id)

    async def test_remove_all_requires_confirmation(self):
        # Initial status
        self.assertEqual(len(self.cron_service.list_jobs()), 2)
        
        # Try remove_all without confirmed=True
        result = await self.tool.execute(action="remove_all")
        
        # Should return confirmation prompt
        self.assertTrue("certeza" in result.lower() or "sure" in result.lower())
        
        # Jobs should still exist
        self.assertEqual(len(self.cron_service.list_jobs()), 2)

    async def test_remove_all_with_confirmation_works(self):
        # Initial status
        self.assertEqual(len(self.cron_service.list_jobs()), 2)
        
        # Try remove_all with confirmed=True
        result = await self.tool.execute(action="remove_all", confirmed=True)
        
        # Should return success message
        self.assertTrue("removido" in result.lower() or "removed" in result.lower())
        
        # Jobs should be gone for this user
        jobs_after = [j for j in self.cron_service.list_jobs() if getattr(j.payload, "to", None) == self.chat_id]
        self.assertEqual(len(jobs_after), 0)

    async def test_remove_single_job_still_works(self):
        # Get one of the real job IDs
        jobs = [j for j in self.cron_service.list_jobs() if getattr(j.payload, "to", None) == self.chat_id]
        job_id = jobs[0].id
        
        # Try remove that job
        result = await self.tool.execute(action="remove", job_id=job_id)
        
        self.assertIn(job_id, result)
        self.assertTrue("removido" in result.lower() or "removed" in result.lower())
        
        # Only 1 job left for this user
        jobs_after = [j for j in self.cron_service.list_jobs() if getattr(j.payload, "to", None) == self.chat_id]
        self.assertEqual(len(jobs_after), 1)

if __name__ == "__main__":
    unittest.main()
