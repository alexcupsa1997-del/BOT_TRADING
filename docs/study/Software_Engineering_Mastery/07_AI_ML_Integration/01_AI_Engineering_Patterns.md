# Module 7.1: LLM Integration Patterns

**Date:** 2026-02-06
**Status:** Completed

## 1. RAG (Retrieval Augmented Generation) Architecture

LLMs (GPT-4) are frozen in time. RAG gives them a "Reference Book" (your live data).

### 1.1 The Flow
1.  **Ingest:**
    *   Read PDF/Docs.
    *   **Chunking:** Split text into 512-token chunks (Overlap 50 tokens).
    *   **Embedding:** Send chunks to `text-embedding-3-small`. Get `float[1536]` vector.
    *   **Store:** Save vector + text in Vector DB (Pinecone/Milvus).
2.  **Retrieve:**
    *   User asks: "How do I reset my password?"
    *   Embed query -> Query Vector.
    *   Search Vector DB for *Top-K* nearest vectors.
3.  **Generate:**
    *   Prompt: `Context: {Retrieved Text} 
 Question: {User Query} 
 Answer:`
    *   LLM generates answer based on *Context*.

## 2. Vector Databases Deep Dive

How to find "Nearest Neighbors" in 1 billion vectors?

### 2.1 HNSW (Hierarchical Navigable Small World)
*   **The Structure:** A multi-layered graph (Skip List logic).
*   **Layer 0 (Bottom):** Contains ALL nodes. Dense connections.
*   **Layer N (Top):** Few nodes. Long-range links.
*   **Search Algorithm:**
    1.  Start at Top Layer. Greedy traverse to find closest node to Query.
    2.  Drop down to Layer N-1. Resume search from that point.
    3.  Repeat until Layer 0.
*   **Performance:** $O(\log N)$ search complexity. Much faster than brute force $O(N)$.

### 2.2 Distance Metrics
*   **Cosine Similarity:** Measures the **Angle** between vectors.
    *   *Best for:* Semantic Text Search. (Length of document doesn't affect topic).
    *   *Range:* -1 to 1.
*   **Euclidean Distance (L2):** Measures the **Distance** between points.
    *   *Best for:* Computer Vision, Physical coordinates.
    *   *Warning:* Sensitive to magnitude. If one vector is unnormalized, Euclidean distance fails for semantic search.

## 3. Engineering for AI

### 3.1 Prompt Engineering
*   **Zero-Shot:** "Translate this to Spanish." (No examples).
*   **Few-Shot:** Give 3 examples of (Input, Output) then the actual Input. Drastically improves accuracy.
*   **Chain of Thought (CoT):** "Let's think step by step." Forces the model to generate reasoning tokens *before* the final answer, reducing logic errors.

### 3.2 Evaluation (The "Unit Tests" of AI)
*   **RAGAS:** Framework to evaluate RAG pipelines.
    *   **Faithfulness:** Does the answer match the retrieved context?
    *   **Answer Relevance:** Does the answer match the user query?
