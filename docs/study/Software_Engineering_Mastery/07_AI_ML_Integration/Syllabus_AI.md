# Phase 7: AI/ML for Software Engineers - Syllabus

You don't need to build models, but you need to know how to use them.

## Module 7.1: LLM Integration Patterns
**Goal:** Build apps that "think".
*   **Prompt Engineering:**
    *   **Zero-Shot vs Few-Shot:** Giving examples.
    *   **Chain of Thought (CoT):** Asking the model to "show its work".
*   **RAG (Retrieval Augmented Generation):**
    *   **Problem:** LLMs hallucinate and have old data.
    *   **Solution:** Fetch relevant data from a DB, paste it into the prompt ("Context"), then ask the question.

## Module 7.2: Vector Databases & Embeddings
**Goal:** Semantic Search ("Find documents about *happy* dogs" matches "Joyful puppy").
*   **Embeddings:** Converting text/images into `float[]` vectors.
*   **Vector Search Algorithms:**
    *   **HNSW (Hierarchical Navigable Small World):** Fast approximate search (Graph-based).
    *   **IVF (Inverted File):** Clustering based.
*   **Distance Metrics:**
    *   **Cosine Similarity:** Angle between vectors (Best for text).
    *   **Euclidean (L2):** Distance between points.
