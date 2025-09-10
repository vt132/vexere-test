# Central config for LLM service
from pathlib import Path

BASE_URL = "http://localhost:1234/v1"
LLM_MODEL = "qwen/qwen3-4b"
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

# Path to FAQ CSV (RAG data), this can change if needed
FAQ_DATA_PATH = Path(__file__).parent / "faq_data.csv"
 
# External services
DATA_SERVICE_URL = "http://localhost:8002"
HTTP_TIMEOUT_SECONDS = 15.0
