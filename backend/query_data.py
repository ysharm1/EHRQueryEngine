#!/usr/bin/env python3
"""
Simple command-line interface for querying extracted clinical data.
Allows residents to query GCS scores, filter by provider, etc.
"""

import sys
import os
from pathlib import Path

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import get_duckdb_connection

def query_gcs_scores(conn, patient_id=None, provider_filter=None):
    """Query GCS scores from the database."""
    query = """
    SELECT 
        p.patient_id,
        p.mrn,
        vs.value as gcs_score,
        vs.recorded_at,
        vs.context,
        vs.source_file
    FROM vital_signs vs
    JOIN patients p ON vs.patient_id = p.patient_id
    WHERE vs.vital_name = 'GCS'
    """
    
    params = []
    if patient_id:
        query += " AND p.patient_id = ?"
        params.append(patient_id)
    
    if provider_filter:
        # Join with procedures to filter by provider
        query += """
        AND EXISTS (
            SELECT 1 FROM procedures_extracted pe
            WHERE pe.patient_id = p.patient_id
            AND pe.provider LIKE ?
        )
        """
        params.append(f"%{provider_filter}%")
    
    query += " ORDER BY vs.recorded_at DESC"
    
    return conn.execute(query, params).fetchall()

def find_lowest_gcs_per_patient(conn):
    """Find the lowest GCS score for each patient."""
    query = """
    SELECT 
        p.patient_id,
        p.mrn,
        MIN(vs.value) as lowest_gcs,
        COUNT(vs.value) as gcs_measurements,
        MIN(vs.recorded_at) as first_measurement,
        MAX(vs.recorded_at) as last_measurement
    FROM vital_signs vs
    JOIN patients p ON vs.patient_id = p.patient_id
    WHERE vs.vital_name = 'GCS'
    GROUP BY p.patient_id, p.mrn
    ORDER BY lowest_gcs ASC
    """
    
    return conn.execute(query).fetchall()

def query_by_provider(conn, provider_type="surgeon"):
    """Query data by provider type."""
    query = """
    SELECT 
        p.patient_id,
        p.mrn,
        pe.description as procedure,
        pe.provider,
        pe.procedure_date,
        pe.source_file
    FROM procedures_extracted pe
    JOIN patients p ON pe.patient_id = p.patient_id
    WHERE pe.provider LIKE ?
    ORDER BY pe.procedure_date DESC
    """
    
    return conn.execute(query, [f"%{provider_type}%"]).fetchall()

def main():
    """Main command-line interface."""
    print("=" * 60)
    print("EHR Data Query Tool")
    print("=" * 60)
    print("1. Query GCS scores")
    print("2. Find lowest GCS per patient")
    print("3. Query data by provider (e.g., surgeons)")
    print("4. Exit")
    print("-" * 60)
    
    conn = get_duckdb_connection()
    
    while True:
        try:
            choice = input("\nSelect option (1-4): ").strip()
            
            if choice == "1":
                patient_id = input("Patient ID (optional, press Enter for all): ").strip() or None
                provider_filter = input("Provider filter (e.g., 'surgeon', press Enter for all): ").strip() or None
                
                results = query_gcs_scores(conn, patient_id, provider_filter)
                print(f"\nFound {len(results)} GCS records:")
                for row in results:
                    print(f"  Patient: {row[0]} | GCS: {row[2]} | Date: {row[3]} | Context: {row[4]}")
                    print(f"    Source: {Path(row[5]).name}")
                    
            elif choice == "2":
                results = find_lowest_gcs_per_patient(conn)
                print(f"\nFound {len(results)} patients with GCS scores:")
                for row in results:
                    print(f"  Patient: {row[0]} | Lowest GCS: {row[2]} | Measurements: {row[3]}")
                    print(f"    First: {row[4]} | Last: {row[5]}")
                    
            elif choice == "3":
                provider_type = input("Provider type (e.g., 'surgeon', 'resident', 'attending'): ").strip() or "surgeon"
                results = query_by_provider(conn, provider_type)
                print(f"\nFound {len(results)} procedures by {provider_type}:")
                for row in results:
                    print(f"  Patient: {row[0]} | Procedure: {row[2]}")
                    print(f"    Provider: {row[3]} | Date: {row[4]}")
                    print(f"    Source: {Path(row[5]).name}")
                    
            elif choice == "4":
                print("Goodbye!")
                break
                
            else:
                print("Invalid choice. Please select 1-4.")
                
        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
        except Exception as e:
            print(f"Error: {e}")
    
    conn.close()

if __name__ == "__main__":
    main()