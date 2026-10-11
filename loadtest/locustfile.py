import random
import string

from locust import HttpUser, between, task


def random_alias(length: int = 8) -> str:
    return "".join(random.choices(string.ascii_letters + string.digits, k=length))


class UrlShortenerUser(HttpUser):
    wait_time = between(0.01, 0.05)

    def on_start(self) -> None:
        self.created_codes: list[str] = []

    @task(1)
    def create_url(self) -> None:
        alias = random_alias()
        with self.client.post(
            "/api/v1/urls",
            json={"long_url": "https://example.com/some/long/path", "custom_alias": alias},
            catch_response=True,
        ) as response:
            if response.status_code == 201:
                self.created_codes.append(response.json()["short_code"])
                response.success()
            elif response.status_code == 429:
                response.success()
            else:
                response.failure(f"create failed {response.status_code}")

    @task(20)
    def redirect(self) -> None:
        if self.created_codes:
            code = random.choice(self.created_codes)
        else:
            code = random_alias()
        with self.client.get(
            f"/{code}", allow_redirects=False, catch_response=True
        ) as response:
            if response.status_code in (302, 404, 410, 429):
                response.success()
            else:
                response.failure(f"redirect failed {response.status_code}")

    @task(2)
    def health(self) -> None:
        self.client.get("/health")
