"""Read-only structural fingerprints for the one-time legacy migration handover."""

import hashlib
import json

from sqlalchemy import text


def structure_fingerprints(connection) -> dict[str, str]:
    # Force stable schema-qualified definitions, independent of each user's search_path.
    old_path = connection.exec_driver_sql("SHOW search_path").scalar_one()
    connection.exec_driver_sql("SET LOCAL search_path = pg_catalog")
    try:
        relations = (
            connection.execute(
                text("""
            SELECT c.oid, n.nspname || '.' || c.relname AS name, c.relkind, c.relpersistence
            FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
            WHERE (n.nspname IN ('knowledge','runtime','qa') OR
                   (n.nspname='dev_meta' AND c.relname='seed_imports'))
              AND c.relkind IN ('r','p','v','m','S','f')
            ORDER BY name
        """)
            )
            .mappings()
            .all()
        )
        result = {}
        for relation in relations:
            oid = {"oid": relation["oid"]}
            columns = (
                connection.execute(
                    text("""
                SELECT a.attname AS name, format_type(a.atttypid,a.atttypmod) AS type,
                       a.attnotnull AS not_null, a.attidentity AS identity,
                       a.attgenerated AS generated, pg_get_expr(d.adbin,d.adrelid) AS default_value
                FROM pg_attribute a LEFT JOIN pg_attrdef d
                  ON d.adrelid=a.attrelid AND d.adnum=a.attnum
                WHERE a.attrelid=:oid AND a.attnum>0 AND NOT a.attisdropped
                ORDER BY a.attnum
            """),
                    oid,
                )
                .mappings()
                .all()
            )
            # PostgreSQL 18 also catalogs NOT NULL as contype='n'. Its semantics
            # remain covered by attnotnull above, as in the frozen PG17 baseline.
            constraints = (
                connection.execute(
                    text("""
                SELECT conname AS name, pg_get_constraintdef(oid, true) AS definition,
                       convalidated AS validated
                FROM pg_constraint
                WHERE conrelid=:oid AND contype <> 'n' ORDER BY conname
            """),
                    oid,
                )
                .mappings()
                .all()
            )
            indexes = (
                connection.execute(
                    text("""
                SELECT pg_get_indexdef(indexrelid) AS definition, indisvalid AS valid
                FROM pg_index WHERE indrelid=:oid ORDER BY definition
            """),
                    oid,
                )
                .mappings()
                .all()
            )
            triggers = (
                connection.execute(
                    text("""
                SELECT tgname AS name, pg_get_triggerdef(oid,true) AS definition,
                       tgenabled AS enabled
                FROM pg_trigger WHERE tgrelid=:oid AND NOT tgisinternal ORDER BY tgname
            """),
                    oid,
                )
                .mappings()
                .all()
            )
            definition = {
                "kind": relation["relkind"],
                "persistence": relation["relpersistence"],
                "columns": [dict(row) for row in columns],
                "constraints": [dict(row) for row in constraints],
                "indexes": [dict(row) for row in indexes],
                "triggers": [dict(row) for row in triggers],
            }
            result[relation["name"]] = digest(definition)
        functions = (
            connection.execute(
                text("""
            SELECT n.nspname || '.' || p.proname || '(' ||
                   pg_get_function_identity_arguments(p.oid) || ')' AS name,
                   pg_get_functiondef(p.oid) AS definition
            FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
            WHERE n.nspname IN ('knowledge','runtime','qa') AND p.prokind IN ('f','p')
            ORDER BY name
        """)
            )
            .mappings()
            .all()
        )
        result.update({"function:" + row["name"]: digest(row["definition"]) for row in functions})
        return result
    finally:
        connection.execute(
            text("SELECT set_config('search_path', :value, true)"), {"value": old_path}
        )


def digest(value) -> str:
    content = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(content.encode()).hexdigest()
