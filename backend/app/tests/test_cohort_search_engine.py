"""Tests for Cohort Search Engine.

Tests the text chunking function, schema migration for note_embeddings,
and search result formatting.
"""
import duckdb
import pytest
from unittest.mock import patch, MagicMock

from app.services.extraction_schema import init_extraction_tables
from app.services.schema_migration import run_clinical_schema_migration
from app.services.cohort_search_engine import CohortSearchEngine


@pytest.fixture
def duckdb_conn():
    """In-memory DuckDB connection with full schema."""
    conn = duckdb.connect(":memory:")
    init_extraction_tables(conn)
    run_clinical_schema_migration(conn)
    yield conn
    conn.close()


@pytest.fixture
def engine(duckdb_conn):
    """CohortSearchEngine instance with in-memory DuckDB."""
    return CohortSearchEngine(duckdb_conn)


# ---------------------------------------------------------------------------
# Text chunking tests
# ---------------------------------------------------------------------------

class TestChunkText:
    def test_empty_text_returns_empty_list(self, engine):
        assert engine._chunk_text("") == []
        assert engine._chunk_text("   ") == []
        assert engine._chunk_text(None) == []

    def test_short_text_returns_single_chunk(self, engine):
        text = "Patient presents with mild headache."
        chunks = engine._chunk_text(text)
        assert len(chunks) == 1
        assert chunks[0] == text

    def test_text_at_max_tokens_returns_single_chunk(self, engine):
        # ~512 tokens ≈ 384 words (512 * 0.75)
        words = ["word"] * 380
        text = " ".join(words) + "."
        chunks = engine._chunk_text(text, max_tokens=512)
        assert len(chunks) == 1

    def test_long_text_produces_multiple_chunks(self, engine):
        # Create text with many sentences that exceeds 512 tokens
        sentences = [f"This is sentence number {i} with some extra words to fill space." for i in range(100)]
        text = " ".join(sentences)
        chunks = engine._chunk_text(text, max_tokens=512, overlap_tokens=50)
        assert len(chunks) > 1

    def test_chunks_respect_sentence_boundaries(self, engine):
        # Each sentence should not be split mid-sentence
        sentences = [
            "The patient has a history of diabetes.",
            "Blood glucose levels are elevated.",
            "HbA1c is 8.5 percent.",
        ]
        text = " ".join(sentences)
        chunks = engine._chunk_text(text, max_tokens=5000)
        # With a large max_tokens, should be one chunk
        assert len(chunks) == 1
        assert chunks[0] == text

    def test_single_long_sentence_becomes_own_chunk(self, engine):
        # A single sentence longer than max_tokens
        long_sentence = " ".join(["word"] * 600) + "."
        short_sentence = "Short sentence here."
        text = long_sentence + " " + short_sentence
        chunks = engine._chunk_text(text, max_tokens=100)
        # The long sentence should be its own chunk
        assert len(chunks) >= 2
        assert long_sentence in chunks[0]

    def test_chunks_capped_at_50(self, engine):
        # Create enough text to generate more than 50 chunks
        sentences = [f"Sentence {i} with enough words to matter." for i in range(500)]
        text = " ".join(sentences)
        chunks = engine._chunk_text(text, max_tokens=20, overlap_tokens=5)
        assert len(chunks) <= 50

    def test_overlap_between_chunks(self, engine):
        # Create text that will produce multiple chunks
        sentences = [f"Sentence number {i} has some content." for i in range(50)]
        text = " ".join(sentences)
        chunks = engine._chunk_text(text, max_tokens=100, overlap_tokens=30)
        # With overlap, consecutive chunks should share some content
        if len(chunks) >= 2:
            # Check that some words from end of chunk 0 appear in start of chunk 1
            words_end_first = set(chunks[0].split()[-10:])
            words_start_second = set(chunks[1].split()[:10])
            # There should be some overlap
            assert len(words_end_first & words_start_second) > 0


# ---------------------------------------------------------------------------
# Schema tests
# ---------------------------------------------------------------------------

class TestNoteEmbeddingsSchema:
    def test_note_embeddings_table_exists(self, duckdb_conn):
        cols = {
            row[0]
            for row in duckdb_conn.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'note_embeddings'"
            ).fetchall()
        }
        expected = {
            "embedding_id", "note_id", "patient_id", "chunk_text",
            "embedding", "recorded_at", "encounter_id", "created_at",
        }
        assert expected.issubset(cols)

    def test_can_insert_and_query_embeddings(self, duckdb_conn):
        # Insert a test embedding
        embedding = [0.1] * 1536
        duckdb_conn.execute(
            """INSERT INTO note_embeddings
               (embedding_id, note_id, patient_id, chunk_text, embedding)
               VALUES (?, ?, ?, ?, ?::FLOAT[1536])""",
            ["emb1", "note1", "patient1", "test chunk", embedding],
        )

        row = duckdb_conn.execute(
            "SELECT embedding_id, note_id, patient_id, chunk_text FROM note_embeddings"
        ).fetchone()
        assert row[0] == "emb1"
        assert row[1] == "note1"
        assert row[2] == "patient1"
        assert row[3] == "test chunk"


# ---------------------------------------------------------------------------
# Embed note tests (with mocked OpenAI)
# ---------------------------------------------------------------------------

class TestEmbedNote:
    @patch("app.services.cohort_search_engine.CohortSearchEngine._get_embedding")
    def test_embed_note_stores_chunks(self, mock_embed, duckdb_conn):
        mock_embed.return_value = [0.5] * 1536
        engine = CohortSearchEngine(duckdb_conn)

        ids = engine.embed_note(
            note_id="n1",
            content="Short note content.",
            patient_id="p1",
            recorded_at="2024-01-15",
            encounter_id="e1",
        )

        assert len(ids) == 1
        row = duckdb_conn.execute(
            "SELECT note_id, patient_id, chunk_text FROM note_embeddings WHERE embedding_id = ?",
            [ids[0]],
        ).fetchone()
        assert row[0] == "n1"
        assert row[1] == "p1"
        assert "Short note content" in row[2]

    @patch("app.services.cohort_search_engine.CohortSearchEngine._get_embedding")
    def test_embed_note_empty_content_returns_empty(self, mock_embed, duckdb_conn):
        engine = CohortSearchEngine(duckdb_conn)
        ids = engine.embed_note("n1", "", "p1")
        assert ids == []
        mock_embed.assert_not_called()

    @patch("app.services.cohort_search_engine.CohortSearchEngine._get_embedding")
    def test_embed_note_skips_failed_chunks(self, mock_embed, duckdb_conn):
        # First call succeeds, second fails
        mock_embed.side_effect = [
            [0.5] * 1536,
            Exception("API error"),
        ]
        engine = CohortSearchEngine(duckdb_conn)

        # Create text with two chunks
        sentences = [f"Sentence {i} with enough words." for i in range(60)]
        text = " ".join(sentences)

        ids = engine.embed_note("n1", text, "p1")
        # Should have at least one successful embedding
        assert len(ids) >= 1


# ---------------------------------------------------------------------------
# Search tests (with mocked OpenAI)
# ---------------------------------------------------------------------------

class TestSearch:
    @patch("app.services.cohort_search_engine.CohortSearchEngine._get_embedding")
    def test_search_returns_results_above_threshold(self, mock_embed, duckdb_conn):
        # Insert test embeddings directly
        emb = [1.0] + [0.0] * 1535
        duckdb_conn.execute(
            """INSERT INTO note_embeddings
               (embedding_id, note_id, patient_id, chunk_text, embedding)
               VALUES (?, ?, ?, ?, ?::FLOAT[1536])""",
            ["emb1", "note1", "patient1", "GI bleeding on warfarin", emb],
        )

        # Query embedding is the same vector -> similarity = 1.0
        mock_embed.return_value = emb
        engine = CohortSearchEngine(duckdb_conn)

        results = engine.search("GI bleeding", top_k=10, threshold=0.3)
        assert len(results) == 1
        assert results[0]["patient_id"] == "patient1"
        assert results[0]["similarity_score"] >= 0.3

    @patch("app.services.cohort_search_engine.CohortSearchEngine._get_embedding")
    def test_search_empty_query_returns_empty(self, mock_embed, duckdb_conn):
        engine = CohortSearchEngine(duckdb_conn)
        results = engine.search("", top_k=10)
        assert results == []
        mock_embed.assert_not_called()

    @patch("app.services.cohort_search_engine.CohortSearchEngine._get_embedding")
    def test_search_respects_top_k(self, mock_embed, duckdb_conn):
        # Insert multiple embeddings
        emb = [1.0] + [0.0] * 1535
        for i in range(5):
            duckdb_conn.execute(
                """INSERT INTO note_embeddings
                   (embedding_id, note_id, patient_id, chunk_text, embedding)
                   VALUES (?, ?, ?, ?, ?::FLOAT[1536])""",
                [f"emb{i}", f"note{i}", f"patient{i}", f"chunk {i}", emb],
            )

        mock_embed.return_value = emb
        engine = CohortSearchEngine(duckdb_conn)

        results = engine.search("test", top_k=3, threshold=0.0)
        assert len(results) <= 3

    @patch("app.services.cohort_search_engine.CohortSearchEngine._get_embedding")
    def test_search_filters_by_patient_id(self, mock_embed, duckdb_conn):
        emb = [1.0] + [0.0] * 1535
        duckdb_conn.execute(
            """INSERT INTO note_embeddings
               (embedding_id, note_id, patient_id, chunk_text, embedding)
               VALUES (?, ?, ?, ?, ?::FLOAT[1536])""",
            ["emb1", "note1", "patient1", "chunk 1", emb],
        )
        duckdb_conn.execute(
            """INSERT INTO note_embeddings
               (embedding_id, note_id, patient_id, chunk_text, embedding)
               VALUES (?, ?, ?, ?, ?::FLOAT[1536])""",
            ["emb2", "note2", "patient2", "chunk 2", emb],
        )

        mock_embed.return_value = emb
        engine = CohortSearchEngine(duckdb_conn)

        results = engine.search("test", patient_id="patient1", threshold=0.0)
        assert len(results) == 1
        assert results[0]["patient_id"] == "patient1"

    @patch("app.services.cohort_search_engine.CohortSearchEngine._get_embedding")
    def test_search_results_ordered_by_similarity_desc(self, mock_embed, duckdb_conn):
        # Insert embeddings with different similarity to query
        emb_high = [1.0] + [0.0] * 1535
        emb_low = [0.5, 0.5] + [0.0] * 1534

        duckdb_conn.execute(
            """INSERT INTO note_embeddings
               (embedding_id, note_id, patient_id, chunk_text, embedding)
               VALUES (?, ?, ?, ?, ?::FLOAT[1536])""",
            ["emb1", "note1", "p1", "high similarity", emb_high],
        )
        duckdb_conn.execute(
            """INSERT INTO note_embeddings
               (embedding_id, note_id, patient_id, chunk_text, embedding)
               VALUES (?, ?, ?, ?, ?::FLOAT[1536])""",
            ["emb2", "note2", "p2", "lower similarity", emb_low],
        )

        mock_embed.return_value = emb_high
        engine = CohortSearchEngine(duckdb_conn)

        results = engine.search("test", threshold=0.0)
        assert len(results) == 2
        assert results[0]["similarity_score"] >= results[1]["similarity_score"]
