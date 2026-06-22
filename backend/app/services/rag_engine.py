import os
import re
import json
import math
import httpx
import logging
from sqlalchemy.orm import Session
from app import models

logger = logging.getLogger(__name__)

# --- Pure-Python Cosine Similarity ---
def calculate_cosine_similarity(v1, v2) -> float:
    if not v1 or not v2:
        return 0.0
    # Pad or truncate to align vector lengths
    min_len = min(len(v1), len(v2))
    v1_aligned = v1[:min_len]
    v2_aligned = v2[:min_len]
    
    dot_product = sum(x * y for x, y in zip(v1_aligned, v2_aligned))
    magnitude1 = math.sqrt(sum(x * x for x in v1_aligned))
    magnitude2 = math.sqrt(sum(x * x for x in v2_aligned))
    
    if not magnitude1 or not magnitude2:
        return 0.0
    return dot_product / (magnitude1 * magnitude2)

# --- Offline Keyword Matching Fallback ---
def calculate_keyword_score(query: str, content: str) -> float:
    q_words = set(re.findall(r"\w+", query.lower()))
    c_words = set(re.findall(r"\w+", content.lower()))
    if not q_words:
        return 0.0
        
    stopwords = {
        "the", "a", "an", "and", "or", "but", "if", "then", "of", "to", "in", "is", "for", "with", "have", "has",
        "i", "you", "my", "me", "do", "what", "should", "take", "treat", "how", "can", "about", "for", "on", "at"
    }
    q_filtered = q_words - stopwords
    c_filtered = c_words - stopwords
    
    if not q_filtered:
        overlap = q_words & c_words
        return len(overlap) / len(q_words)
        
    overlap = q_filtered & c_filtered
    return len(overlap) / len(q_filtered)

# --- Fetch Embedding Vector ---
async def fetch_query_embedding(text: str, hf_key: str, gemini_key: str) -> list[float]:
    embedding = []
    
    # 1. Try Gemini Embedding API (768 dimensions)
    has_gemini = gemini_key and not gemini_key.startswith("your_")
    if has_gemini:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/text-embedding-004:embedContent?key={gemini_key}"
            async with httpx.AsyncClient() as client:
                res = await client.post(
                    url,
                    json={
                        "model": "models/text-embedding-004",
                        "content": {"parts": [{"text": text}]}
                    },
                    timeout=5.0
                )
                if res.status_code == 200:
                    embedding = res.json().get("embedding", {}).get("values", [])
                    if embedding:
                        return embedding
        except Exception as e:
            logger.error(f"Gemini embedding API error: {e}")

    # 2. Try Hugging Face Inference API (384 dimensions)
    has_hf = hf_key and not hf_key.startswith("your_")
    if has_hf:
        try:
            url = "https://api-inference.huggingface.co/models/sentence-transformers/all-MiniLM-L6-v2"
            headers = {"Authorization": f"Bearer {hf_key}", "Content-Type": "application/json"}
            async with httpx.AsyncClient() as client:
                res = await client.post(url, headers=headers, json={"inputs": text}, timeout=5.0)
                if res.status_code == 200:
                    result = res.json()
                    if isinstance(result, list) and len(result) > 0 and isinstance(result[0], float):
                        return result
                    elif isinstance(result, list) and len(result) > 0 and isinstance(result[0], list):
                        return result[0]
        except Exception as e:
            logger.error(f"Hugging Face embedding API error: {e}")
            
    return []

# --- Semantic Retrieval ---
async def retrieve_clinical_guidelines(
    db: Session,
    query: str,
    hf_key: str = "",
    gemini_key: str = "",
    limit: int = 3
) -> list:
    try:
        guidelines = db.query(models.ClinicalGuideline).all()
        if not guidelines:
            return []
            
        # Get query vector
        query_vector = await fetch_query_embedding(query, hf_key, gemini_key)
        
        matches = []
        if query_vector:
            # We have a query vector, compute cosine similarity
            for g in guidelines:
                try:
                    g_vector = json.loads(g.embedding_json)
                    score = calculate_cosine_similarity(query_vector, g_vector)
                    matches.append((g, score))
                except Exception as parse_err:
                    logger.error(f"Failed to parse guideline embedding {g.id}: {parse_err}")
                    matches.append((g, 0.0))
        else:
            # Fallback: compute keyword similarity offline
            logger.info("RAG: Embedding vector empty/offline, falling back to keyword overlaps.")
            for g in guidelines:
                score = calculate_keyword_score(query, g.content + " " + g.title)
                matches.append((g, score))
                
        # Sort by similarity score descending
        matches.sort(key=lambda x: x[1], reverse=True)
        
        # Take the top matches above a positive threshold (e.g. score > 0.05)
        top_matches = []
        for g, score in matches[:limit]:
            if score > 0.05:
                top_matches.append(g)
                
        return top_matches
    except Exception as e:
        logger.error(f"Error retrieving clinical guidelines: {e}")
        return []
