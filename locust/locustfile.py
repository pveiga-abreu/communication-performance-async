import random

from locust import HttpUser, tag, task


class User(HttpUser):
    @tag("create")
    @task
    def create_order(self):
        customer_id = str(random.randint(1, 1000))
        total_amount = random.randint(100, 1000)
        items = [f"item{random.randint(1, 99)}" for i in range(1, 5)]

        self.client.post(
            "/create_order",
            json={
                "customer_id": customer_id,
                "items": items,
                "total_amount": total_amount,
            },
            timeout=30,
            verify=False,
        )
