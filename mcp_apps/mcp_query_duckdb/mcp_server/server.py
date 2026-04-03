import json
import logging
import os
import random
import sqlite3
import asyncio
import aiosqlite
import time
from enum import StrEnum, auto
from typing import Any, Literal
import datetime

import pandas as pd
from mcp.server.fastmcp import Context
from mcp.server.fastmcp import FastMCP
from pydantic import Field, BaseModel
from starlette.requests import Request

from mcp_server.config import AppConfig

logger = logging.getLogger()
logger.setLevel(logging.INFO)

config = AppConfig()
config_file = os.environ.get("CONFIG_FILE")
config.ensure_initialized(config_file or './mcp_server.conf')

# Initialize FastMCP server for Query tools
mcp = FastMCP(
    name="Example MCP Server",
    host=config.config.get_string("app.http.server.bind.address"),
    port=config.config.get_int("app.http.server.port"),
)

class UserInfo(BaseModel):
    sub: str|None
    authorization: str|None
    user_dn: str|None
    email: str|None

def get_user_info(context: Context) -> UserInfo:
    """
    A function that gives the headers for the request.
    """
    request_object = context.request_context.request
    headers: dict[str, str] = request_object.headers

    # TODO filter headers for what is needed, i.e. x-api-key, x-user-id, etc.
    return UserInfo(
        sub=headers.get("x-user-sub", None),
        authorization=headers.get("authorization", None),
        user_dn=headers.get("x-user-dn", None),
        email=headers.get("x-user-email", None)
    )


@mcp.tool(description="Retrieves the full database schema including all tables, columns, data types, and constraints. Use this tool before querying if you are unsure about table names, column names, or data types.")
async def get_database_schema(
        context: Context[Any, Any, Request] = None
) -> dict:
    """
    Retrieves the full schema of the DuckDB database, including all tables, their columns,
    data types, nullable flags, default values, and primary/foreign key constraints.

    :param context: **(Injected by FastMCP)** The execution context object
    :type context: Context[Any, Any, Request]
    :return: A dictionary containing the database schema.
    :rtype: dict
    """
    user_info = get_user_info(context)
    logger.info(f"Running get_database_schema tool on behalf of user: {user_info.sub} with email: {user_info.email}")

    DB_PATH = config.config.get_string("app.sqlite_db.file.path", "../data/demo.duckdb")
    is_duckdb = DB_PATH.endswith('.duckdb')

    try:
        if is_duckdb:
            import duckdb
            from concurrent.futures import ThreadPoolExecutor

            def fetch_schema():
                with duckdb.connect(DB_PATH) as conn:
                    # Get all tables
                    tables = conn.execute(
                        "SELECT table_schema, table_name FROM information_schema.tables "
                        "WHERE table_schema NOT IN ('information_schema', 'pg_catalog') "
                        "ORDER BY table_schema, table_name"
                    ).fetchall()

                    schema = {}
                    for table_schema, table_name in tables:
                        qualified_name = f"{table_schema}.{table_name}" if table_schema != "main" else table_name

                        # Get columns
                        columns = conn.execute(
                            "SELECT column_name, data_type, is_nullable, column_default "
                            "FROM information_schema.columns "
                            "WHERE table_schema = ? AND table_name = ? "
                            "ORDER BY ordinal_position",
                            [table_schema, table_name]
                        ).fetchall()

                        col_info = [
                            {
                                "name": col[0],
                                "type": col[1],
                                "nullable": col[2] == "YES",
                                "default": col[3],
                            }
                            for col in columns
                        ]

                        # Get primary key constraints
                        try:
                            pk_result = conn.execute(
                                "SELECT constraint_column_names FROM duckdb_constraints() "
                                "WHERE table_name = ? AND constraint_type = 'PRIMARY KEY'",
                                [table_name]
                            ).fetchall()
                            primary_keys = [str(row[0]) for row in pk_result] if pk_result else []
                        except Exception:
                            primary_keys = []

                        # Get row count estimate
                        try:
                            count = conn.execute(
                                f'SELECT COUNT(*) FROM "{table_schema}"."{table_name}"'
                            ).fetchone()[0]
                        except Exception:
                            count = None

                        schema[qualified_name] = {
                            "columns": col_info,
                            "primary_keys": primary_keys,
                            "row_count": count,
                        }

                    return schema

            loop = asyncio.get_event_loop()
            with ThreadPoolExecutor() as executor:
                schema = await loop.run_in_executor(executor, fetch_schema)

            return {
                "status": f"Schema retrieved successfully. Found {len(schema)} table(s).",
                "database_type": "DuckDB",
                "schema": schema,
            }

        else:
            # SQLite fallback
            async with aiosqlite.connect(DB_PATH) as conn:
                tables_cursor = await conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
                )
                tables = await tables_cursor.fetchall()

                schema = {}
                for (table_name,) in tables:
                    pragma_cursor = await conn.execute(f'PRAGMA table_info("{table_name}")')
                    columns = await pragma_cursor.fetchall()

                    col_info = [
                        {
                            "name": col[1],
                            "type": col[2],
                            "nullable": col[3] == 0,
                            "default": col[4],
                            "primary_key": col[5] == 1,
                        }
                        for col in columns
                    ]

                    count_cursor = await conn.execute(f'SELECT COUNT(*) FROM "{table_name}"')
                    count = (await count_cursor.fetchone())[0]

                    schema[table_name] = {
                        "columns": col_info,
                        "row_count": count,
                    }

            return {
                "status": f"Schema retrieved successfully. Found {len(schema)} table(s).",
                "database_type": "SQLite",
                "schema": schema,
            }

    except Exception as e:
        return {"error": f"Error retrieving database schema: {str(e)}"}


@mcp.tool(description="Executes a DuckDB query against the database with enhanced error handling and performance optimization. IMPORTANT: If you are unsure about the database schema (table names, column names, or data types), call the 'get_database_schema' tool first to retrieve the full schema before constructing your query.")
async def execute_sqlite_query(
        query: str,
        context: Context[Any, Any, Request] = None
) -> dict:
    """
    Executes a DuckDB query against the database with timeout support and DuckDB-specific optimizations.

    IMPORTANT: If you do not know the database schema (table names, column names, or column types),
    call the 'get_database_schema' tool first before writing your query. This avoids errors from
    guessing table or column names.

    :param query: The DuckDB query string to execute.
    :type query: str
    :param context: **(Injected by FastMCP)** The execution context object
    :type context: Context[Any, Any, Request]
    :return: A dictionary containing the results of the query execution.
    :rtype: dict
    """
    user_info = get_user_info(context)
    logger.info(f"Running DuckDB query tool on behalf of user: {user_info.sub} with email: {user_info.email}")

    # Support both SQLite (legacy) and DuckDB paths
    DB_PATH = config.config.get_string("app.sqlite_db.file.path", "../data/demo.duckdb")
    QUERY_TIMEOUT = config.config.get_int("app.sqlite_db.query_timeout_seconds", 60)  # Increased for DuckDB
    
    # Check if it's a DuckDB file
    is_duckdb = DB_PATH.endswith('.duckdb')
    
    async def async_execute_query():
        try:
            if is_duckdb:
                # Use DuckDB for .duckdb files
                import duckdb
                # DuckDB doesn't have async support, so we run in executor
                import asyncio
                from concurrent.futures import ThreadPoolExecutor
                
                def execute_duckdb_query():
                    with duckdb.connect(DB_PATH) as conn:
                        # Enable progress bar for long-running queries
                        conn.execute("SET enable_progress_bar=true")
                        
                        # Execute query and get results
                        result = conn.execute(query)
                        columns = [desc[0] for desc in result.description] if result.description else []
                        rows = result.fetchall()
                        
                        if rows:
                            df = pd.DataFrame(rows, columns=columns)
                            # Handle DuckDB-specific data types better
                            data = json.loads(df.to_json(date_format='iso', default_handler=str))
                            
                            # Add query performance info
                            row_count = len(df)
                            col_count = len(df.columns)
                            
                            # Check context window limits
                            data_json_str = json.dumps(data)
                            context_size = len(data_json_str)
                            
                            # Configurable context limit (default ~100KB which is roughly 25k tokens)
                            MAX_CONTEXT_SIZE = config.config.get_int("app.sqlite_db.max_context_size", 100000)
                            
                            if context_size > MAX_CONTEXT_SIZE:
                                return {
                                    "status": f"DuckDB query executed successfully. Too many rows returned which will exceed the context window limit set ({MAX_CONTEXT_SIZE:,} characters). Consider adding LIMIT clause or more specific WHERE conditions.",
                                    "data": None,
                                    "metadata": {
                                        "row_count": row_count,
                                        "column_count": col_count,
                                        "columns": columns,
                                        "database_type": "DuckDB",
                                        "context_size": context_size,
                                        "context_limit": MAX_CONTEXT_SIZE,
                                        "exceeded_limit": True
                                    }
                                }
                            
                            return {
                                "status": f"DuckDB query executed successfully. {row_count} rows, {col_count} columns returned.",
                                "data": data,
                                "metadata": {
                                    "row_count": row_count,
                                    "column_count": col_count,
                                    "columns": columns,
                                    "database_type": "DuckDB",
                                    "context_size": context_size,
                                    "context_limit": MAX_CONTEXT_SIZE,
                                    "exceeded_limit": False
                                }
                            }
                        else:
                            return {
                                "status": "DuckDB query executed successfully. No rows returned.",
                                "data": None,
                                "metadata": {
                                    "row_count": 0,
                                    "column_count": 0,
                                    "columns": [],
                                    "database_type": "DuckDB"
                                }
                            }
                
                # Run in thread pool to avoid blocking
                loop = asyncio.get_event_loop()
                with ThreadPoolExecutor() as executor:
                    result = await loop.run_in_executor(executor, execute_duckdb_query)
                    return result
                    
            else:
                # Fallback to SQLite for .db files
                async with aiosqlite.connect(DB_PATH) as conn:
                    async with conn.execute(query) as cursor:
                        columns = [col[0] for col in cursor.description] if cursor.description else []
                        rows = await cursor.fetchall()
                        if rows:
                            df = pd.DataFrame(rows, columns=columns)
                            data = json.loads(df.to_json())
                            
                            # Check context window limits
                            data_json_str = json.dumps(data)
                            context_size = len(data_json_str)
                            
                            # Configurable context limit (default ~100KB which is roughly 25k tokens)
                            MAX_CONTEXT_SIZE = config.config.get_int("app.sqlite_db.max_context_size", 100000)
                            
                            if context_size > MAX_CONTEXT_SIZE:
                                return {
                                    "status": f"SQLite query executed successfully. Too many rows returned which will exceed the context window limit set ({MAX_CONTEXT_SIZE:,} characters). Consider adding LIMIT clause or more specific WHERE conditions.",
                                    "data": None,
                                    "metadata": {
                                        "row_count": len(df),
                                        "column_count": len(df.columns),
                                        "columns": columns,
                                        "database_type": "SQLite",
                                        "context_size": context_size,
                                        "context_limit": MAX_CONTEXT_SIZE,
                                        "exceeded_limit": True
                                    }
                                }
                            
                            return {
                                "status": f"SQLite query executed successfully. {len(df)} rows returned.",
                                "data": data,
                                "metadata": {
                                    "row_count": len(df),
                                    "column_count": len(df.columns),
                                    "columns": columns,
                                    "database_type": "SQLite",
                                    "context_size": context_size,
                                    "context_limit": MAX_CONTEXT_SIZE,
                                    "exceeded_limit": False
                                }
                            }
                        else:
                            return {
                                "status": "SQLite query executed successfully. No rows returned.",
                                "data": None,
                                "metadata": {
                                    "row_count": 0,
                                    "column_count": 0,
                                    "columns": [],
                                    "database_type": "SQLite"
                                }
                            }
                            
        except Exception as e:
            error_msg = str(e)
            
            # Enhanced DuckDB-specific error handling
            if is_duckdb:
                duckdb_suggestions = []
                
                if "must appear in the GROUP BY clause" in error_msg:
                    duckdb_suggestions.append("Wrap non-grouped columns with ANY_VALUE() function")
                    duckdb_suggestions.append("Example: SELECT group_col, ANY_VALUE(other_col) FROM table GROUP BY group_col")
                
                if "GROUP_CONCAT" in error_msg:
                    duckdb_suggestions.append("Use STRING_AGG(column, ',') instead of GROUP_CONCAT(column)")
                
                if "REAL" in error_msg or "Real" in error_msg:
                    duckdb_suggestions.append("Use DOUBLE instead of REAL for floating-point numbers")
                
                if "SUBSTR" in error_msg:
                    duckdb_suggestions.append("Use SUBSTRING() instead of SUBSTR()")
                
                if "STRFTIME" in error_msg:
                    duckdb_suggestions.append("Use DAYOFWEEK() instead of STRFTIME('%w') for day of week")
                    duckdb_suggestions.append("Use DATE_DIFF() for date calculations")
                
                if "TIMESTAMP" in query and "TIMESTAMP" not in error_msg:
                    duckdb_suggestions.append("Quote TIMESTAMP column as \"TIMESTAMP\" (it's a reserved keyword)")
                
                if duckdb_suggestions:
                    suggestion_text = "\n\nDuckDB-specific suggestions:\n" + "\n".join(f"• {s}" for s in duckdb_suggestions)
                    error_msg += suggestion_text
            
            return {"error": f"Error executing query: {error_msg}"}

    try:
        result = await asyncio.wait_for(async_execute_query(), timeout=QUERY_TIMEOUT)
        return result
    except asyncio.TimeoutError:
        db_type = "DuckDB" if is_duckdb else "SQLite"
        timeout_message = (
            f"{db_type} query execution timed out after {QUERY_TIMEOUT} seconds. "
            f"This usually indicates the query is too complex or returns too many results. "
            f"Please try a more specific query with additional WHERE conditions or add a LIMIT clause "
            f"to reduce the result set size. Consider using techniques like: "
            f"1) Adding LIMIT with a reasonable number (e.g., LIMIT 100), "
            f"2) Adding more specific WHERE conditions to filter data, "
            f"3) Using aggregate functions (COUNT, SUM, AVG) instead of selecting all rows, "
            f"4) Selecting fewer columns if you don't need all data"
        )
        
        if is_duckdb:
            timeout_message += (
                f", 5) For DuckDB, consider using sampling: SELECT * FROM table USING SAMPLE 1000 ROWS, "
                f"6) Use EXPLAIN to analyze query performance before execution, "
                f"7) Note: Results are also limited by context window size ({config.config.get_int('app.sqlite_db.max_context_size', 100000):,} characters)."
            )
        
        logger.warning(f"Query timed out after {QUERY_TIMEOUT} seconds: {query}")
        return {"error": timeout_message}

@mcp.tool(description="Analyzes a DuckDB query for performance optimization and provides execution plan")
async def analyze_duckdb_query(
        query: str,
        context: Context[Any, Any, Request] = None
) -> dict:
    """
    Analyzes a DuckDB query and provides performance insights and execution plan.

    :param query: The DuckDB query string to analyze.
    :type query: str
    :param context: **(Injected by FastMCP)** The execution context object
    :type context: Context[Any, Any, Request]
    :return: A dictionary containing query analysis results.
    :rtype: dict
    """
    user_info = get_user_info(context)
    logger.info(f"Running DuckDB query analysis tool on behalf of user: {user_info.sub} with email: {user_info.email}")

    DB_PATH = config.config.get_string("app.sqlite_db.file.path", "../data/demo.duckdb")
    
    if not DB_PATH.endswith('.duckdb'):
        return {"error": "Query analysis is only available for DuckDB databases (.duckdb files)"}
    
    try:
        import duckdb
        from concurrent.futures import ThreadPoolExecutor
        import asyncio
        
        def analyze_query():
            with duckdb.connect(DB_PATH) as conn:
                results = {}
                
                # Get execution plan
                try:
                    explain_result = conn.execute(f"EXPLAIN {query}").fetchall()
                    results["execution_plan"] = [row[0] for row in explain_result]
                except Exception as e:
                    results["execution_plan_error"] = str(e)
                
                # Get query tree
                try:
                    tree_result = conn.execute(f"EXPLAIN (FORMAT JSON) {query}").fetchall()
                    results["query_tree"] = tree_result[0][0] if tree_result else None
                except Exception as e:
                    results["query_tree_error"] = str(e)
                
                # Estimate query complexity
                complexity_hints = []
                query_lower = query.lower()
                
                if "join" in query_lower:
                    join_count = query_lower.count("join")
                    complexity_hints.append(f"Contains {join_count} JOIN operation(s)")
                
                if "group by" in query_lower:
                    complexity_hints.append("Uses GROUP BY aggregation")
                
                if "order by" in query_lower:
                    complexity_hints.append("Uses ORDER BY sorting")
                
                if "window" in query_lower or "over" in query_lower:
                    complexity_hints.append("Uses window functions")
                
                if "with" in query_lower:
                    complexity_hints.append("Uses Common Table Expressions (CTEs)")
                
                if len(query) > 1000:
                    complexity_hints.append("Large query (>1000 characters)")
                
                results["complexity_analysis"] = complexity_hints
                
                # Performance recommendations
                recommendations = []
                
                if "select *" in query_lower:
                    recommendations.append("Consider selecting only needed columns instead of SELECT *")
                
                if "limit" not in query_lower and "count" not in query_lower:
                    recommendations.append("Consider adding LIMIT clause for large result sets")
                
                if "where" not in query_lower and "having" not in query_lower:
                    recommendations.append("Consider adding WHERE conditions to filter data")
                
                if "string_agg" in query_lower:
                    recommendations.append("STRING_AGG operations can be memory-intensive for large groups")
                
                results["performance_recommendations"] = recommendations
                
                return results
        
        # Run analysis in thread pool
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as executor:
            analysis = await loop.run_in_executor(executor, analyze_query)
            
            return {
                "status": "Query analysis completed successfully",
                "analysis": analysis
            }
            
    except Exception as e:
        return {"error": f"Error analyzing query: {str(e)}"}

@mcp.tool(description="Returns the current date in ISO format (YYYY-MM-DD)")
def get_current_date(context: Context[Any, Any, Request] = None) -> str:
    """Returns the current date in ISO format (YYYY-MM-DD)."""
    current_date = datetime.date.today().isoformat()
    logger.info(f"get_current_date tool called. Returning: {current_date}")
    return current_date


if __name__ == "__main__":
    """
    Run with: python -m discover_search.aisio_chat.tools.mcp_server
    """
    # mcp.run('sse')
    mcp.run(transport="streamable-http")

    # uvicorn.run(
    #     mcp.streamable_http_app(),
    #     host=config.config.get_string("app.http.server.bind.address"),
    #     port=config.config.get_int("app.http.server.port"),
    #     ssl_keyfile="/Users/andrew.carter/data/workspace-ist/keycloak/ssl/pulse-dev.pem",
    #     ssl_certfile="/Users/andrew.carter/data/workspace-ist/keycloak/ssl/pulse-dev.crt"
    # )
