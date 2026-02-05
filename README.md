# EU Adaptation Mission Query Tool

A natural language query interface for exploring EU Adaptation Mission projects and participating organizations, built using the NL2SQL pattern with Claude AI.

## Overview

This tool provides an intuitive way to query data on EU-funded climate adaptation projects and participating organizations through natural language questions. It converts your questions into SQL queries, executes them against a SQLite database, and presents results in a user-friendly web interface.

**Dataset:**
- **908 participants** from 40 countries
- **46 funded projects** (2021-2029)
- **€430.89M** total participant funding
- **€484.45M** total project budget

## Architecture

### Pattern: NL2SQL with Claude
```
User Question → Claude LLM (OpenRouter) → SQL Query → SQLite Database → Results → Natural Language Summary
```

**Design rationale:** This approach costs ~£0.001-0.002 per query because data stays in SQLite rather than passing entire datasets through the LLM context window.

### File Structure

```
adaptation_mission_projects/
├── app.py                                      # Streamlit web interface
├── load_data.py                                # Data loading pipeline
├── test_database.py                            # Database validation tests
├── requirements.txt                            # Python dependencies
├── .env                                        # API key (create this)
├── .gitignore                                  # Git exclusions
├── adaptation_mission.db                       # SQLite database (generated)
├── adaptation_mission_participants.xlsx        # Source data
├── mission_funded_projects_with_details.xlsx   # Source data
└── README.md                                   # This file
```

## Database Schema

### Table: `participants`
Organizations participating in EU Adaptation Mission projects.

**Columns:**
- `participant_id` (INTEGER) - Unique ID
- `participations` (INTEGER) - Number of projects participated in (1-10)
- `legal_name` (TEXT) - Official organization name
- `participant_code` (TEXT) - EU portal URL identifier
- `participant_type` (TEXT) - PUB, PRC, HES, REC, OTH
- `net_eu_contribution_euro` (REAL) - Total EU funding received
- `funding_programme` (TEXT) - H2020 or HORIZON
- `country_territory` (TEXT) - Country/region
- `city` (TEXT) - City name
- `nuts_1_name`, `nuts_2_name`, `nuts_3_name` (TEXT) - EU geographic codes (contains "-" for non-EU countries)

### Table: `projects`
EU-funded adaptation mission projects.

**Columns:**
- `project_id` (INTEGER) - Unique ID
- `acronym` (TEXT) - Short project name (e.g., REGILIENCE)
- `title` (TEXT) - Full project title
- `project_url` (TEXT) - CORDIS project page URL
- `project_start_date` (DATE) - Start date
- `project_end_date` (DATE) - End date
- `total_budget_euro` (REAL) - Total project budget
- `eu_contribution_euro` (REAL) - EU contribution
- `funding_programme` (TEXT) - H2020, HORIZON, or Horizon Europe
- `topic_code` (TEXT) - Call topic code
- `type_of_action` (TEXT) - CSA or IA
- `category` (TEXT) - Support to regions or Cross cutting
- **`climate_risks` (TEXT)** - Semicolon-separated list (e.g., "Drought; Flooding; Extreme heat")
- **`main_themes` (TEXT)** - Semicolon-separated list (e.g., "Governance; Infrastructure; Water management")
- **`regions` (TEXT)** - Semicolon-separated list of project regions
- `coordinator` (TEXT) - Project coordinator "Organization, Country"
- `coordinator_org` (TEXT) - Coordinator organization name (for joining)
- `coordinator_country` (TEXT) - Coordinator country
- `website` (TEXT) - Project website URL

### Join Capability

Projects can be linked to their coordinator's details:
```sql
SELECT p.*, part.*
FROM projects p
LEFT JOIN participants part ON p.coordinator_org = part.legal_name
```

**Note:** This join only connects coordinators, not all project participants. The participants table shows aggregate data per organization across all their project participations.

## Setup & Installation

### Prerequisites
- Python 3.9+
- OpenRouter API key (get one at [openrouter.ai](https://openrouter.ai))

### Installation Steps

1. **Clone or navigate to the directory:**
   ```bash
   cd /Users/willdavies/Documents/GitHub/tools/adaptation_mission_projects
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Create `.env` file with your API key:**
   ```bash
   echo 'OPENROUTER_API_KEY="your-key-here"' > .env
   ```

4. **Generate the database (if needed):**
   ```bash
   python load_data.py
   ```
   This loads both XLSX files and creates `adaptation_mission.db`

5. **Run validation tests (optional):**
   ```bash
   python test_database.py
   ```

6. **Launch the app:**
   ```bash
   streamlit run app.py
   ```

The app will open in your browser at `http://localhost:8501`

## Usage Examples

### Participant Queries
- "Which countries have the most participants?"
- "List all research organizations in Germany"
- "Organizations participating in multiple projects"
- "Total EU funding by participant type"

### Project Queries
- "What are the top 5 projects by budget?"
- "Projects addressing sea level rise"
- "Show me projects in Spain"
- "When do most projects end?"
- "Compare H2020 vs Horizon Europe projects"

### Cross-Table Queries (with joins)
- "Which universities coordinate projects?"
- "Italian-led projects addressing drought"
- "Projects coordinated by public bodies"

### Complex Queries
- "Projects addressing both drought and flooding"
- "Regions with the most project activity"
- "Average project budget by climate risk"
- "How many projects address water management?"

## Key Features

### ✅ Multi-Value Field Support
The tool handles semicolon-separated lists in `climate_risks`, `main_themes`, and `regions` columns using LIKE queries with case-insensitive matching.

### ✅ Smart Error Handling
When queries return no results, the tool suggests:
- Common climate risks and themes in the database
- Top countries with participants
- Formatting tips for multi-value field searches

### ✅ Join Queries
Automatically detects when coordinator details are needed and performs SQL joins between projects and participants tables.

### ✅ Professional UI
- Climate-themed design (green color scheme)
- Euro-formatted currency values
- Responsive tables with hover effects
- CSV export capability
- Collapsible SQL viewer

### ✅ Natural Language Summaries
Results include AI-generated descriptions explaining key findings for policy analysts.

## Design Decisions & Implementation Notes

### 1. Single Combined Tool vs. Separate Tools
**Decision:** Single tool for both datasets
**Rationale:** Enables cross-table queries and provides unified interface for exploring relationships between projects and participants.

### 2. Multi-Value Field Handling
**Decision:** Keep as semicolon-separated text, use LIKE queries
**Rationale:** Simpler implementation than normalizing to separate tables. Trade-off: can't easily count unique values, but pattern matching works well for most queries.

**Example:**
```sql
-- Correct
WHERE climate_risks LIKE '%Drought%'

-- Wrong (will not match)
WHERE climate_risks = 'Drought'
```

### 3. Coordinator Join Limitation
**Important:** The join only connects project **coordinators** to the participants table, not all project members.

- ✅ **Possible:** "Who coordinated project X?"
- ❌ **Not possible:** "Which organizations participated in project X?"

This is a data limitation - the source files don't include a junction table mapping all participants to their projects.

### 4. NUTS Codes for Non-EU Countries
NUTS columns contain "-" for non-EU countries (e.g., Albania, Andorra, Australia).

For EU-only queries:
```sql
WHERE nuts_1_name != '-'
```

### 5. Case Sensitivity in Searches
The system uses `COLLATE NOCASE` for case-insensitive LIKE queries, so users can search "drought" or "Drought" and get matches.

### 6. Currency Display
- All monetary values stored in euros (not thousands)
- Large values displayed in millions for readability: "€12.85M" instead of "€12,850,322.50"
- SQL queries use: `ROUND(euro_value / 1000000.0, 2) as value_millions`

## System Prompt Engineering

The tool includes an extensive system prompt (400+ lines) with:
- Complete schema descriptions for both tables
- 9 critical rules for SQL generation
- 12+ few-shot examples covering common query patterns
- Temporal handling rules (filtering vs. grouping by time)
- Multi-value field query patterns
- Join logic guidelines

This ensures Claude generates accurate, optimized SQL queries.

## Testing & Validation

The `test_database.py` script runs 15 validation tests:
1. Row counts (908 participants, 46 projects)
2. No NULLs in critical columns
3. Coordinator join capability (~52 matches)
4. Multi-value fields contain semicolons
5. Date ranges valid (2021-2029)
6. Budget logic (total ≥ EU contribution)
7. Index existence
8. Participant type diversity (5 types)
9. Geographic coverage (40 countries)
10. Funding programme diversity

All tests currently passing ✓

## Deployment Considerations

### Streamlit Community Cloud
- Requires GitHub repository (can be private)
- API key stored in Streamlit secrets: `OPENROUTER_API_KEY`
- One private app allowed on free tier
- Simply connect your GitHub repo and configure secrets

### Cost Estimates
- ~£0.001-0.002 per query using Claude Sonnet 4 via OpenRouter
- Much cheaper than passing full datasets through LLM context window
- 100 queries ≈ £0.10-0.20

## Development Session Summary

**Date:** 2026-02-05

**Objective:** Create an adaptation mission project query tool following the CatchQuery architecture.

**Approach:**
1. Explored existing CatchQuery tool to understand patterns
2. Analyzed two XLSX source files (participants and projects)
3. Designed two-table schema with join capability via coordinator names
4. Implemented data loading pipeline with coordinator parsing
5. Created Streamlit UI with comprehensive system prompt
6. Built validation test suite
7. Successfully generated and validated database

**Key Challenges Solved:**
- Coordinator name parsing (uppercase matching for joins)
- Multi-value field handling (LIKE queries)
- NUTS code interpretation for non-EU countries
- SQLite date function syntax
- Case-insensitive search support

**Files Generated:**
- `load_data.py` (235 lines)
- `app.py` (600+ lines)
- `test_database.py` (200+ lines)
- `requirements.txt`
- `.gitignore`
- Implementation plan: `/Users/willdavies/.claude/plans/swift-jingling-popcorn.md`

## Related Tools

This tool follows the same architecture as:
- **CatchQuery** - UK fish landings query tool
- **EmissionsQuery** (planned) - Global emissions data query tool

All three tools share:
- NL2SQL pattern with Claude via OpenRouter
- SQLite backend with indexed columns
- Streamlit web interface
- Comprehensive system prompts with domain-specific rules
- Cost-effective query-per-request model

## Data Sources

- **EU Missions Programme**: Climate adaptation projects funded under Horizon Europe
- **CORDIS**: EU research project database
- **Horizon Results Platform**: Project outcomes and details

## License & Disclaimers

This tool uses AI to generate database queries, which may occasionally produce inaccurate results. Please verify important findings against the source data.

Data sourced from EU public databases. For official project information, consult:
- [EU Missions Programme](https://ec.europa.eu/info/research-and-innovation/funding/funding-opportunities/funding-programmes-and-open-calls/horizon-europe/eu-missions-horizon-europe_en)
- [CORDIS Project Database](https://cordis.europa.eu/)

---

**Created by:** AdaptMEL
**Contact:** [Your contact information]

