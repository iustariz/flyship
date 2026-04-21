from google.cloud import bigquery

PROJECT = "meli-bi-data"
TABLE = "meli-bi-data.SBOX_CX_BI_ADS_CORE.METRICAS_VERTICALES_CX"

_client = None


def get_client() -> bigquery.Client:
    global _client
    if _client is None:
        _client = bigquery.Client(project=PROJECT)
    return _client


def get_schema() -> list[dict]:
    client = get_client()
    table = client.get_table(TABLE)
    return [
        {"name": f.name, "type": f.field_type, "description": f.description or ""}
        for f in table.schema
    ]


def get_verticals() -> list[str]:
    """Return distinct vertical names available in the table."""
    client = get_client()
    # Try common column names for vertical/category
    for col in ["vertical", "verticals", "vertical_name", "categoria", "category", "VERTICAL", "VERTICAL_NAME"]:
        try:
            query = f"SELECT DISTINCT `{col}` FROM `{TABLE}` WHERE `{col}` IS NOT NULL ORDER BY 1 LIMIT 100"
            rows = list(client.query(query).result())
            return [row[0] for row in rows if row[0]]
        except Exception:
            continue

    # Fallback: get schema and find the most likely vertical column
    schema = get_schema()
    string_cols = [f["name"] for f in schema if f["type"] in ("STRING", "VARCHAR")]
    if string_cols:
        col = string_cols[0]
        query = f"SELECT DISTINCT `{col}` FROM `{TABLE}` WHERE `{col}` IS NOT NULL ORDER BY 1 LIMIT 100"
        rows = list(client.query(query).result())
        return [row[0] for row in rows if row[0]]
    return []


def get_vertical_data(vertical: str) -> list[dict]:
    """Return metrics for a specific vertical, ordered by most relevant columns."""
    client = get_client()
    schema = get_schema()
    col_names = [f["name"] for f in schema]

    # Find vertical column
    vertical_col = None
    for candidate in ["vertical", "verticals", "vertical_name", "categoria", "category", "VERTICAL"]:
        if candidate in col_names:
            vertical_col = candidate
            break
    if not vertical_col:
        vertical_col = col_names[0]

    query = f"""
        SELECT *
        FROM `{TABLE}`
        WHERE LOWER(CAST(`{vertical_col}` AS STRING)) = LOWER('{vertical.replace("'", "\\'")}')
        LIMIT 100
    """
    rows = list(client.query(query).result())
    return [dict(row.items()) for row in rows]


def get_all_verticals_summary() -> list[dict]:
    """Return a summary across all verticals for the opportunities overview."""
    client = get_client()
    schema = get_schema()
    col_names = [f["name"] for f in schema]

    vertical_col = None
    for candidate in ["vertical", "verticals", "vertical_name", "categoria", "category", "VERTICAL"]:
        if candidate in col_names:
            vertical_col = candidate
            break
    if not vertical_col:
        return []

    # Find numeric columns that might indicate volume/opportunity
    numeric_cols = [
        f["name"] for f in schema
        if f["type"] in ("INTEGER", "INT64", "FLOAT", "FLOAT64", "NUMERIC", "BIGNUMERIC")
    ][:5]

    agg_parts = ", ".join(
        f"SUM(`{c}`) as sum_{c}, AVG(`{c}`) as avg_{c}" for c in numeric_cols
    ) if numeric_cols else "COUNT(*) as count"

    query = f"""
        SELECT `{vertical_col}` as vertical, COUNT(*) as rows
        {(", " + agg_parts) if numeric_cols else ""}
        FROM `{TABLE}`
        WHERE `{vertical_col}` IS NOT NULL
        GROUP BY 1
        ORDER BY 2 DESC
        LIMIT 50
    """
    rows = list(client.query(query).result())
    return [dict(row.items()) for row in rows]
