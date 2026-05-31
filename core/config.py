import os
try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv() -> None:
        return None

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
RUN_MODE = os.getenv("DISASTER_MAS_MODE", "auto").lower()  # auto | local | llm
MODEL = "claude-sonnet-4-20250514"
MAX_TOKENS = 1000
MAX_RETRIES = 2
AGENT_TIMEOUT_SECONDS = 30
CONFIDENCE_THRESHOLD = 0.6
ENABLE_CRITIC_LOOP = True
ENABLE_OFFICIAL_WEB_DATA = os.getenv("ENABLE_OFFICIAL_WEB_DATA", "true").lower() != "false"
ENABLE_WEB_SEARCH = os.getenv("ENABLE_WEB_SEARCH", "false").lower() == "true"
WEB_TIMEOUT_SECONDS = float(os.getenv("WEB_TIMEOUT_SECONDS", "3"))
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")


def should_use_llm() -> bool:
    if RUN_MODE == "local":
        return False
    if RUN_MODE == "llm":
        return bool(ANTHROPIC_API_KEY)
    return bool(ANTHROPIC_API_KEY)
