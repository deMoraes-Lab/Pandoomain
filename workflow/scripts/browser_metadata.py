#!/usr/bin/env python3
"""
Convert Genome Metadata TSV to a SQLite database for the browser visualizer.

This script reads the genomes_metadata.tsv output and creates a SQLite database
indexed by genome accession. It filters for specific columns required by the visualizer.
"""

import argparse
import os
import sqlite3
import sys
from typing import List, Optional

import pandas as pd


def setup_database(output_db: str) -> None:
    """
    Remove existing database.

    Args:
        output_db: Path to the output SQLite database.
    """
    if os.path.exists(output_db):
        print(f"Removing existing database: {output_db}")
        os.remove(output_db)


def create_index(conn: sqlite3.Connection, table_name: str) -> None:
    """
    Create an index on the 'genome' column.

    Args:
        conn: SQLite connection object.
        table_name: Name of the table to index.
    """
    print(f"Creating index on 'genome' for table '{table_name}'...")
    try:
        cursor = conn.cursor()
        cursor.execute(f"CREATE INDEX idx_metadata_genome ON {table_name} (genome);")
        print("  ...Index created.")
    except Exception as e:
        print(f"ERROR creating index: {e}", file=sys.stderr)


def tsv_to_sqlite(input_tsv: str, output_db: str) -> None:
    """
    Convert the metadata TSV file to a SQLite database.

    Args:
        input_tsv: Path to the input TSV file.
        output_db: Path to the output SQLite database.
    """
    table_name = "metadata"
    required_columns = ["genome", "org", "strain"]

    print(f"--- Starting TSV to SQLite Conversion for Metadata ---")
    print(f"Input: {input_tsv}")
    print(f"Output: {output_db}")

    if not os.path.exists(input_tsv):
        print(f"ERROR: Input file not found at '{input_tsv}'", file=sys.stderr)
        sys.exit(1)

    # Ensure output directory exists
    output_dir = os.path.dirname(output_db)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)

    print(f"Inspecting header of {input_tsv}...")
    try:
        header = pd.read_csv(input_tsv, sep="\t", nrows=0).columns.tolist()
        cols_to_use = [col for col in required_columns if col in header]

        if not cols_to_use:
            print(f"ERROR: None of required cols {required_columns} found.", file=sys.stderr)
            sys.exit(1)
        
        if "genome" not in cols_to_use:
            print(f"ERROR: Essential 'genome' column missing.", file=sys.stderr)
            sys.exit(1)

        print(f"  ...Found columns: {cols_to_use}")

    except Exception as e:
        print(f"ERROR reading header: {e}", file=sys.stderr)
        sys.exit(1)

    setup_database(output_db)

    print(f"Connecting to SQLite database: {output_db}")
    conn = sqlite3.connect(output_db, timeout=300.0)

    print(f"Loading data from {input_tsv}...")
    try:
        df = pd.read_csv(input_tsv, sep="\t", usecols=cols_to_use)
        
        # Ensure all required columns are present
        for col in required_columns:
            if col not in df.columns:
                df[col] = None
        
        # Reorder
        df = df[required_columns]

        df.to_sql(table_name, conn, if_exists="replace", index=False)
        print(f"  ...Data loaded into '{table_name}'.")

        create_index(conn, table_name)

    except Exception as e:
        print(f"ERROR loading data: {e}", file=sys.stderr)
        conn.close()
        sys.exit(1)

    conn.close()
    print("--- Conversion complete! ---")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert Metadata TSV to SQLite DB for browser visualizer."
    )
    parser.add_argument("input_tsv", help="Path to input TSV file")
    parser.add_argument("output_db", help="Path to output SQLite database")
    
    args = parser.parse_args()
    
    tsv_to_sqlite(args.input_tsv, args.output_db)


if __name__ == "__main__":
    main()
