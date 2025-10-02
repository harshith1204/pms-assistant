"""
Chunking Configuration for Qdrant Indexing

This file centralizes chunking parameters to make it easy to tune
chunking behavior for different content types.
"""

# Default chunking settings (current behavior)
DEFAULT_CHUNK_CONFIG = {
    "page": {
        "max_words": 320,
        "overlap_words": 80,
        "min_words_to_chunk": 320,  # Only chunk if longer than this
    },
    "work_item": {
        "max_words": 300,
        "overlap_words": 60,
        "min_words_to_chunk": 300,
    },
    "project": {
        "max_words": 300,
        "overlap_words": 60,
        "min_words_to_chunk": 300,
    },
    "cycle": {
        "max_words": 300,
        "overlap_words": 60,
        "min_words_to_chunk": 300,
    },
    "module": {
        "max_words": 300,
        "overlap_words": 60,
        "min_words_to_chunk": 300,
    },
}

# Aggressive chunking (creates more smaller chunks for better granularity)
AGGRESSIVE_CHUNK_CONFIG = {
    "page": {
        "max_words": 200,
        "overlap_words": 40,
        "min_words_to_chunk": 100,  # Chunk anything > 100 words
    },
    "work_item": {
        "max_words": 150,
        "overlap_words": 30,
        "min_words_to_chunk": 80,   # Chunk anything > 80 words
    },
    "project": {
        "max_words": 150,
        "overlap_words": 30,
        "min_words_to_chunk": 80,
    },
    "cycle": {
        "max_words": 150,
        "overlap_words": 30,
        "min_words_to_chunk": 80,
    },
    "module": {
        "max_words": 150,
        "overlap_words": 30,
        "min_words_to_chunk": 80,
    },
}

# Conservative chunking (only chunks very long documents)
CONSERVATIVE_CHUNK_CONFIG = {
    "page": {
        "max_words": 500,
        "overlap_words": 100,
        "min_words_to_chunk": 500,
    },
    "work_item": {
        "max_words": 400,
        "overlap_words": 80,
        "min_words_to_chunk": 400,
    },
    "project": {
        "max_words": 400,
        "overlap_words": 80,
        "min_words_to_chunk": 400,
    },
    "cycle": {
        "max_words": 400,
        "overlap_words": 80,
        "min_words_to_chunk": 400,
    },
    "module": {
        "max_words": 400,
        "overlap_words": 80,
        "min_words_to_chunk": 400,
    },
}

# Active configuration (change this to switch modes)
ACTIVE_CONFIG = DEFAULT_CHUNK_CONFIG

def get_chunk_config(content_type: str) -> dict:
    """Get chunking configuration for a specific content type.
    
    Args:
        content_type: One of 'page', 'work_item', 'project', 'cycle', 'module'
        
    Returns:
        Dictionary with max_words, overlap_words, min_words_to_chunk
    """
    return ACTIVE_CONFIG.get(content_type, ACTIVE_CONFIG["work_item"])

def chunk_text_configurable(text: str, content_type: str):
    """Chunk text using configuration for the given content type.
    
    Args:
        text: Input text to chunk
        content_type: Type of content (page, work_item, etc.)
        
    Returns:
        List of chunk strings
    """
    if not text:
        return []
    
    config = get_chunk_config(content_type)
    max_words = config["max_words"]
    overlap_words = config["overlap_words"]
    min_words = config.get("min_words_to_chunk", max_words)
    
    words = text.split()
    
    # Don't chunk if below minimum threshold
    if len(words) <= min_words:
        return [text]
    
    chunks = []
    step = max(1, max_words - overlap_words)
    
    for start in range(0, len(words), step):
        end = min(start + max_words, len(words))
        chunk = " ".join(words[start:end]).strip()
        if chunk:
            chunks.append(chunk)
        if end == len(words):
            break
    
    return chunks

# Explanation of configurations:
"""
DEFAULT (Current Behavior):
- Pages: 320 words/chunk, 80 overlap
- Work items: 300 words/chunk, 60 overlap
- Others: 300 words/chunk, 60 overlap
- Result: ~70-80% single-chunk documents (typical PM data)

AGGRESSIVE (More Granular):
- Pages: 200 words/chunk, 40 overlap
- Work items: 150 words/chunk, 30 overlap
- Chunks documents > 80-100 words
- Result: ~40-50% multi-chunk documents
- Use when: You want finer-grained retrieval, have longer descriptions

CONSERVATIVE (Fewer Chunks):
- Pages: 500 words/chunk, 100 overlap
- Work items: 400 words/chunk, 80 overlap
- Only chunks very long documents
- Result: ~90%+ single-chunk documents
- Use when: You want whole-document retrieval, have short content

TO SWITCH MODES:
Change line 78: ACTIVE_CONFIG = AGGRESSIVE_CHUNK_CONFIG
Then re-run: python3 qdrant/insertdocs.py
"""
