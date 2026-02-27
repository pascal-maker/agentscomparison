"""Teams module for multi-agent workflows."""


def __getattr__(name: str):
    if name == "discovery_team":
        from teams.discovery_orchestrator import discovery_team
        return discovery_team
    raise AttributeError(f"module 'teams' has no attribute {name!r}")


__all__ = ["discovery_team"]
