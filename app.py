"""
EU Adaptation Mission Query Interface

A web interface for querying EU adaptation mission projects and participants.
Run with: streamlit run app.py
"""

import streamlit as st
import sqlite3
import pandas as pd
import os
import time
import base64
from dotenv import load_dotenv

# Configuration
DB_PATH = "adaptation_mission.db"

# Load environment variables from .env file
load_dotenv()

# Get API key from environment variable
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

if not OPENROUTER_API_KEY:
    st.error("""
    **Missing API Key**

    Please set the OPENROUTER_API_KEY environment variable:

    ```bash
    export OPENROUTER_API_KEY="your-key-here"
    ```

    Then restart the application.
    """)
    st.stop()

SCHEMA_DESCRIPTION = """
DATABASE SCHEMA:

TABLE: participants
Represents organizations participating in EU Adaptation Mission projects.
- participant_id (INTEGER): Unique ID
- participations (INTEGER): Number of projects this organization participates in (1-10)
- legal_name (TEXT): Official organization name (uppercase)
- participant_code (TEXT): EU portal URL identifier
- participant_type (TEXT): Organization type
    Values: 'PUB' (public body), 'PRC' (private company), 'HES' (higher education),
            'OTH' (other), 'REC' (research)
- net_eu_contribution_euro (REAL): Total EU funding received (euros)
- funding_programme (TEXT): 'H2020' or 'HORIZON'
- country_territory (TEXT): Country/region (e.g., 'Spain', 'Italy', 'Greece')
- city (TEXT): City name
- nuts_1_name, nuts_2_name, nuts_3_name (TEXT): EU NUTS geographic codes
    Note: Contains "-" for non-EU countries

TABLE: projects
Represents EU-funded adaptation mission projects.
- project_id (INTEGER): Unique ID
- acronym (TEXT): Short project name (e.g., 'REGILIENCE', 'TransformAr')
- title (TEXT): Full project title
- project_url (TEXT): CORDIS project page URL
- project_start_date (DATE): Start date (YYYY-MM-DD format, 2021-2029 range)
- project_end_date (DATE): End date
- total_budget_euro (REAL): Total project budget in euros
- eu_contribution_euro (REAL): EU contribution in euros
- hrp_result_url (TEXT): Horizon Results Platform link
- funding_programme (TEXT): 'H2020', 'HORIZON', or 'Horizon Europe'
- topic_code (TEXT): Call topic code (e.g., 'LC-GD-1-3-2020')
- type_of_action (TEXT): 'CSA' (coordination/support) or 'IA' (innovation action)
- mission_relevance_flag (TEXT): Always 'mission funded'
- category (TEXT): 'Support to regions' or 'Cross cutting'
- climate_risks (TEXT): Semicolon-separated list of climate risks
    Examples: "Drought; Flooding; Extreme heat; Sea level rise; Wildfires"
- main_themes (TEXT): Semicolon-separated list of adaptation themes
    Examples: "Governance; Infrastructure; Water management; Ecosystems and nature-based solutions"
- regions (TEXT): Semicolon-separated list of regions
    Examples: "Valencia (Spain); Galicia Region (Spain); City of Egaleo (Greece)"
- coordinator (TEXT): Project coordinator "Organization, Country"
- coordinator_org (TEXT): Coordinator organization name (for joining)
- coordinator_country (TEXT): Coordinator country
- website (TEXT): Project website URL

RELATIONSHIP:
To find the coordinator's details from participants table:
  JOIN participants ON projects.coordinator_org = participants.legal_name

Note: The participants table shows AGGREGATE data per organization across all projects.
The "participations" column indicates how many projects each organization is involved in.
"""

SYSTEM_PROMPT = f"""You convert natural language questions about EU Adaptation Mission projects into SQL queries.

{SCHEMA_DESCRIPTION}

=== CRITICAL RULES ===

RULE 1 - MULTI-VALUE FIELD QUERIES:
The climate_risks, main_themes, and regions columns contain semicolon-separated lists.
To search within these fields, use LIKE with wildcards and COLLATE NOCASE for case-insensitive matching:

CORRECT:
  WHERE climate_risks LIKE '%Drought%'
  WHERE main_themes LIKE '%Water management%'
  WHERE regions LIKE '%Spain%'
  WHERE climate_risks LIKE '%drought%' COLLATE NOCASE

WRONG (will not match):
  WHERE climate_risks = 'Drought'

When counting distinct values within these fields, you cannot easily unnest them.
Instead, count projects that mention the term:
  SELECT COUNT(*) FROM projects WHERE climate_risks LIKE '%Flooding%'

RULE 2 - MONETARY VALUES:
- All monetary values are in EUROS (not thousands)
- Display with appropriate formatting: ROUND(euro_value, 2)
- Use clear aliases: total_budget_millions, avg_contribution_euro
- For millions: ROUND(euro_value / 1000000.0, 2) as value_millions
- For totals: ROUND(SUM(euro_column), 2) as total_euros

RULE 3 - DATE HANDLING:
- Dates are stored as DATE type (YYYY-MM-DD)
- For year filtering: WHERE strftime('%Y', project_start_date) = '2021'
- For date ranges: WHERE project_start_date BETWEEN '2021-01-01' AND '2022-12-31'
- For currently active projects: WHERE project_start_date <= date('now') AND project_end_date >= date('now')

RULE 4 - GEOGRAPHIC QUERIES:
- NUTS columns may contain "-" for non-EU countries - filter these out:
  WHERE nuts_1_name != '-'
- Country names are in various formats: 'Spain', 'Italy', 'Greece', etc.
- For EU-only queries: WHERE nuts_1_name != '-'

RULE 5 - JOINING TABLES:
Only join when the user explicitly asks about coordinator details or wants to combine
participant and project information:
  SELECT p.acronym, p.total_budget_euro, part.participant_type, part.city
  FROM projects p
  LEFT JOIN participants part ON p.coordinator_org = part.legal_name

Do NOT join if only querying projects or only querying participants.

RULE 6 - URL COLUMNS:
- project_url, participant_code, hrp_result_url, website are URLs
- Do NOT include in SELECT unless specifically requested
- Use for reference but not for grouping/aggregation

RULE 7 - AGGREGATION DEFAULTS:
- Default LIMIT: 20 rows unless specified otherwise
- Always include ORDER BY for TOP N queries
- Use ROUND() for all numeric outputs to 2 decimal places
- Include context columns (acronym for projects, legal_name for participants)

RULE 8 - NULL HANDLING:
- topic_code has 3 NULLs
- hrp_result_url has 3 NULLs
- website has 1 NULL
- Use WHERE column IS NOT NULL when relevant

RULE 9 - OUTPUT FORMAT:
- Return ONLY the SQL query, no explanation
- Use valid SQLite syntax
- Use meaningful aliases
- Do NOT include markdown code fences

=== EXAMPLES ===

Q: "What are the top 5 projects by budget?"
```sql
SELECT acronym, title,
       ROUND(total_budget_euro / 1000000.0, 2) as budget_millions,
       coordinator
FROM projects
ORDER BY total_budget_euro DESC
LIMIT 5
```

Q: "Which countries have the most participants?"
```sql
SELECT country_territory,
       COUNT(*) as participant_count,
       ROUND(SUM(net_eu_contribution_euro) / 1000000.0, 2) as total_funding_millions
FROM participants
WHERE country_territory IS NOT NULL
GROUP BY country_territory
ORDER BY participant_count DESC
LIMIT 10
```

Q: "List all projects addressing drought"
```sql
SELECT acronym, title, coordinator,
       ROUND(total_budget_euro / 1000000.0, 2) as budget_millions,
       project_start_date
FROM projects
WHERE climate_risks LIKE '%Drought%'
ORDER BY total_budget_euro DESC
```

Q: "How many projects address water management?"
```sql
SELECT COUNT(*) as project_count,
       ROUND(SUM(total_budget_euro) / 1000000.0, 2) as total_budget_millions
FROM projects
WHERE main_themes LIKE '%Water management%'
```

Q: "Show projects in Spain with their coordinator details"
```sql
SELECT p.acronym, p.title,
       p.coordinator,
       part.participant_type,
       part.city,
       ROUND(p.total_budget_euro / 1000000.0, 2) as budget_millions
FROM projects p
LEFT JOIN participants part ON p.coordinator_org = part.legal_name
WHERE p.regions LIKE '%Spain%'
ORDER BY p.total_budget_euro DESC
```

Q: "Which organizations coordinate multiple projects?"
```sql
SELECT coordinator_org, coordinator_country,
       COUNT(*) as projects_coordinated,
       ROUND(SUM(total_budget_euro) / 1000000.0, 2) as total_budget_millions
FROM projects
GROUP BY coordinator_org, coordinator_country
HAVING COUNT(*) > 1
ORDER BY projects_coordinated DESC
```

Q: "Average project budget by funding programme"
```sql
SELECT funding_programme,
       COUNT(*) as project_count,
       ROUND(AVG(total_budget_euro) / 1000000.0, 2) as avg_budget_millions,
       ROUND(SUM(eu_contribution_euro) / 1000000.0, 2) as total_eu_contribution_millions
FROM projects
GROUP BY funding_programme
ORDER BY project_count DESC
```

Q: "List research organizations (REC) participating in projects"
```sql
SELECT legal_name, country_territory, participations,
       ROUND(net_eu_contribution_euro, 2) as contribution_euro
FROM participants
WHERE participant_type = 'REC'
ORDER BY participations DESC, net_eu_contribution_euro DESC
LIMIT 20
```

Q: "Projects starting in 2022 addressing flooding"
```sql
SELECT acronym, title, coordinator,
       project_start_date,
       ROUND(total_budget_euro / 1000000.0, 2) as budget_millions
FROM projects
WHERE strftime('%Y', project_start_date) = '2022'
  AND climate_risks LIKE '%Flooding%'
ORDER BY project_start_date
```

Q: "Total EU funding by country"
```sql
SELECT country_territory,
       COUNT(*) as participant_count,
       ROUND(SUM(net_eu_contribution_euro) / 1000000.0, 2) as total_eu_funding_millions
FROM participants
GROUP BY country_territory
ORDER BY total_eu_funding_millions DESC
LIMIT 15
```

Q: "Projects coordinated by universities"
```sql
SELECT p.acronym, p.title,
       p.coordinator,
       ROUND(p.total_budget_euro / 1000000.0, 2) as budget_millions
FROM projects p
LEFT JOIN participants part ON p.coordinator_org = part.legal_name
WHERE part.participant_type = 'HES'
ORDER BY p.total_budget_euro DESC
```

Q: "Italian-led projects addressing drought"
```sql
SELECT acronym, title, coordinator,
       ROUND(total_budget_euro / 1000000.0, 2) as budget_millions
FROM projects
WHERE coordinator_country LIKE '%Italy%'
  AND climate_risks LIKE '%Drought%'
ORDER BY total_budget_euro DESC
```
"""


import requests

def get_sql_from_llm(question: str):
    """Get SQL query from Claude via OpenRouter"""
    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "anthropic/claude-sonnet-4",
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": question}
                ],
                "max_tokens": 512,
            }
        )
        response.raise_for_status()
        data = response.json()
        sql = data["choices"][0]["message"]["content"].strip()
        # Remove markdown code fences if present
        sql = sql.replace("```sql", "").replace("```", "").strip()
        return sql
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 401:
            st.error("Invalid API key. Please check OPENROUTER_API_KEY environment variable.")
        elif e.response.status_code == 429:
            st.error("Rate limit exceeded. Please try again in a moment.")
        else:
            st.error(f"API error ({e.response.status_code}): {e}")
        st.stop()
    except Exception as e:
        st.error(f"Unexpected error: {e}")
        st.stop()

def run_query(sql: str, db_path: str):
    """Execute SQL and return DataFrame"""
    try:
        conn = sqlite3.connect(db_path)
        df = pd.read_sql(sql, conn)
        conn.close()
        return df, None
    except Exception as e:
        return None, str(e)

def generate_table_description(question: str, sql: str, df: pd.DataFrame) -> str:
    """Generate natural language description of query results"""
    try:
        sample_data = df.head(5).to_dict('records')

        description_prompt = f"""Given this user question: "{question}"

And this SQL query: {sql}

Sample results (first 5 rows): {sample_data}
Total rows: {len(df)}

Provide a clear, 1-2 sentence description explaining what this table shows and key findings.
Be conversational. Focus on interpreting data for EU climate adaptation policy analysts."""

        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "anthropic/claude-sonnet-4",
                "messages": [{"role": "user", "content": description_prompt}],
                "max_tokens": 256,
            }
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"].strip()
    except Exception:
        return f"Table showing {len(df)} results for your query."


def analyze_empty_results(sql: str, question: str, db_path: str) -> dict:
    """Analyze why query returned empty results and suggest alternatives"""
    try:
        conn = sqlite3.connect(db_path)
        suggestions = []

        # Check if querying projects table
        if "FROM projects" in sql.upper():
            # Check for climate risk or theme queries
            if "climate_risks LIKE" in sql or "main_themes LIKE" in sql or "regions LIKE" in sql:
                suggestions.append("**Tip**: Multi-value fields use semicolon-separated lists. Make sure your search term matches the exact capitalization in the data.")
                suggestions.append("Common climate risks: Drought, Flooding, Extreme heat, Sea level rise, Wildfires, Heavy precipitation")
                suggestions.append("Common themes: Governance, Infrastructure, Water management, Ecosystems and nature-based solutions")

            # Check available climate risks
            sample_risks = conn.execute("SELECT DISTINCT climate_risks FROM projects WHERE climate_risks IS NOT NULL LIMIT 5").fetchall()
            if sample_risks:
                suggestions.append(f"Example climate risks in database: {sample_risks[0][0][:100]}...")

        # Check if querying participants table
        if "FROM participants" in sql.upper():
            # Check available countries
            top_countries = conn.execute("SELECT country_territory, COUNT(*) as cnt FROM participants GROUP BY country_territory ORDER BY cnt DESC LIMIT 5").fetchall()
            if top_countries:
                country_list = ", ".join([f"{c[0]} ({c[1]})" for c in top_countries])
                suggestions.append(f"Top countries with participants: {country_list}")

        conn.close()

        return {
            'suggestions': suggestions
        }

    except Exception as e:
        return {
            'suggestions': [f"Unable to analyze query: {str(e)}"]
        }


# Streamlit UI
st.set_page_config(page_title="EU Adaptation Mission Query", layout="wide")

# Add background image with opacity
def get_base64_image(image_path):
    """Convert image to base64 for CSS embedding"""
    with open(image_path, "rb") as img_file:
        return base64.b64encode(img_file.read()).decode()

# Get base64 of background image
bg_image = get_base64_image("Gemini_Generated_Image_stduqnstduqnstdu.png")

st.markdown(f"""
<style>
    /* Hide Streamlit header bar */
    header[data-testid="stHeader"] {{
        visibility: hidden;
        height: 0;
    }}

    /* Main app background with faded image */
    .stApp {{
        background-image: linear-gradient(rgba(255, 255, 255, 0.85), rgba(255, 255, 255, 0.85)),
                          url("data:image/png;base64,{bg_image}");
        background-size: cover;
        background-position: center;
        background-repeat: no-repeat;
        background-attachment: fixed;
    }}

    /* Professional typography */
    body, p, div, h1, h2, h3, h4, h5, h6, span, label, input, button {{
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    }}

    /* Title styling */
    h1 {{
        color: #2E7D32 !important;
        font-weight: 500 !important;
        letter-spacing: -0.3px !important;
        font-size: 2.2rem !important;
        margin-bottom: 0.5rem !important;
    }}

    /* Subtitle and body text */
    p, div {{
        line-height: 1.6 !important;
    }}

    /* Button styling */
    div.stButton > button {{
        background-color: #F1F8E9;
        color: #2E7D32;
        border: 1px solid #A5D6A7;
        border-radius: 4px;
        padding: 10px 20px;
        font-size: 14px;
        font-weight: 500;
        transition: all 0.2s ease;
        box-shadow: 0 1px 2px rgba(0,0,0,0.05);
    }}
    div.stButton > button:hover {{
        background-color: #DCEDC8;
        border-color: #2E7D32;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }}

    /* Primary button styling */
    div.stButton > button[kind="primary"] {{
        background-color: #2E7D32;
        color: white;
        border: none;
    }}
    div.stButton > button[kind="primary"]:hover {{
        background-color: #1B5E20;
    }}
</style>
""", unsafe_allow_html=True)

st.title("EU Adaptation Mission Query Tool")
st.markdown("Explore EU-funded climate adaptation Mission Projects and their participants")

# Introductory paragraph
st.markdown("""
This tool provides access to data on EU Adaptation Mission projects and participating organisations.
At time of publication of this tool (May 2025), the dataset includes 46 funded projects and 908 organisations
from across Europe and beyond, covering climate adaptation initiatives addressing risks like flooding, drought,
extreme heat, and sea level rise. Query by project characteristics, climate risks, geographic regions, funding
details, or organisation types.
""")

st.markdown("")  # Add spacing

# Main interface with form for Enter key support
with st.form(key="query_form", clear_on_submit=False):
    question = st.text_input(
        "Your question:",
        placeholder="e.g., Which projects address flooding and sea level rise?",
    )

    col1, col2 = st.columns([6, 1])
    with col1:
        run_button = st.form_submit_button("Query", type="primary", use_container_width=False)
    with col2:
        reset_button = st.form_submit_button("Reset", use_container_width=True)

# Handle reset
if reset_button:
    st.rerun()

if run_button and question and not reset_button:
    start_time = time.time()
    status_placeholder = st.empty()
    status_placeholder.info("Processing your query...")

    try:
        sql = get_sql_from_llm(question)

        df, error = run_query(sql, DB_PATH)
        elapsed = time.time() - start_time
        status_placeholder.empty()

        if error:
            st.error(f"Query error: {error}")
        elif df is not None:
            # Check if results are empty (0 rows) or contain only NULL aggregations (1 row with all NULLs)
            is_empty = len(df) == 0
            is_null_aggregation = (len(df) == 1 and df.select_dtypes(include=['number']).isna().all().all())

            if is_empty or is_null_aggregation:
                st.warning("No results found for your query.")

                # Analyze why and provide suggestions
                analysis = analyze_empty_results(sql, question, DB_PATH)

                if analysis['suggestions']:
                    st.info("**Suggestions:**")
                    for suggestion in analysis['suggestions']:
                        st.markdown(f"- {suggestion}")

                # Still show the SQL
                with st.expander("View Generated SQL", expanded=True):
                    st.code(sql, language="sql")

                st.caption(f"Query executed in {elapsed:.2f} seconds")
            else:
                # Normal results display
                # Transform column names to Title Case
                def format_column_name(col_name: str) -> str:
                    """Transform snake_case to Title Case"""
                    special_cases = {
                        'eu': 'EU',
                        'euros': 'Euros',
                        'euro': '(€)',
                        'millions': '(Millions)',
                    }

                    words = col_name.replace('_', ' ').split()
                    formatted_words = []

                    for word in words:
                        if word.lower() in special_cases:
                            formatted_words.append(special_cases[word.lower()])
                        else:
                            formatted_words.append(word.capitalize())

                    return ' '.join(formatted_words)

                # Transform column names
                df.columns = [format_column_name(col) for col in df.columns]

                # Display results heading
                st.subheader("Results")

                # Format numeric columns
                for col in df.columns:
                    if df[col].dtype in ['float64', 'float32']:
                        if 'euro' in col.lower() or '€' in col.lower() or 'budget' in col.lower() or 'contribution' in col.lower() or 'funding' in col.lower():
                            df[col] = df[col].apply(lambda x: f"€{x:,.2f}" if pd.notna(x) else "")
                        else:
                            df[col] = df[col].apply(lambda x: f"{x:,.2f}" if pd.notna(x) else "")

                # Apply Pandas Styler for enhanced table aesthetics
                styled_df = df.style.set_properties(**{
                    'background-color': '#E8F5E9',
                    'color': '#1B5E20',
                    'border-color': '#4CAF50',
                    'padding': '10px'
                }).set_table_styles([
                    {'selector': 'th', 'props': [
                        ('background-color', '#2E7D32'),
                        ('color', 'white'),
                        ('font-weight', 'bold'),
                        ('padding', '12px')
                    ]},
                    {'selector': 'tr:nth-child(even)', 'props': [
                        ('background-color', '#E8F5E9')
                    ]},
                    {'selector': 'tr:nth-child(odd)', 'props': [
                        ('background-color', 'white')
                    ]},
                    {'selector': 'tr:hover', 'props': [
                        ('background-color', '#C8E6C9')
                    ]},
                    {'selector': 'table', 'props': [
                        ('border-radius', '8px'),
                        ('overflow', 'hidden')
                    ]}
                ])

                st.dataframe(styled_df, use_container_width=True, hide_index=True)

                # Generate and display description
                with st.spinner("Generating description..."):
                    description = generate_table_description(question, sql, df)
                st.markdown(f"**About this data**: {description}")

                st.caption(f"Query executed in {elapsed:.2f} seconds")
                st.markdown("")  # Add spacing

                # SQL display in collapsible expander (after results)
                with st.expander("View Generated SQL", expanded=False):
                    st.code(sql, language="sql")

                st.markdown("")  # Add spacing

                # Option to download
                csv = df.to_csv(index=False)
                st.download_button(
                    "Download CSV",
                    csv,
                    "query_results.csv",
                    "text/csv",
                )

    except Exception as e:
        st.error(f"Error: {e}")

# Footer
st.markdown("---")

footer_col1, footer_col2 = st.columns([2, 1])

with footer_col1:
    st.markdown("**Data sources:**")
    st.markdown(
        "- [EU Mission for Climate Adaptation Project Portfolio](https://dashboard.tech.ec.europa.eu/qs_digit_dashboard_mt/public/sense/app/c575fc3f-9de4-4659-9134-e3d0289ae3e9/sheet/2ea6dbc9-79f4-4c68-8480-78b47880c01d/state/analysis)"
    )
    st.markdown(
        "- [Mission Project Catalogue 2025](https://mission-adaptation-portal.ec.europa.eu/mission-project-catalogue_en)"
    )

with footer_col2:
    st.markdown("**Created by**")
    try:
        st.image("AdaptMEL_logo.png", width=120)
    except Exception:
        st.markdown("*AdaptMEL*")

# Disclaimers
st.markdown("")  # Spacing
st.markdown("""
<p style="font-size: 0.85rem; color: #6c757d; text-align: center; margin-top: 2rem;">
This tool uses AI to generate database queries, which may occasionally produce inaccurate results.
Please verify important findings against the source data.
</p>
""", unsafe_allow_html=True)
