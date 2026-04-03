#!/bin/bash

# Entrypoint script for mcp_query_duckdb service
# Two-phase generation:
#   1. Run gen_{dataset}_data.py to generate CSV files in data/{dataset}/
#   2. Run csv_to_duckdb.py to convert CSVs to DuckDB in data/databases/

set -e

# Get configuration
ACTIVE_DATASET="${ACTIVE_DATASET:-hormuz}"
SQLITE_DB_FILE_PATH="${SQLITE_DB_FILE_PATH:-/app/databases/hormuz.duckdb}"
DEMO_REPEATABLE_SEED="${DEMO_REPEATABLE_SEED:-42}"

echo "================================"
echo "MCP DuckDB Service Startup"
echo "================================"
echo "Dataset: $ACTIVE_DATASET"
echo "Database: $SQLITE_DB_FILE_PATH"
echo ""

# Check if database file already exists
if [ -f "$SQLITE_DB_FILE_PATH" ]; then
    echo "✓ Database file found: $SQLITE_DB_FILE_PATH"
    echo "  Using existing database"
    echo ""
else
    echo "✗ Database file not found: $SQLITE_DB_FILE_PATH"

    # Check if dataset generator exists
    GENERATOR="/app/data/datasets/${ACTIVE_DATASET}/gen_${ACTIVE_DATASET}_data.py"
    CSV_IMPORTER="/app/data/csv_to_duckdb.py"

    if [ ! -f "$GENERATOR" ]; then
        echo "✗ Generator not found: $GENERATOR"
        echo "  Cannot generate database without generator"
        echo "  Continuing with service startup (database operations will fail)"
        echo ""
    elif [ ! -f "$CSV_IMPORTER" ]; then
        echo "✗ CSV importer not found: $CSV_IMPORTER"
        echo "  Cannot convert CSV to DuckDB without importer"
        echo "  Continuing with service startup (database operations will fail)"
        echo ""
    else
        echo "✓ Generator found: $GENERATOR"
        echo "✓ CSV importer found: $CSV_IMPORTER"
        echo ""
        echo "Phase 1: Generating CSV files from dataset: $ACTIVE_DATASET"
        echo "This may take a few moments..."
        echo ""

        # Create output directory for CSV files
        mkdir -p "/app/data/${ACTIVE_DATASET}"

        # Run the generator to create CSV files in data/{dataset}/
        cd "/app/data/datasets/${ACTIVE_DATASET}"
        if [ -n "$DEMO_REPEATABLE_SEED" ] && [ "$DEMO_REPEATABLE_SEED" != "0" ]; then
            echo "Using seed: $DEMO_REPEATABLE_SEED (repeatable generation)"
            python "gen_${ACTIVE_DATASET}_data.py" --output-dir "/app/data/${ACTIVE_DATASET}" --seed "$DEMO_REPEATABLE_SEED"
        else
            python "gen_${ACTIVE_DATASET}_data.py" --output-dir "/app/data/${ACTIVE_DATASET}"
        fi

        if [ $? -ne 0 ]; then
            echo ""
            echo "✗ Failed to generate CSV files"
            exit 1
        fi

        echo ""
        echo "✓ CSV files generated successfully"
        echo ""
        echo "Phase 2: Converting CSVs to DuckDB"
        echo "Source: /app/data/${ACTIVE_DATASET}/"
        echo "Target: $SQLITE_DB_FILE_PATH"
        echo ""

        # Ensure database directory exists
        DB_DIR=$(dirname "$SQLITE_DB_FILE_PATH")
        mkdir -p "$DB_DIR"

        # Import CSVs to DuckDB
        # The generator puts CSVs in /app/data/{dataset}/ directory
        python /app/data/csv_to_duckdb.py \
            --directory "/app/data/${ACTIVE_DATASET}" \
            --db "$SQLITE_DB_FILE_PATH"

        if [ $? -eq 0 ]; then
            echo ""
            echo "✓ Database created successfully: $SQLITE_DB_FILE_PATH"
            echo ""
        else
            echo ""
            echo "✗ Failed to convert CSV to DuckDB"
            exit 1
        fi
    fi
fi

echo "Starting MCP DuckDB server..."
echo "================================"
echo ""

# Start the MCP server
exec python -m mcp_server.server

