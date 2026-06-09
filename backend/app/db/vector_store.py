import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
from app.config import CHROMA_DB_DIR, EMBEDDING_MODEL_NAME, NATIONAL_LAWS_COLLECTION, STATE_LAWS_COLLECTION, TOP_K_RESULTS

class VectorStore:
    def __init__(self):
        self.client = chromadb.PersistentClient(path=str(CHROMA_DB_DIR))
        self.embedding_fn = SentenceTransformerEmbeddingFunction(model_name=EMBEDDING_MODEL_NAME)

    def search_national(self, query: str, top_k: int = TOP_K_RESULTS) -> str:
        try:
            collection = self.client.get_collection(name=NATIONAL_LAWS_COLLECTION, embedding_function=self.embedding_fn)
            results = collection.query(query_texts=[query], n_results=top_k)
            return self._format_results(results)
        except Exception as e:
            return f"Error querying national laws: {e}"

    def search_state(self, query: str, state: str, top_k: int = TOP_K_RESULTS) -> str:
        try:
            collection = self.client.get_collection(name=STATE_LAWS_COLLECTION, embedding_function=self.embedding_fn)
            
            # Normalize state name to match metadata (e.g. "Tamil Nadu" -> "tamil_nadu")
            normalized_state = state.lower().replace(" ", "_")
            
            results = collection.query(
                query_texts=[query],
                n_results=top_k,
                where={"state": normalized_state}
            )
            return self._format_results(results)
        except Exception as e:
            return f"Error querying state laws: {e}"

    def _format_results(self, results: dict) -> str:
        if not results.get("documents") or not results["documents"][0]:
            return "No relevant legal information found."

        formatted = []
        for i, doc in enumerate(results["documents"][0]):
            meta = results["metadatas"][0][i]
            act_name = meta.get("act_name", "Unknown Act")
            page = meta.get("page_number", "?")
            formatted.append(f"[Source: {act_name}, Page {page}]\n{doc}")

        return "\n\n---\n\n".join(formatted)

vector_store = VectorStore()
