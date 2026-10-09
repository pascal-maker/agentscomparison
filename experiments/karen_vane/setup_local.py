"""Configure only the isolated trial instance, using local Ollama (no secrets)."""

import httpx

from .adapter import Settings


def main():
    settings = Settings.from_env()
    with httpx.Client(base_url=settings.url, timeout=30) as client:
        response = client.get("/api/providers")
        response.raise_for_status()
        providers = response.json()["providers"]
        if not any(p["name"] == settings.provider_name for p in providers):
            response = client.post("/api/providers", json={
                "type": "ollama", "name": settings.provider_name,
                "config": {"baseURL": "http://host.docker.internal:11434"},
            })
            response.raise_for_status()
        response = client.get("/api/providers")
        response.raise_for_status()
        provider = next(p for p in response.json()["providers"] if p["name"] == settings.provider_name)
        for field, selected in (("chatModels", settings.chat_model),
                                ("embeddingModels", settings.embedding_model)):
            if not any(m["key"] == selected for m in provider[field]):
                raise RuntimeError(f"Configured model is unavailable: {selected}")
        response = client.post("/api/config/setup-complete")
        response.raise_for_status()
    print(f"Vane ready at {settings.url}; chat={settings.chat_model}, embeddings={settings.embedding_model}")


if __name__ == "__main__":
    main()
