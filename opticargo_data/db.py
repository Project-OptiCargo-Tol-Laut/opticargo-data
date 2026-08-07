from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from .config import database_url


class SchemaMismatch(RuntimeError):
    pass


@dataclass
class ColumnInfo:
    name: str
    data_type: str
    udt_name: str
    nullable: bool
    default: str | None
    identity: bool


@dataclass
class UpsertStats:
    processed: int
    materialized_ids: int
    unique_aliases: int
    id_map: dict[str, str]


ALIASES = {
    "users": {
        "account_status": ["account_status", "status"],
        "password_hash": ["password_hash", "hashed_password", "password_digest"],
    },
    "cargo_capacities": {
        "cargo_type_allowed": ["cargo_type_allowed", "cargo_types_allowed", "allowed_cargo_types"],
        "temperature_range": ["temperature_range", "temperature"],
    },
}


# Required columns that are part of the Gateway persistence model but are
# intentionally not duplicated in static dataset JSON.  Defaults are deliberately
# narrow: only well-defined persistence metadata may be synthesized here.
# Business/domain fields must still be supplied by the dataset contract.
SEED_TIMESTAMP = datetime(2026, 7, 1, tzinfo=timezone.utc)
INTEGER_TYPES = {"smallint", "integer", "bigint"}
INTEGER_UDT_TYPES = {"int2", "int4", "int8"}


def apply_schema_defaults(
    table: str, projected: dict[str, Any], cols: dict[str, ColumnInfo]
) -> dict[str, Any]:
    """Fill safe persistence metadata required by the live Gateway schema.

    `version` is the optimistic-lock/version counter used by current Gateway
    tables such as `voyages`; a freshly seeded row starts at version 1.
    Required audit timestamps without DB defaults use a fixed UTC timestamp so
    the competition seed remains reproducible.  No business field is guessed.
    """

    out = dict(projected)
    for name, info in cols.items():
        if name in out or info.nullable or info.default is not None or info.identity:
            continue
        if name == "version":
            if info.data_type in INTEGER_TYPES or info.udt_name in INTEGER_UDT_TYPES:
                out[name] = 1
                continue
            raise SchemaMismatch(
                f"public.{table}.version is required but has unsupported type "
                f"{info.data_type}/{info.udt_name}; refusing to guess a value"
            )
        if name in {"created_at", "updated_at"} and (
            "timestamp" in info.data_type or info.udt_name in {"timestamp", "timestamptz"}
        ):
            out[name] = SEED_TIMESTAMP
    return out


def connect():
    import psycopg

    return psycopg.connect(database_url())


def table_columns(conn, table: str) -> dict[str, ColumnInfo]:
    sql = """
    SELECT column_name, data_type, udt_name, is_nullable, column_default, is_identity
      FROM information_schema.columns
     WHERE table_schema='public' AND table_name=%s
     ORDER BY ordinal_position
    """
    with conn.cursor() as cur:
        cur.execute(sql, (table,))
        rows = cur.fetchall()
    if not rows:
        raise SchemaMismatch(f"Required table public.{table} not found. Run Gateway migrations first.")
    return {
        r[0]: ColumnInfo(r[0], r[1], r[2], r[3] == "YES", r[4], r[5] == "YES")
        for r in rows
    }


def primary_key(conn, table: str) -> list[str]:
    q = """
    SELECT a.attname
      FROM pg_index i
      JOIN LATERAL unnest(i.indkey) WITH ORDINALITY AS k(attnum, ord) ON true
      JOIN pg_attribute a ON a.attrelid=i.indrelid AND a.attnum=k.attnum
     WHERE i.indrelid=%s::regclass AND i.indisprimary
     ORDER BY k.ord
    """
    with conn.cursor() as cur:
        cur.execute(q, (f"public.{table}",))
        return [r[0] for r in cur.fetchall()]


def unique_keys(conn, table: str) -> list[list[str]]:
    """Return simple (non-expression) unique keys, excluding the primary key."""

    q = """
    SELECT array_agg(a.attname ORDER BY k.ord) AS columns
      FROM pg_index i
      JOIN LATERAL unnest(i.indkey) WITH ORDINALITY AS k(attnum, ord) ON true
      JOIN pg_attribute a ON a.attrelid=i.indrelid AND a.attnum=k.attnum
     WHERE i.indrelid=%s::regclass
       AND i.indisunique
       AND NOT i.indisprimary
       AND i.indexprs IS NULL
       AND k.attnum > 0
     GROUP BY i.indexrelid
     ORDER BY i.indexrelid::regclass::text
    """
    with conn.cursor() as cur:
        cur.execute(q, (f"public.{table}",))
        return [list(r[0]) for r in cur.fetchall() if r[0]]


def foreign_keys(conn, table: str) -> dict[str, tuple[str, str]]:
    """Return single-column FK mappings: local_col -> (foreign_table, foreign_col)."""

    q = """
    SELECT la.attname AS local_column,
           ft.relname AS foreign_table,
           fa.attname AS foreign_column
      FROM pg_constraint c
      JOIN pg_class lt ON lt.oid = c.conrelid
      JOIN pg_namespace n ON n.oid = lt.relnamespace
      JOIN pg_class ft ON ft.oid = c.confrelid
      JOIN LATERAL unnest(c.conkey) WITH ORDINALITY lk(attnum, ord) ON true
      JOIN LATERAL unnest(c.confkey) WITH ORDINALITY fk(attnum, ord) ON fk.ord = lk.ord
      JOIN pg_attribute la ON la.attrelid = c.conrelid AND la.attnum = lk.attnum
      JOIN pg_attribute fa ON fa.attrelid = c.confrelid AND fa.attnum = fk.attnum
     WHERE c.contype = 'f'
       AND n.nspname = 'public'
       AND lt.relname = %s
       AND cardinality(c.conkey) = 1
    """
    with conn.cursor() as cur:
        cur.execute(q, (table,))
        return {r[0]: (r[1], r[2]) for r in cur.fetchall()}


def _candidate_column(table: str, key: str, cols: dict[str, ColumnInfo]) -> str | None:
    candidates = ALIASES.get(table, {}).get(key, [key])
    for name in candidates:
        if name in cols:
            return name
    return key if key in cols else None


def project_row(table: str, row: dict[str, Any], cols: dict[str, ColumnInfo]) -> dict[str, Any]:
    out = {}
    for key, val in row.items():
        col = _candidate_column(table, key, cols)
        if col:
            out[col] = val
    return out


def _adapt(value: Any, info: ColumnInfo):
    if value is None:
        return None
    if info.data_type in {"json", "jsonb"}:
        from psycopg.types.json import Jsonb

        return Jsonb(value)
    if info.data_type == "ARRAY":
        return value
    if isinstance(value, (dict, list)):
        import json

        return json.dumps(value, ensure_ascii=False)
    return value


def validate_required_columns(table: str, projected: dict[str, Any], cols: dict[str, ColumnInfo]):
    missing = []
    for name, info in cols.items():
        if name in projected:
            continue
        if info.nullable or info.default is not None or info.identity:
            continue
        missing.append(name)
    if missing:
        raise SchemaMismatch(
            f"public.{table} has required columns not covered by the data contract: {missing}. "
            "Use the Gateway OpenAPI/migration as source of truth and add a mapping before seeding."
        )


def _where_key_sql(sql, columns: list[str]):
    return sql.SQL(" AND ").join(
        sql.SQL("{} = {}").format(sql.Identifier(column), sql.Placeholder())
        for column in columns
    )


def _find_existing_pk(cur, table: str, row: dict[str, Any], pk: list[str], unique: list[list[str]]):
    from psycopg import sql

    candidates: list[tuple[str, list[str]]] = []
    if pk and all(c in row and row[c] is not None for c in pk):
        candidates.append(("primary", pk))
    for key in unique:
        # PostgreSQL UNIQUE normally allows multiple NULLs; skip NULL-bearing keys.
        if key and all(c in row and row[c] is not None for c in key):
            candidates.append(("unique", key))

    for kind, key in candidates:
        q = sql.SQL("SELECT {} FROM {} WHERE {} LIMIT 1").format(
            sql.SQL(",").join(map(sql.Identifier, pk)),
            sql.Identifier(table),
            _where_key_sql(sql, key),
        )
        cur.execute(q, [row[c] for c in key])
        found = cur.fetchone()
        if found:
            return kind, key, tuple(found)
    return None


def _update_existing(cur, table: str, row: dict[str, Any], pk: list[str], existing_pk: tuple[Any, ...]):
    from psycopg import sql

    update = [name for name in row if name not in pk]
    if not update:
        return
    q = sql.SQL("UPDATE {} SET {} WHERE {}").format(
        sql.Identifier(table),
        sql.SQL(",").join(
            sql.SQL("{}={}").format(sql.Identifier(name), sql.Placeholder())
            for name in update
        ),
        _where_key_sql(sql, pk),
    )
    cur.execute(q, [row[name] for name in update] + list(existing_pk))


def _remap_foreign_keys(
    row: dict[str, Any],
    fks: dict[str, tuple[str, str]],
    id_maps: dict[str, dict[str, str]],
):
    for local_col, (foreign_table, foreign_col) in fks.items():
        if foreign_col != "id" or local_col not in row or row[local_col] is None:
            continue
        mapping = id_maps.get(foreign_table, {})
        value = str(row[local_col])
        if value in mapping:
            row[local_col] = mapping[value]


def upsert_rows(
    conn,
    table: str,
    rows: list[dict[str, Any]],
    *,
    idempotent: bool = True,
    id_maps: dict[str, dict[str, str]] | None = None,
) -> UpsertStats:
    """Schema-aware deterministic upsert with business-unique alias support.

    When a seed row's primary id differs from a row already identified by a
    database UNIQUE key, the database id is kept and an alias is returned.  That
    alias is then used to remap downstream foreign keys.  This is what makes the
    seed compatible with schemas such as routes where the source dataset can
    contain multiple curated variants but the Gateway permits one row per
    origin/destination/type.
    """

    from psycopg import sql

    cols = table_columns(conn, table)
    pk = primary_key(conn, table)
    unique = unique_keys(conn, table)
    fks = foreign_keys(conn, table)
    if not pk and idempotent:
        raise SchemaMismatch(f"public.{table} has no primary key; cannot guarantee idempotent seed")

    id_maps = id_maps or {}
    result_map: dict[str, str] = {}
    aliases = 0
    materialized: set[str] = set()

    with conn.cursor() as cur:
        for raw in rows:
            row = project_row(table, raw, cols)
            _remap_foreign_keys(row, fks, id_maps)
            row = apply_schema_defaults(table, row, cols)
            validate_required_columns(table, row, cols)
            row = {name: _adapt(value, cols[name]) for name, value in row.items()}

            raw_pk = str(raw.get("id")) if raw.get("id") is not None else None

            if idempotent:
                found = _find_existing_pk(cur, table, row, pk, unique)
                if found:
                    kind, _key, existing_pk = found
                    # Keep the DB's canonical PK. Updating the PK itself would
                    # break existing references and defeat idempotency.
                    _update_existing(cur, table, row, pk, existing_pk)
                    if len(pk) == 1 and raw_pk is not None:
                        db_id = str(existing_pk[0])
                        result_map[raw_pk] = db_id
                        materialized.add(db_id)
                        if kind == "unique" and db_id != raw_pk:
                            aliases += 1
                    continue

            names = list(row)
            values = [row[name] for name in names]
            q = sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
                sql.Identifier(table),
                sql.SQL(",").join(map(sql.Identifier, names)),
                sql.SQL(",").join([sql.Placeholder() for _ in names]),
            )
            # The preflight lookup handles all known unique keys.  A target-less
            # DO NOTHING is a final safety net for a concurrent/conflicting row;
            # deterministic one-off seed jobs normally never take this branch.
            if idempotent:
                q += sql.SQL(" ON CONFLICT DO NOTHING")
            cur.execute(q, values)

            if len(pk) == 1 and raw_pk is not None:
                # Re-query so a concurrent ON CONFLICT DO NOTHING still resolves
                # to the canonical database id.
                found = _find_existing_pk(cur, table, row, pk, unique)
                if not found:
                    raise SchemaMismatch(f"{table}: inserted row could not be resolved by primary/unique key")
                _kind, _key, existing_pk = found
                db_id = str(existing_pk[0])
                result_map[raw_pk] = db_id
                materialized.add(db_id)
                if db_id != raw_pk:
                    aliases += 1

    return UpsertStats(
        processed=len(rows),
        materialized_ids=len(materialized) if result_map else len(rows),
        unique_aliases=aliases,
        id_map=result_map,
    )


def schema_report(conn, tables: list[str]) -> str:
    lines = []
    for table in tables:
        cols = table_columns(conn, table)
        pk = primary_key(conn, table)
        unique = unique_keys(conn, table)
        fks = foreign_keys(conn, table)
        lines.append(f"[{table}] pk={pk} unique={unique} fks={fks}")
        for c in cols.values():
            lines.append(
                f"  {c.name}: {c.data_type}/{c.udt_name} nullable={c.nullable} default={c.default!r}"
            )
    return "\n".join(lines)
