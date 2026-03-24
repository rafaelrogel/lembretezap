from locust import HttpUser, task, between, events
import random
import json

API_KEY = "zappelin-test-secret-key-12345"

class ZappelinUser(HttpUser):
    wait_time = between(0.1, 0.5)  # Wait 100-500ms between tasks
    host = "http://localhost:8000"

    def on_start(self):
        self.headers = {"X-API-Key": API_KEY}
        self.user_id = random.randint(1, 100)

    @task(10)
    def get_users(self):
        self.client.get("/users", headers=self.headers)

    @task(5)
    def get_user_lists(self):
        self.client.get(
            f"/users/{self.user_id}/lists",
            headers=self.headers
        )

    @task(5)
    def get_user_events(self):
        tipo = random.choice(["lembrete", "evento", None])
        params = {"tipo": tipo} if tipo else {}
        self.client.get(
            f"/users/{self.user_id}/events",
            headers=self.headers,
            params=params
        )

    @task(3)
    def get_audit_log(self):
        limit = random.choice([100, 250, 500])
        self.client.get(
            "/audit",
            headers=self.headers,
            params={"limit": limit}
        )

    @task(1)
    def health_check(self):
        self.client.get("/health")


class ZappelinAdminUser(HttpUser):
    wait_time = between(0.5, 2)
    host = "http://localhost:8000"

    def on_start(self):
        self.headers = {"X-API-Key": API_KEY}

    @task(10)
    def heavy_audit_query(self):
        self.client.get(
            "/audit",
            headers=self.headers,
            params={"limit": 500}
        )

    @task(5)
    def get_all_users(self):
        self.client.get("/users", headers=self.headers)
