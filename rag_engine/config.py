from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
POLICY_DOCUMENTS_DIR = PROJECT_ROOT / "policy_documents"
CHROMA_DB_DIR = PROJECT_ROOT / "data" / "chroma"

COLLECTION_NAME = "hr_policy_documents"
# Default embedding model. Can be a sentence-transformers model id (loads locally)
# or a Hugging Face Hub model id (requires HUGGINGFACE_API_KEY and will use the
# Hugging Face Inference API). Recommended: BAAI/bge-base-en-v1.5
EMBEDDING_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

CHUNK_SIZE = 900
CHUNK_OVERLAP = 150
DEFAULT_TOP_K = 5