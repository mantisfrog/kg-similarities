"""
Project-wide path config and small helper.
Keep scripts path-free: `from config import ...`.
"""

from pathlib import Path
import os

# --- Project roots ---
BASE_DIR: Path = Path(__file__).resolve().parent.parent
DATA_DIR: Path = BASE_DIR / "data"

# --- Raw data directories ---
RAW_DIR: Path = DATA_DIR / "raw"
DEPOSIT_DIR: Path = RAW_DIR / "deposit"
COMPANY_DIR: Path = RAW_DIR / "company"
SHP_DIR: Path = RAW_DIR / "shp"

# Company subdirs
BLOOMBERG_DIR: Path = COMPANY_DIR / "bloomberg"
LINKEDIN_DIR: Path = COMPANY_DIR / "linkedin_unpickled"
MS_DIR: Path = COMPANY_DIR / "modern_slavery"

# --- Processed / master / graph ---
PROCESSED_DIR: Path = DATA_DIR / "processed"
MASTER_DIR: Path = DATA_DIR / "master"
GRAPH_DIR: Path = DATA_DIR / "graph"

# --- Common inputs (deposits & projects) ---
MASTER_PROJECT_CSV: Path = MASTER_DIR / "ProjectData_Master.csv"
MINERAL_DEPOSITS_JSON: Path = DEPOSIT_DIR / "MineralDeposits.json"
MAJOR_RESOURCE_PROJECTS_CSV: Path = DEPOSIT_DIR / "MajorResourceProjects.csv"
MINE_VIEW_CSV: Path = DEPOSIT_DIR / "MineView.csv"
COMMODITY_MAPPING_CSV: Path = DEPOSIT_DIR / "commodity_mapping.csv"
CATEGORIZATION_CSV: Path = DEPOSIT_DIR / "categorization.csv"
COMPANY_TSV: Path = COMPANY_DIR / "COMPANY_202509.tsv"

# --- Common outputs ---
PROCESSED_DEPOSITS_CSV: Path = PROCESSED_DIR / "MineralDeposits.csv"
NODE_COMMODITY_CSV: Path = GRAPH_DIR / "node_Commodity.csv"
MERGED_COMPANY_CSV: Path = PROCESSED_DIR / "CompanyData_Merged.csv"
MASTER_COMPANY_CSV: Path = MASTER_DIR / "CompanyData_Master.csv"

# --- Shapefiles ---
PROVINCES_SHP: Path = SHP_DIR / "116823_AGP_2018" / "ProvinceFullExtent.shp"
STATES_SHP: Path = SHP_DIR / "STE_2021_AUST_SHP_GDA94" / "STE_2021_AUST_GDA94.shp"

# --- Neo4j / Cypher ---
CYPHER_FILE: Path = BASE_DIR / "cypher" / "import.cypher"
NEO4J_URI: str = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER: str = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD: str = os.getenv("NEO4J_PASSWORD", "neo4jroot")

# --- Bloomberg / LinkedIn / MS specific (additional coverage) ---
BLOOMBERG_TICKER_DES_CSV: Path = BLOOMBERG_DIR / "TICKER_NAME_DES.csv"
BLOOMBERG_ICB_DIR: Path = BLOOMBERG_DIR / "ICB"
BLOOMBERG_BICS_DIR: Path = BLOOMBERG_DIR / "BICS"

LINKEDIN_MINING_CSV: Path = LINKEDIN_DIR / "linkedin_mining_companies.csv"
MS_CLEANED_CSV: Path = MS_DIR / "cleaned_ms_statements.csv"

# Intermediate/aux files for company name processing
FORMER_NAMES_CSV: Path = PROCESSED_DIR / "former_names.csv"
NODE_COMPANY_CSV: Path = GRAPH_DIR / "node_Company.csv"

# Consolidated outputs
PROCESSED_BLOOMBERG_CSV: Path = PROCESSED_DIR / "Bloomberg_Companies.csv"
MATCHES_SCORES_GRAPH_CSV: Path = PROCESSED_DIR / "Matches_Scores_Graph.csv"

# Manual aliasing and change logs
MANUAL_ALIASES_CSV: Path = COMPANY_DIR / "manual_add_company_names.csv"
MATCHES_SCORES_BB_MS_LOG_CSV: Path = PROCESSED_DIR / "Matches_Scores_Bloomberg_to_MS_Log.csv"
MATCHES_SCORES_MERGED_LI_LOG_CSV: Path = PROCESSED_DIR / "Matches_Scores_Merged_to_Linkedin_Log.csv"
CHANGES_LOG_CSV: Path = MASTER_DIR / "ACN_Merge_Changes_Log.csv"

# --- Small helpers ---
def ensure_parent(path: Path) -> Path:
    """Create parent directories before writing."""
    path.parent.mkdir(parents=True, exist_ok=True)
    return path