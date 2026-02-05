"""
Database Validation Tests for EU Adaptation Mission Query Tool

Validates database integrity, schema, and data quality.
Run with: python test_database.py
"""

import sqlite3
import sys
from pathlib import Path


def run_test(conn, test_name, query, expected_condition, fail_msg="Test failed"):
    """Run a single test query and check condition"""
    try:
        cursor = conn.execute(query)
        result = cursor.fetchone()

        if expected_condition(result):
            print(f"✓ {test_name}: PASS")
            if result:
                print(f"  Result: {result[0] if len(result) == 1 else result}")
            return True
        else:
            print(f"✗ {test_name}: FAIL - {fail_msg}")
            print(f"  Result: {result}")
            return False
    except Exception as e:
        print(f"✗ {test_name}: ERROR - {e}")
        return False


def main():
    db_path = Path(__file__).parent / "adaptation_mission.db"

    if not db_path.exists():
        print(f"Error: Database not found at {db_path}")
        print("Please run load_data.py first to create the database.")
        sys.exit(1)

    print("=" * 60)
    print("EU ADAPTATION MISSION DATABASE VALIDATION")
    print("=" * 60)
    print()

    conn = sqlite3.connect(db_path)
    tests_passed = 0
    tests_failed = 0

    # Test 1: Row counts
    print("Test 1: Row counts")
    if run_test(
        conn,
        "Participants count",
        "SELECT COUNT(*) FROM participants",
        lambda r: r[0] == 908,
        "Expected 908 participants"
    ):
        tests_passed += 1
    else:
        tests_failed += 1

    if run_test(
        conn,
        "Projects count",
        "SELECT COUNT(*) FROM projects",
        lambda r: r[0] == 46,
        "Expected 46 projects"
    ):
        tests_passed += 1
    else:
        tests_failed += 1

    print()

    # Test 2: No NULLs in critical columns
    print("Test 2: Critical columns non-NULL")
    if run_test(
        conn,
        "Participants legal_name",
        "SELECT COUNT(*) FROM participants WHERE legal_name IS NULL",
        lambda r: r[0] == 0,
        "Found NULL legal_names"
    ):
        tests_passed += 1
    else:
        tests_failed += 1

    if run_test(
        conn,
        "Projects title",
        "SELECT COUNT(*) FROM projects WHERE title IS NULL",
        lambda r: r[0] == 0,
        "Found NULL titles"
    ):
        tests_passed += 1
    else:
        tests_failed += 1

    print()

    # Test 3: Coordinator join works
    print("Test 3: Coordinator join capability")
    if run_test(
        conn,
        "Coordinator joins",
        "SELECT COUNT(*) FROM projects p JOIN participants part ON p.coordinator_org = part.legal_name",
        lambda r: r[0] >= 10,
        "Expected at least 10 successful joins"
    ):
        tests_passed += 1
    else:
        tests_failed += 1

    print()

    # Test 4: Multi-value fields intact
    print("Test 4: Multi-value fields contain semicolons")
    if run_test(
        conn,
        "Climate risks format",
        "SELECT COUNT(*) FROM projects WHERE climate_risks LIKE '%;%'",
        lambda r: r[0] > 0,
        "No semicolons found in climate_risks"
    ):
        tests_passed += 1
    else:
        tests_failed += 1

    if run_test(
        conn,
        "Main themes format",
        "SELECT COUNT(*) FROM projects WHERE main_themes LIKE '%;%'",
        lambda r: r[0] > 0,
        "No semicolons found in main_themes"
    ):
        tests_passed += 1
    else:
        tests_failed += 1

    print()

    # Test 5: Date ranges valid
    print("Test 5: Date ranges valid")
    if run_test(
        conn,
        "Project dates in range",
        "SELECT COUNT(*) FROM projects WHERE project_start_date >= '2021-01-01' AND project_start_date <= '2029-12-31'",
        lambda r: r[0] > 0,
        "Project dates outside expected range"
    ):
        tests_passed += 1
    else:
        tests_failed += 1

    if run_test(
        conn,
        "End date after start date",
        "SELECT COUNT(*) FROM projects WHERE project_end_date < project_start_date",
        lambda r: r[0] == 0,
        "Found projects where end_date < start_date"
    ):
        tests_passed += 1
    else:
        tests_failed += 1

    print()

    # Test 6: Budget logic
    print("Test 6: Budget logic")
    if run_test(
        conn,
        "Total budget >= EU contribution",
        "SELECT COUNT(*) FROM projects WHERE total_budget_euro < eu_contribution_euro",
        lambda r: r[0] == 0,
        "Found projects where total_budget < eu_contribution"
    ):
        tests_passed += 1
    else:
        tests_failed += 1

    print()

    # Test 7: Index existence
    print("Test 7: Indexes exist")
    if run_test(
        conn,
        "Participant indexes",
        "SELECT COUNT(*) FROM sqlite_master WHERE type='index' AND tbl_name='participants'",
        lambda r: r[0] >= 4,
        "Expected at least 4 indexes on participants table"
    ):
        tests_passed += 1
    else:
        tests_failed += 1

    if run_test(
        conn,
        "Project indexes",
        "SELECT COUNT(*) FROM sqlite_master WHERE type='index' AND tbl_name='projects'",
        lambda r: r[0] >= 5,
        "Expected at least 5 indexes on projects table"
    ):
        tests_passed += 1
    else:
        tests_failed += 1

    print()

    # Test 8: Participant types
    print("Test 8: Participant types present")
    if run_test(
        conn,
        "Participant type diversity",
        "SELECT COUNT(DISTINCT participant_type) FROM participants",
        lambda r: r[0] >= 4,
        "Expected at least 4 participant types (PUB, PRC, HES, REC, OTH)"
    ):
        tests_passed += 1
    else:
        tests_failed += 1

    print()

    # Test 9: Geographic coverage
    print("Test 9: Geographic coverage")
    if run_test(
        conn,
        "Country diversity",
        "SELECT COUNT(DISTINCT country_territory) FROM participants",
        lambda r: r[0] >= 20,
        "Expected at least 20 different countries"
    ):
        tests_passed += 1
    else:
        tests_failed += 1

    print()

    # Test 10: Funding programmes
    print("Test 10: Funding programmes present")
    if run_test(
        conn,
        "Funding programme diversity",
        "SELECT COUNT(DISTINCT funding_programme) FROM projects",
        lambda r: r[0] >= 2,
        "Expected at least 2 funding programmes"
    ):
        tests_passed += 1
    else:
        tests_failed += 1

    print()

    conn.close()

    # Summary
    print("=" * 60)
    print(f"SUMMARY: {tests_passed} passed, {tests_failed} failed")
    print("=" * 60)

    if tests_failed == 0:
        print("✓ All tests passed! Database is valid.")
        return 0
    else:
        print("✗ Some tests failed. Please review the database.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
