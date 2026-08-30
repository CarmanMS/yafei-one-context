from one_context.identifiers import is_portable_id


def test_portable_identifiers():
    assert is_portable_id("FunctionCanvas")
    assert is_portable_id("math-research.v1")
    for value in ("", "../escape", "has space", "CON", "name.", "x" * 65):
        assert not is_portable_id(value)
