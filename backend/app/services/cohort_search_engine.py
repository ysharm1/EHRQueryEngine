"""
Cohort Search Engine

Embedding-based semantic search over clinical notes using OpenAI text-embedding-3-small.
Embeddings stored in DuckDB as FLOAT[1536] arrays, with cosine similarity computed in SQL.

Implements Requirements 3.1-3.10
"""
import logging
import re
import time
import uuid
from typing import List, Optional

from openai import OpenAI

from app.config import settings

logger = logging.getLogger(__name__)


class CohortSearchEngine:
    """Embedding-based semantic search over clinical notes."""

    def __init__(self, duckdb_conn):
        self.conn = duckdb_conn
        self._client: Optional[OpenAI] = None

    @property
    def _openai_client(self) -> OpenAI:
        """Lazy-init OpenAI client."""
        if self._client is None:
            self._client = OpenAI(api_key=settings.openai_api_key)
        return self._client

    # -------------------------------------------------------------------------
    # Text chunking
    # -------------------------------------------------------------------------

    def _chunk_text(
        self, text: str, max_tokens: int = 512, overlap_tokens: int = 50
    ) -> List[str]:
        """Split text into overlapping chunks at sentence boundaries.

        Uses a simple word-count approximation: words / 0.75 ≈ tokens.
        This avoids a tiktoken dependency while being close enough for chunking.

        Args:
            text: The text to chunk.
            max_tokens: Maximum tokens per chunk (approximate).
            overlap_tokens: Overlap between consecutive chunks in tokens.

        Returns:
            List of text chunks. Returns [text] if text fits in one chunk,
            or [] if text is empty.
        """
        if not text or not text.strip():
            return []

        text = text.strip()

        # Approximate token count: words / 0.75
        def _approx_tokens(s: str) -> int:
            word_count = len(s.split())
            return int(word_count / 0.75)

        # If the whole text fits in one chunk, return as-is
        if _approx_tokens(text) <= max_tokens:
            return [text]

        # Split into sentences at . ! ? followed by whitespace or end of string
        sentences = re.split(r'(?<=[.!?])\s+', text)
        # Filter out empty sentences
        sentences = [s for s in sentences if s.strip()]

        if not sentences:
            return [text]

        chunks: List[str] = []
        current_sentences: List[str] = []
        current_tokens = 0

        for sentence in sentences:
            sentence_tokens = _approx_tokens(sentence)

            # If a single sentence exceeds max_tokens, add it as its own chunk
            if sentence_tokens > max_tokens:
                # First, flush current buffer if non-empty
                if current_sentences:
                    chunks.append(" ".join(current_sentences))
                    current_sentences = []
                    current_tokens = 0
                chunks.append(sentence)
                continue

            # If adding this sentence would exceed the limit, flush
            if current_tokens + sentence_tokens > max_tokens and current_sentences:
                chunks.append(" ".join(current_sentences))

                # Calculate overlap: keep trailing sentences that fit in overlap_tokens
                overlap_sentences: List[str] = []
                overlap_count = 0
                for s in reversed(current_sentences):
                    s_tokens = _approx_tokens(s)
                    if overlap_count + s_tokens > overlap_tokens:
                        break
                    overlap_sentences.insert(0, s)
                    overlap_count += s_tokens

                current_sentences = overlap_sentences
                current_tokens = overlap_count

            current_sentences.append(sentence)
            current_tokens += sentence_tokens

        # Flush remaining
        if current_sentences:
            chunks.append(" ".join(current_sentences))

        # Cap at 50 chunks per note to prevent runaway
        return chunks[:50]

    # -------------------------------------------------------------------------
    # Embedding generation
    # -------------------------------------------------------------------------

    def _get_embedding(self, text: str) -> List[float]:
        """Call OpenAI text-embedding-3-small API with retry.

        Args:
            text: Text to embed.

        Returns:
            List of 1536 floats representing the embedding.

        Raises:
            Exception: If all retries fail.
        """
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = self._openai_client.embeddings.create(
                    model="text-embedding-3-small",
                    input=text,
                )
                embedding = response.data[0].embedding

                # Validate dimension
                if not isinstance(embedding, list) or len(embedding) != 1536:
                    raise ValueError(
                        f"Expected 1536-dim embedding, got {len(embedding) if isinstance(embedding, list) else type(embedding)}"
                    )

                return embedding
            except Exception as e:
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt  # exponential backoff: 1s, 2s, 4s
                    logger.warning(
                        f"Embedding API attempt {attempt + 1} failed: {e}. "
                        f"Retrying in {wait_time}s..."
                    )
                    time.sleep(wait_time)
                else:
                    logger.error(f"Embedding API failed after {max_retries} attempts: {e}")
                    raise

    # -------------------------------------------------------------------------
    # embed_note
    # -------------------------------------------------------------------------

    def embed_note(
        self,
        note_id: str,
        content: str,
        patient_id: str,
        recorded_at: Optional[str] = None,
        encounter_id: Optional[str] = None,
    ) -> List[str]:
        """Chunk and embed a clinical note, storing results in DuckDB.

        Args:
            note_id: ID of the clinical note.
            content: Full text content of the note.
            patient_id: Patient the note belongs to.
            recorded_at: Timestamp when the note was recorded.
            encounter_id: Associated encounter ID.

        Returns:
            List of embedding_ids created.
        """
        chunks = self._chunk_text(content)
        if not chunks:
            logger.debug(f"No chunks generated for note {note_id} (empty content)")
            return []

        embedding_ids: List[str] = []

        for chunk in chunks:
            try:
                embedding = self._get_embedding(chunk)
            except Exception as e:
                logger.error(
                    f"Failed to embed chunk for note {note_id}: {e}. Skipping."
                )
                continue

            embedding_id = str(uuid.uuid4())
            try:
                self.conn.execute(
                    """INSERT INTO note_embeddings
                       (embedding_id, note_id, patient_id, chunk_text, embedding,
                        recorded_at, encounter_id)
                       VALUES (?, ?, ?, ?, ?::FLOAT[1536], ?::TIMESTAMP, ?)""",
                    [
                        embedding_id,
                        note_id,
                        patient_id,
                        chunk,
                        embedding,
                        recorded_at,
                        encounter_id,
                    ],
                )
                embedding_ids.append(embedding_id)
            except Exception as e:
                logger.error(
                    f"Failed to store embedding for note {note_id}: {e}"
                )

        return embedding_ids

    # -------------------------------------------------------------------------
    # Cosine similarity search
    # -------------------------------------------------------------------------

    def search(
        self,
        query: str,
        top_k: int = 20,
        threshold: float = 0.3,
        patient_id: Optional[str] = None,
    ) -> List[dict]:
        """Embed query and find similar notes via cosine similarity.

        Args:
            query: Natural language search query.
            top_k: Maximum number of results to return.
            threshold: Minimum cosine similarity score.
            patient_id: Optional filter to a specific patient.

        Returns:
            List of dicts with: patient_id, relevant_sentence, note_date,
            similarity_score, note_id, encounter_id.
        """
        if not query or not query.strip():
            return []

        # Embed the query
        query_embedding = self._get_embedding(query.strip())

        # Build SQL with CTE to compute similarity first, then filter
        sql = """
            WITH scored AS (
                SELECT
                    patient_id,
                    chunk_text,
                    recorded_at,
                    note_id,
                    encounter_id,
                    list_cosine_similarity(embedding, ?::FLOAT[1536]) AS similarity
                FROM note_embeddings
            )
            SELECT
                patient_id,
                chunk_text,
                recorded_at,
                note_id,
                encounter_id,
                similarity
            FROM scored
            WHERE similarity >= ?
        """
        params: list = [query_embedding, threshold]

        if patient_id:
            sql += " AND patient_id = ?"
            params.append(patient_id)

        sql += " ORDER BY similarity DESC LIMIT ?"
        params.append(top_k)

        rows = self.conn.execute(sql, params).fetchall()

        results = []
        for row in rows:
            results.append({
                "patient_id": row[0],
                "relevant_sentence": row[1],
                "note_date": row[2].isoformat() if row[2] else None,
                "note_id": row[3],
                "encounter_id": row[4],
                "similarity_score": round(float(row[5]), 4),
            })

        return results

    # -------------------------------------------------------------------------
    # Reindex all
    # -------------------------------------------------------------------------

    def reindex_all(self) -> dict:
        """Regenerate embeddings for all clinical notes.

        Returns:
            Dict with notes_processed, embeddings_created, and errors count.
        """
        # Fetch all clinical notes
        rows = self.conn.execute(
            "SELECT id, patient_id, content, recorded_at, encounter_id FROM clinical_notes"
        ).fetchall()

        # Clear existing embeddings
        self.conn.execute("DELETE FROM note_embeddings")

        notes_processed = 0
        embeddings_created = 0
        errors = 0

        for row in rows:
            note_id = row[0]
            patient_id = row[1]
            content = row[2]
            recorded_at = row[3]
            encounter_id = row[4]

            if not content:
                continue

            notes_processed += 1
            try:
                ids = self.embed_note(
                    note_id=note_id,
                    content=content,
                    patient_id=patient_id,
                    recorded_at=str(recorded_at) if recorded_at else None,
                    encounter_id=encounter_id,
                )
                embeddings_created += len(ids)
            except Exception as e:
                logger.error(f"Error reindexing note {note_id}: {e}")
                errors += 1

        return {
            "notes_processed": notes_processed,
            "embeddings_created": embeddings_created,
            "errors": errors,
        }
