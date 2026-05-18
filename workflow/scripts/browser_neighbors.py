#!/usr/bin/env python3
"""
Convert Neighbors TSV results to a SQLite database for the browser visualizer.

This script reads the neighbors TSV output and creates a detailed SQLite database
with indexes for efficient querying by the visualizer.
"""

import argparse
import os
import sqlite3
import sys
from typing import Dict

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


def create_indexes(conn: sqlite3.Connection, table_name: str) -> None:
    """
    Create indexes on genome and neighborhood ID columns.

    Args:
        conn: SQLite connection object.
        table_name: Name of the table to index.
    """
    print(f"Creating indexes for table '{table_name}'...")
    cursor = conn.cursor()
    try:
        print("  ...Index on 'genome'")
        cursor.execute(f"CREATE INDEX idx_genome ON {table_name} (genome);")
        
        print("  ...Index on 'nei'")
        cursor.execute(f"CREATE INDEX idx_nei ON {table_name} (nei);")
        
        print("  ...Composite Index on (genome, nei)")
        cursor.execute(f"CREATE INDEX idx_genome_nei ON {table_name} (genome, nei);")
        
        print("  ...Indexes created.")
    except Exception as e:
        print(f"ERROR creating indexes: {e}", file=sys.stderr)


def tsv_to_sqlite(input_tsv: str, output_db: str, chunk_size: int = 100000) -> None:
    """
    Convert the neighbors TSV file to a SQLite database.

    Args:
        input_tsv: Path to the input TSV file.
        output_db: Path to the output SQLite database.
        chunk_size: Processing chunk size.
    """
    table_name = "neighbors"

    print(f"--- Starting TSV to SQLite Conversion for Neighbors ---")
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
        # Mapping input TSV columns to DB columns
        cols_to_read = {
            "genome": "genome",
            "neid": "nei",
            "neoff": "neioff",
            "order": "gene_order",
            "pid": "pid",
            "gene": "gene",
            "product": "product",
            "start": "start",
            "end": "end",
            "strand": "strand",
            "frame": "frame",
            "locus_tag": "locus_tag",
            "contig": "contig",
            "queries": "queries",
        }

        print(f"Reading and loading chunks from {input_tsv}...")
        
        reader = pd.read_csv(
            input_tsv,
            sep="\t",
            chunksize=chunk_size,
            iterator=True,
            usecols=list(cols_to_read.keys()),
        )

        for i, chunk in enumerate(reader):
            print(f"  Processing chunk {i + 1}...", end="\r")
            
            chunk.rename(columns=cols_to_read, inplace=True)
            chunk.to_sql(table_name, conn, if_exists="append", index=False)
            
        print("\nAll chunks loaded.")

        create_indexes(conn, table_name)

    except Exception as e:
        print(f"\nERROR during processing: {e}", file=sys.stderr)
        conn.close()
        sys.exit(1)

    conn.close()
    print("--- Conversion complete! ---")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert Neighbors TSV to SQLite DB for browser visualizer."
    )
    parser.add_argument("input_tsv", help="Path to input TSV file")
    parser.add_argument("output_db", help="Path to output SQLite database")
    
    args = parser.parse_args()
    
    tsv_to_sqlite(args.input_tsv, args.output_db)


if __name__ == "__main__":
    main()
