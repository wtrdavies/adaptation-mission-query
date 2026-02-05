"""
Data Loader for EU Adaptation Mission Projects

Processes XLSX files containing adaptation mission project and participant data
and loads them into SQLite.

Usage:
    python load_data.py
"""

import sys
import os
import sqlite3
import pandas as pd
from pathlib import Path


def load_participants(filepath: Path):
    """Load and standardize participants data"""

    print(f"  Loading: {filepath.name}")

    try:
        df = pd.read_excel(filepath)
        print(f"    Loaded {len(df):,} rows")

        # Rename columns to snake_case
        column_mapping = {
            'Participations': 'participations',
            'Legal Name': 'legal_name',
            'Participant Identification Code': 'participant_code',
            'Participant Type': 'participant_type',
            'NET EU financial contribution (euro)': 'net_eu_contribution_euro',
            'Funding programme': 'funding_programme',
            'Country/Territory': 'country_territory',
            'CITY': 'city',
            'NUTS 1 Name': 'nuts_1_name',
            'NUTS 2 Name': 'nuts_2_name',
            'NUTS 3 Name': 'nuts_3_name',
        }

        df = df.rename(columns=column_mapping)

        # Verify all expected columns are present
        expected_cols = list(column_mapping.values())
        missing = [col for col in expected_cols if col not in df.columns]
        if missing:
            print(f"    Warning: Missing columns: {missing}")

        return df

    except Exception as e:
        print(f"    Error loading file: {e}")
        return None


def load_projects(filepath: Path):
    """Load and standardize projects data"""

    print(f"  Loading: {filepath.name}")

    try:
        df = pd.read_excel(filepath)
        print(f"    Loaded {len(df):,} rows")

        # Rename columns to snake_case
        column_mapping = {
            'ACRONYM': 'acronym',
            'TITLE': 'title',
            'Project id': 'project_url',
            'Project Start Date': 'project_start_date',
            'Project End Date': 'project_end_date',
            'Total budget (euro)': 'total_budget_euro',
            'EU financial contribution (euro)': 'eu_contribution_euro',
            'HRP Result (link)': 'hrp_result_url',
            'Funding programme': 'funding_programme',
            'TOPIC_CODE': 'topic_code',
            'Type of Action': 'type_of_action',
            'Mission relevance flag': 'mission_relevance_flag',
            'category': 'category',
            'climate_risks': 'climate_risks',
            'main_themes': 'main_themes',
            'regions': 'regions',
            'coordinator': 'coordinator',
            'website': 'website',
        }

        df = df.rename(columns=column_mapping)

        # Parse coordinator into org and country
        # Format: "Organization Name, Country"
        def parse_coordinator(coord_str):
            if pd.isna(coord_str) or ',' not in coord_str:
                return coord_str, None, None
            parts = coord_str.rsplit(',', 1)
            org = parts[0].strip().upper()  # Uppercase to match legal_name
            country = parts[1].strip() if len(parts) > 1 else None
            return coord_str, org, country

        # Apply parsing
        parsed = df['coordinator'].apply(parse_coordinator)
        df['coordinator'] = parsed.apply(lambda x: x[0])
        df['coordinator_org'] = parsed.apply(lambda x: x[1])
        df['coordinator_country'] = parsed.apply(lambda x: x[2])

        # Verify all expected columns are present
        expected_cols = list(column_mapping.values()) + ['coordinator_org', 'coordinator_country']
        missing = [col for col in expected_cols if col not in df.columns]
        if missing:
            print(f"    Warning: Missing columns: {missing}")

        return df

    except Exception as e:
        print(f"    Error loading file: {e}")
        return None


def create_database(db_path: str, df_participants: pd.DataFrame, df_projects: pd.DataFrame):
    """Create SQLite database with both tables"""

    if df_participants is None or df_projects is None:
        print("Cannot create database: missing data!")
        return

    print(f"\nCreating database: {db_path}")
    conn = sqlite3.connect(db_path)

    # Load participants table
    print("Loading participants table...")
    df_participants.to_sql('participants', conn, if_exists='replace', index_label='participant_id')

    # Load projects table
    print("Loading projects table...")
    df_projects.to_sql('projects', conn, if_exists='replace', index_label='project_id')

    # Create indexes for common queries
    print("Creating indexes...")
    indexes = [
        'CREATE INDEX idx_legal_name ON participants(legal_name)',
        'CREATE INDEX idx_country ON participants(country_territory)',
        'CREATE INDEX idx_participant_type ON participants(participant_type)',
        'CREATE INDEX idx_funding_programme_part ON participants(funding_programme)',

        'CREATE INDEX idx_acronym ON projects(acronym)',
        'CREATE INDEX idx_funding_programme_proj ON projects(funding_programme)',
        'CREATE INDEX idx_coordinator_org ON projects(coordinator_org)',
        'CREATE INDEX idx_start_date ON projects(project_start_date)',
        'CREATE INDEX idx_category ON projects(category)',
    ]

    for idx_sql in indexes:
        try:
            conn.execute(idx_sql)
        except sqlite3.OperationalError as e:
            print(f"    Warning: {e}")

    conn.commit()

    # Print summary
    print("\n" + "=" * 60)
    print("DATABASE SUMMARY")
    print("=" * 60)

    summary_queries = [
        ("Total participants", "SELECT COUNT(*) FROM participants"),
        ("Total projects", "SELECT COUNT(*) FROM projects"),
        ("Participant countries", "SELECT COUNT(DISTINCT country_territory) FROM participants"),
        ("Total participant funding (€M)", "SELECT ROUND(SUM(net_eu_contribution_euro)/1000000, 2) FROM participants"),
        ("Total project budget (€M)", "SELECT ROUND(SUM(total_budget_euro)/1000000, 2) FROM projects"),
        ("Total EU contribution (€M)", "SELECT ROUND(SUM(eu_contribution_euro)/1000000, 2) FROM projects"),
        ("Project date range", "SELECT MIN(project_start_date) || ' to ' || MAX(project_end_date) FROM projects"),
        ("Coordinator joins", "SELECT COUNT(*) FROM projects p JOIN participants part ON p.coordinator_org = part.legal_name"),
    ]

    for label, query in summary_queries:
        try:
            result = conn.execute(query).fetchone()[0]
            print(f"{label}: {result}")
        except Exception as e:
            print(f"{label}: Error - {e}")

    conn.close()
    print(f"\nDatabase saved to: {db_path}")


def main():
    # File paths
    script_dir = Path(__file__).parent
    participants_file = script_dir / "adaptation_mission_participants.xlsx"
    projects_file = script_dir / "mission_funded_projects_with_details.xlsx"
    output_db = script_dir / "adaptation_mission.db"

    # Verify files exist
    if not participants_file.exists():
        print(f"Error: Participants file not found: {participants_file}")
        sys.exit(1)

    if not projects_file.exists():
        print(f"Error: Projects file not found: {projects_file}")
        sys.exit(1)

    print("=" * 60)
    print("EU ADAPTATION MISSION DATA LOADER")
    print("=" * 60)

    # Load files
    print("\nLoading participants data...")
    df_participants = load_participants(participants_file)

    print("\nLoading projects data...")
    df_projects = load_projects(projects_file)

    # Create database
    if df_participants is not None and df_projects is not None:
        create_database(str(output_db), df_participants, df_projects)
        print("\n✓ Database created successfully!")
    else:
        print("\n✗ Failed to create database due to loading errors")
        sys.exit(1)


if __name__ == "__main__":
    main()
