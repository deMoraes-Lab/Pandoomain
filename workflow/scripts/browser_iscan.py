#!/usr/bin/env python3
"""
Convert InterProScan TSV results to a SQLite database for the browser visualizer.

This script reads the InterProScan TSV output and creates a SQLite database
indexed by protein ID (pid). It is designed to be part of the Pandoomain pipeline.
"""

import argparse
import os
import sqlite3
import sys
from pathlib import Path
from typing import List

import pandas as pd


def setup_database(output_db: str) -> None:
    """
    Remove existing database and clean up.

    Args:
        output_db: Path to the output SQLite database.
    """
    if os.path.exists(output_db):
        print(f"Removing existing database: {output_db}")
        os.remove(output_db)


def create_index(conn: sqlite3.Connection, table_name: str) -> None:
    """
    Create an index on the 'pid' column.

    Args:
        conn: SQLite connection object.
        table_name: Name of the table to index.
    """
    print(f"Creating index on 'pid' for table '{table_name}'...")
    try:
        cursor = conn.cursor()
        cursor.execute(f"CREATE INDEX idx_iscan_pid ON {table_name} (pid);")
        print("  ...Index created.")
    except Exception as e:
        print(f"ERROR creating index: {e}", file=sys.stderr)


def tsv_to_sqlite(input_tsv: str, output_db: str, chunk_size: int = 100000) -> None:
    """
    Convert the iscan TSV file to a SQLite database.

    Args:
        input_tsv: Path to the input TSV file.
        output_db: Path to the output SQLite database.
        chunk_size: Number of rows to process at a time.
    """
    table_name = "iscan"

    print(f"--- Starting TSV to SQLite Conversion for InterProScan ---")
    print(f"Input: {input_tsv}")
    print(f"Output: {output_db}")

    if not os.path.exists(input_tsv):
        print(f"ERROR: Input file not found at '{input_tsv}'", file=sys.stderr)
        sys.exit(1)

    # Ensure output directory exists
    output_dir = os.path.dirname(output_db)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)

    setup_database(output_db)

    print(f"Connecting to SQLite database: {output_db}")
    conn = sqlite3.connect(output_db, timeout=300.0)

    try:
        # Columns to use from the TSV (0-indexed)
        # 0: pid, 1: start, 2: stop, 3: length, 7: pfam, 8: pfam_desc
        cols_to_use = [0, 1, 2, 3, 7, 8]
        col_names = ["pid", "start", "stop", "length", "pfam", "pfam_desc"]

        print(f"Reading and loading chunks from {input_tsv}...")
        
        # Specify dtypes to avoid warnings and mixed type issues
        dtypes = {
            1: "str", # start (read as str then coerce)
            2: "str", # stop
            3: "str", # length
            7: "str", # pfam
            8: "str"  # pfam_desc
        }

        reader = pd.read_csv(
            input_tsv,
            sep="\t",
            header=None,
            chunksize=chunk_size,
            iterator=True,
            usecols=cols_to_use,
            dtype=dtypes,
            low_memory=False,
            comment="#",
        )

        for i, chunk in enumerate(reader):
            print(f"  Processing chunk {i + 1}...", end="\r")

            chunk.columns = col_names

            # Ensure correct data types
            chunk["start"] = pd.to_numeric(chunk["start"], errors="coerce").fillna(0).astype(int)
            chunk["stop"] = pd.to_numeric(chunk["stop"], errors="coerce").fillna(0).astype(int)
            chunk["length"] = pd.to_numeric(chunk["length"], errors="coerce").fillna(0).astype(int)

            chunk.to_sql(table_name, conn, if_exists="append", index=False)
        
        print("\nAll chunks loaded.")

        create_index(conn, table_name)

    except Exception as e:
        print(f"\nERROR during processing: {e}", file=sys.stderr)
        conn.close()
        sys.exit(1)

    conn.close()
    print("--- Conversion complete! ---")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert InterProScan TSV to SQLite DB for browser visualizer."
    )
    parser.add_argument("input_tsv", help="Path to input TSV file")
    parser.add_argument("output_db", help="Path to output SQLite database")
    
    args = parser.parse_args()
    
    tsv_to_sqlite(args.input_tsv, args.output_db)


if __name__ == "__main__":
    main()
