#!/usr/bin/env python3
"""
Export DuckDB tables to CSV files

Exports all tables from a DuckDB database to individual CSV files named after the tables.

Usage:
    # Export the active dataset (from DEMO_DATASET env var)
    python export_duckdb_to_csv.py

    # Export specific dataset
    python export_duckdb_to_csv.py --dataset caribbean

    # Export with custom output directory
    python export_duckdb_to_csv.py --dataset hormuz --output-dir ./exports

    # Export from specific database file
    python export_duckdb_to_csv.py --db-file ./custom/path/data.duckdb --output-dir ./exports
"""

import os
import sys
import argparse
import duckdb
from pathlib import Path


def export_tables_to_csv(db_path, output_dir="."):
    """
    Export all tables from a DuckDB database to CSV files.

    Args:
        db_path: Path to the .duckdb database file
        output_dir: Directory to save CSV files (default: current directory)

    Returns:
        bool: True if successful, False otherwise
    """
    # Verify database exists
    if not os.path.exists(db_path):
        print(f"✗ Database file not found: {db_path}")
        return False

    # Create output directory
    os.makedirs(output_dir, exist_ok=True)

    try:
        # Connect to database
        print(f"Connecting to database: {db_path}")
        conn = duckdb.connect(db_path, read_only=True)

        # Get all tables
        tables = conn.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'").fetchall()

        if not tables:
            print("✗ No tables found in database")
            conn.close()
            return False

        table_names = [t[0] for t in tables]
        print(f"Found {len(table_names)} table(s): {', '.join(table_names)}\n")

        # Export each table
        exported_files = []
        for table_name in table_names:
            output_file = os.path.join(output_dir, f"{table_name}.csv")

            try:
                print(f"Exporting {table_name}...", end=" ")

                # Get row count
                count = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]

                # Export to CSV
                conn.execute(f"COPY {table_name} TO '{output_file}' (HEADER, DELIMITER ',')")

                print(f"✓ ({count:,} rows)")
                exported_files.append((table_name, output_file, count))

            except Exception as e:
                print(f"✗ Error: {e}")
                return False

        conn.close()

        # Print summary
        print(f"\n{'='*70}")
        print("Export Summary:")
        print(f"{'='*70}")
        total_rows = 0
        for table_name, file_path, count in exported_files:
            file_size = os.path.getsize(file_path)
            size_mb = file_size / (1024 * 1024)
            total_rows += count
            print(f"  {table_name:35} {count:>10,} rows  {size_mb:>8.2f} MB")
            print(f"    → {file_path}")

        print(f"{'='*70}")
        print(f"Total: {total_rows:,} rows exported to {len(exported_files)} file(s)")
        print(f"Output directory: {os.path.abspath(output_dir)}")
        print("✓ Export complete!\n")

        return True

    except Exception as e:
        print(f"✗ Error: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Export DuckDB tables to CSV files")

    parser.add_argument(
        "--dataset",
        type=str,
        default=None,
        help="Dataset name (e.g., caribbean, hormuz, ukraine, south_china_sea). "
             "If not specified, uses DEMO_DATASET environment variable or 'hormuz' default."
    )

    parser.add_argument(
        "--db-file",
        type=str,
        default=None,
        help="Path to specific .duckdb database file. "
             "If specified, --dataset is ignored."
    )

    parser.add_argument(
        "--output-dir",
        type=str,
        default=".",
        help="Output directory for CSV files (default: current directory)"
    )

    args = parser.parse_args()

    # Determine database file path
    if args.db_file:
        db_path = args.db_file
    else:
        # Get dataset name
        dataset = args.dataset or os.getenv("DEMO_DATASET", "hormuz")

        # Construct database path relative to this script
        script_dir = os.path.dirname(os.path.abspath(__file__))
        db_path = os.path.join(script_dir, "databases", f"{dataset}.duckdb")

    print(f"\n{'='*70}")
    print("DuckDB Table Exporter")
    print(f"{'='*70}\n")

    # Export tables
    success = export_tables_to_csv(db_path, args.output_dir)

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())

