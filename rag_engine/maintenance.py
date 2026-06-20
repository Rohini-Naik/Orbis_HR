from rag_engine.rag_pipeline import index_policy_documents


def main(reset: bool = True) -> dict:
    """Simple maintenance CLI to (re)index policy documents."""
    print("Starting indexing... (reset=%s)" % reset)
    result = index_policy_documents(reset=reset)
    print("Indexing finished:", result)
    return result


if __name__ == "__main__":
    main(reset=True)
