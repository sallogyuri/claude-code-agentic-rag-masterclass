from services.chunking_service import chunk_text


def test_empty_string_returns_empty_list():
    assert chunk_text("") == []


def test_short_text_produces_single_chunk():
    text = "Hello world"
    chunks = chunk_text(text)
    assert len(chunks) == 1
    assert chunks[0] == "Hello world"


def test_long_text_produces_multiple_chunks():
    # 2500 chars, chunk_size=1000, overlap=200 → stride=800
    # starts: 0, 800, 1600, 2400 → 4 chunks
    text = "x" * 2500
    chunks = chunk_text(text)
    assert len(chunks) == 4


def test_each_chunk_respects_chunk_size():
    text = "x" * 3000
    chunks = chunk_text(text)
    assert all(len(c) <= 1000 for c in chunks)


def test_overlap_carries_content_from_previous_chunk():
    # First 1000 chars are 'a', next 1000 are 'b'
    text = "a" * 1000 + "b" * 1000
    chunks = chunk_text(text)
    # chunk[1] starts at offset 800, so first 200 chars must be 'a'
    assert chunks[1][:200] == "a" * 200


def test_custom_chunk_size_and_overlap():
    text = "x" * 100
    chunks = chunk_text(text, chunk_size=30, overlap=5)
    # stride = 25: starts at 0, 25, 50, 75 → 4 chunks
    assert len(chunks) == 4
    assert chunks[0] == "x" * 30
    assert chunks[-1] == "x" * 25  # text[75:105] clipped to text[75:100]
