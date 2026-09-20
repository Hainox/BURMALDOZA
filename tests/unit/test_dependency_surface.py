def test_required_runtime_imports_are_available() -> None:
    import alembic
    import fastapi
    import hypothesis
    import sqlalchemy

    assert alembic.__version__
    assert fastapi.__version__
    assert hypothesis.__version__
    assert sqlalchemy.__version__
