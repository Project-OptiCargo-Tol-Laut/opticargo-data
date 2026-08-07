from opticargo_data.db import ColumnInfo, SchemaMismatch, apply_schema_defaults


def col(name, data_type, udt_name, *, nullable=False, default=None, identity=False):
    return ColumnInfo(name, data_type, udt_name, nullable, default, identity)


def test_required_integer_version_defaults_to_one():
    cols = {
        "id": col("id", "uuid", "uuid"),
        "version": col("version", "integer", "int4"),
    }
    row = apply_schema_defaults("voyages", {"id": "abc"}, cols)
    assert row["version"] == 1


def test_existing_version_is_preserved():
    cols = {"version": col("version", "integer", "int4")}
    row = apply_schema_defaults("voyages", {"version": 7}, cols)
    assert row["version"] == 7


def test_unknown_required_business_field_is_not_guessed():
    cols = {"mystery_required": col("mystery_required", "text", "text")}
    row = apply_schema_defaults("voyages", {}, cols)
    assert "mystery_required" not in row


def test_non_integer_version_is_rejected():
    cols = {"version": col("version", "text", "text")}
    try:
        apply_schema_defaults("voyages", {}, cols)
    except SchemaMismatch as exc:
        assert "unsupported type" in str(exc)
    else:
        raise AssertionError("SchemaMismatch expected")
