from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
POLICY_DOCUMENTS_DIR = PROJECT_ROOT / "policy_documents"
CHROMA_DB_DIR = PROJECT_ROOT / "data" / "chroma"

COLLECTION_NAME = "hr_policy_documents"
# Default embedding model, loaded locally by sentence-transformers.
# Must match the model the ChromaDB index was built with — changing it changes
# the vector dimension, so re-index afterwards:
#     python -m rag_engine.maintenance
EMBEDDING_MODEL_NAME = "BAAI/bge-base-en-v1.5"

CHUNK_SIZE = 900
CHUNK_OVERLAP = 150
DEFAULT_TOP_K = 5