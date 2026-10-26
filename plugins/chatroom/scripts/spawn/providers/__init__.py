"""The providers of the spawn mode: catalog.py says who they are (free tiers, links, key probes), openai_compat.py talks
to them (one adapter, every provider is OpenAI-compatible), recovery.py finishes an answer (a broken stream resumed, broken
tool JSON repaired). The roles call complete(); the catalog calls list_models()."""
from spawn.providers.openai_compat import chat, list_models  # noqa: F401
from spawn.providers.recovery import complete  # noqa: F401
