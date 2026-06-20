from rag_engine.rag_pipeline import index_policy_documents, search_policy


def main():
    print("Indexing policy documents into ChromaDB...")

    index_result = index_policy_documents(reset=True)
    print(index_result)

    question = "What does the company policy say about code of conduct?"
    print(f"\nQuestion: {question}")

    search_result = search_policy(question, top_k=3)

    for index, result in enumerate(search_result["results"], start=1):
        print("\n" + "-" * 80)
        print(f"Result {index}")
        print(
            f"Source: {result['source']} | "
            f"Page: {result['page']} | "
            f"Score: {result['score']}"
        )
        print(result["text"][:800])


if __name__ == "__main__":
    main()
