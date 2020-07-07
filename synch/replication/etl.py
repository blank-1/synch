import logging
from typing import Dict

from synch.factory import get_reader, get_writer
from synch.settings import Settings

logger = logging.getLogger("synch.replication.etl")


def etl_full(
    alias: str, schema: str, tables_pk: Dict, renew=False,
):
    """
    full etl
    """
    reader = get_reader(alias)
    source_db_database = Settings.get_source_db_database(alias, schema)
    schema = source_db_database.get("database")
    for table in source_db_database.get("tables"):
        if table.get("auto_full_etl") is False:
            continue
        table_name = table.get("table")
        pk = tables_pk.get(table_name)
        writer = get_writer(table.get("clickhouse_engine"))
        if not pk:
            logger.warning(f"No pk found in {schema}.{table_name}, skip")
            continue
        elif isinstance(pk, tuple):
            pk = f"({','.join(pk)}"
        if renew:
            drop_sql = f"drop table {schema}.{table_name}"
            try:
                writer.execute(drop_sql)
                logger.info(f"drop table success:{schema}.{table_name}")
            except Exception:
                logger.warning(f"Try to drop table {schema}.{table_name} fail")
        if not writer.table_exists(schema, table_name):
            sign_column = table.get("sign_column")
            version_column = table.get("version_column")
            writer.execute(
                writer.get_table_create_sql(
                    reader,
                    schema,
                    table_name,
                    pk,
                    table.get("partition_by"),
                    table.get("engine_settings"),
                    sign_column=sign_column,
                    version_column=version_column,
                )
            )
            if reader.fix_column_type and not table.get("skip_decimal"):
                writer.fix_table_column_type(reader, schema, table_name)
            full_insert_sql = writer.get_full_insert_sql(reader, schema, table_name, sign_column)
            writer.execute(full_insert_sql)
            logger.info(f"full data etl for {schema}.{table_name} success")
        else:
            logger.info(
                f"{schema}.{table_name} exists, skip, or use --renew force etl with drop old tables"
            )
