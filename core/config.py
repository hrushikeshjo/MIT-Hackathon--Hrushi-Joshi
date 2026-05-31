import os
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
MODEL = "claude-sonnet-4-20250514"
MAX_TOKENS = 1000
MAX_RETRIES = 2
AGENT_TIMEOUT_SECONDS = 30
CONFIDENCE_THRESHOLD = 0.6
ENABLE_CRITIC_LOOP = True
