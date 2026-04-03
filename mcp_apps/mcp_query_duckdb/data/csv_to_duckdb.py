#!/usr/bin/env python3
"""
CSV to DuckDB Importer

Imports CSV files into DuckDB tables. Table names are derived from CSV filenames
(without .csv extension).

Features:
- Auto-detects CSV files in specified directory
- Creates tables if they don't exist
- Optionally appends to existing tables or recreates them
- Handles multiple CSV files in one command

Usage:
    # Import all CSVs in current directory (recreates existing tables)
    python csv_to_duckdb.py

    # Import from specific directory
    python csv_to_duckdb.py --directory ./data

    # Append to existing tables instead of recreating
    python csv_to_duckdb.py --directory ./data --append

    # Import specific CSV file
    python csv_to_duckdb.py --file data.csv

Example:
    # From gen_hormuz_data.py
    from csv_to_duckdb import CSVImporter
    importer = CSVImporter(directory='.', db_file='hormuz.duckdb')
    importer.import_all()
"""

import argparse
import sys
import os
import glob
from pathlib import Path

try:
    import duckdb
    DUCKDB_AVAILABLE = True
except ImportError:
    DUCKDB_AVAILABLE = False


class CSVImporter:
    """Import CSV files into DuckDB tables."""

    def __init__(self, directory='.', db_file=None, append=False):
        """
        Initialize the CSV importer.

        Args:
            directory: Directory containing CSV files (default: current)
            db_file: DuckDB database file path (default: derived from directory)
            append: Whether to append to existing tables (default: False, recreates)
        """
        if not DUCKDB_AVAILABLE:
            raise ImportError("DuckDB not installed. Install with: pip install duckdb")

        self.directory = directory
        self.append = append

        # Derive database filename if not provided
        if db_file is None:
            dir_name = Path(directory).name if directory != '.' else 'data'
            self.db_file = f"{dir_name}.duckdb"
        else:
            self.db_file = db_file

    def get_csv_files(self, pattern='*.csv'):
        """Get list of CSV files in directory."""
        csv_dir = os.path.join(self.directory, pattern)
        return sorted(glob.glob(csv_dir))

    def get_table_name(self, csv_file):
        """Derive table name from CSV filename."""
        basename = os.path.basename(csv_file)
        return os.path.splitext(basename)[0]

    def import_csv(self, csv_file, conn):
        """Import a single CSV file into DuckDB."""
        table_name = self.get_table_name(csv_file)

        try:
            # Check if table exists
            result = conn.execute(
                f"SELECT table_name FROM information_schema.tables WHERE table_schema='main' AND table_name='{table_name}'"
            ).fetchall()
            table_exists = len(result) > 0

            if table_exists and not self.append:
                # Drop existing table if not appending
                conn.execute(f"DROP TABLE {table_name}")
                print(f"  Dropped existing table: {table_name}")

            if table_exists and self.append:
                # Append to existing table - INSERT data
                conn.execute(f"INSERT INTO {table_name} SELECT * FROM read_csv_auto('{csv_file}')")
                print(f"✓ Appended {csv_file} → {table_name}")
            else:
                # Create new table
                conn.execute(f"CREATE TABLE {table_name} AS SELECT * FROM read_csv_auto('{csv_file}')")
                print(f"✓ Imported {csv_file} → {table_name}")

            return True

        except Exception as e:
            print(f"✗ Error importing {csv_file}: {e}", file=sys.stderr)
            return False

    def import_all(self, pattern='*.csv'):
        """Import all CSV files in directory."""
        csv_files = self.get_csv_files(pattern)

        if not csv_files:
            print(f"⚠ No CSV files found in {self.directory}", file=sys.stderr)
            return False

        try:
            conn = duckdb.connect(self.db_file)

            print(f"Importing CSVs to {self.db_file}")
            print(f"Append mode: {self.append}\n")

            success_count = 0
            for csv_file in csv_files:
                if self.import_csv(csv_file, conn):
                    success_count += 1

            conn.close()

            print(f"\n✓ Successfully imported {success_count}/{len(csv_files)} files")
            return True

        except Exception as e:
            print(f"✗ Error connecting to database: {e}", file=sys.stderr)
            return False

    def import_single(self, csv_file):
        """Import a single CSV file."""
        if not os.path.exists(csv_file):
            print(f"✗ File not found: {csv_file}", file=sys.stderr)
            return False

        try:
            conn = duckdb.connect(self.db_file)
            success = self.import_csv(csv_file, conn)
            conn.close()
            return success
        except Exception as e:
            print(f"✗ Error: {e}", file=sys.stderr)
            return False

    def get_table_stats(self):
        """Get statistics about imported tables."""
        try:
            conn = duckdb.connect(self.db_file)

            result = conn.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema='main'"
            ).fetchall()

            if not result:
                print("No tables found in database")
                return

            print(f"\nTables in {self.db_file}:")
            for (table_name,) in result:
                count = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
                print(f"  {table_name}: {count} records")

            conn.close()
        except Exception as e:
            print(f"✗ Error: {e}", file=sys.stderr)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Import CSV files into DuckDB tables'
    )
    parser.add_argument(
        '--directory', '-d', type=str, default='.',
        help='Directory containing CSV files (default: current directory)'
    )
    parser.add_argument(
        '--db', type=str, default=None,
        help='DuckDB database file (default: derived from directory name)'
    )
    parser.add_argument(
        '--file', '-f', type=str, default=None,
        help='Import a specific CSV file (not used with --directory)'
    )
    parser.add_argument(
        '--append', '-a', action='store_true',
        help='Append to existing tables instead of recreating them'
    )
    parser.add_argument(
        '--stats', '-s', action='store_true',
        help='Show statistics about imported tables'
    )

    args = parser.parse_args()

    try:
        importer = CSVImporter(
            directory=args.directory,
            db_file=args.db,
            append=args.append
        )

        if args.stats:
            importer.get_table_stats()
            return 0

        if args.file:
            success = importer.import_single(args.file)
            return 0 if success else 1

        success = importer.import_all()
        return 0 if success else 1

    except ImportError as e:
        print(f"✗ {e}", file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())

