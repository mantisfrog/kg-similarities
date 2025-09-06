import streamlit as st
import random
import json
from time import perf_counter
from neo4j import GraphDatabase
from neo4j.graph import Node, Relationship, Path as Neo4jPath

# Import Gemini SDK (pip install google-genai)
try:
    from google import genai
except Exception:
    genai = None

# --- Page and Neo4j Configuration ---
st.set_page_config(page_title="Neo4j AI Assistant", page_icon="🕸️", layout="wide")
NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "neo4jroot"

# --- Static Content ---
SCHEMA = """
Graph schema (simplified):
Nodes:
- Name(nameID UNIQUE, nameText)
- Company(companyID UNIQUE, companyName)
- Commodity(commodityID UNIQUE, commoditySymbol, commodityDesc, commodityGroup)
- Deposit(depositID UNIQUE, eno:int, state, location, operatingStatus, geologicAge, depositModelEnvironment, depositModelGroup, depositModelType, provinces, igneous, metallogenic, sedimentary, tectonic)
Relationships:
- (Name)-[:REFERS_TO]->(Deposit)
- (Deposit)-[:HAS {role}]->(Commodody)
- (Company)-[:OWNS]->(Deposit)
"""
MODEL_ID = "gemini-2.5-flash-preview-05-20"
SPINNER_MESSAGES = [
    "Contacting the AI overlords...", "Translating human thoughts into Cypher...", "Warming up the graph traversal engines...",
    "Asking the model nicely for a query...", "Reticulating splines... and nodes...", "Consulting the Neo4j oracles...",
    "Polishing the Cypher query...", "Don't worry, the AI is friendly... for now.",
]

# --- Neo4j Helper Functions ---
@st.cache_resource
def get_neo4j_driver():
    """Create and cache a Neo4j driver instance."""
    try:
        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        driver.verify_connectivity()
        return driver
    except Exception as e:
        st.error(f"Neo4j connection failed: {e}")
        return None

def _serialize_value(v):
    """Recursively serialize Neo4j graph objects to JSON-friendly formats."""
    if isinstance(v, (Node, Relationship)):
        return dict(v)
    if isinstance(v, Neo4jPath):
        return [dict(p) for p in v]
    if isinstance(v, list):
        return [_serialize_value(item) for item in v]
    if isinstance(v, dict):
        return {k: _serialize_value(val) for k, val in v.items()}
    return v

def run_cypher_query(driver, query, params=None):
    """Execute a Cypher query and return serialized results."""
    with driver.session() as session:
        result = session.run(query, params or {})
        records = [r.data() for r in result]
        serialized_records = [_serialize_value(rec) for rec in records]
        summary = result.consume()
        return {
            "records": serialized_records,
            "summary": summary.counters.__dict__
        }

# --- Gemini Helper Function ---
def generate_cypher_with_gemini(nl_prompt: str, schema_text: str) -> str:
    """Generate a Cypher query from natural language using Gemini."""
    if genai is None:
        raise RuntimeError("google-genai is not installed. Run: pip install google-genai")
    try:
        api_key = st.secrets["GOOGLE_GENAI_API_KEY"]
    except Exception:
        raise RuntimeError("Missing API key. Configure GOOGLE_GENAI_API_KEY in .streamlit/secrets.toml")

    client = genai.Client(api_key=api_key)
    sys_hint = (
        "You are a Cypher assistant for Neo4j 5. Respond with a single Cypher query only, no explanations, no markdown fences.\n"
        "Use the provided schema. Prefer read-only queries unless the user explicitly requests writes.\n"
        "Use property names exactly as in schema (e.g., Name.nameText, Company.companyName).\n"
        "If filtering by substring, use CONTAINS; for case-insensitive use toLower(). Limit results with LIMIT when reasonable."
    )
    prompt = f"{sys_hint}\n\nSchema:\n{schema_text}\n\nUser request:\n{nl_prompt}\n\nReturn only the Cypher."
    config = genai.types.GenerateContentConfig(temperature=0.2, max_output_tokens=512)
    resp = client.models.generate_content(model=MODEL_ID, contents=prompt, config=config)
    text = getattr(resp, "text", "") or getattr(resp, "output_text", "") or ""
    text = text.strip()
    if text.startswith("```"):
        lines = [ln for ln in text.strip("`").splitlines() if not ln.strip().lower() == "cypher"]
        text = "\n".join(lines).strip()
    return text

# --- Streamlit UI ---
st.title("Neo4j AI Assistant")
tab_assist, tab_query = st.tabs(["Cypher Assistant", "Query Runner"])

# --- Cypher Assistant Tab ---
with tab_assist:
    st.subheader("Generate Cypher from Natural Language")
    with st.expander("View current schema"):
        st.code(SCHEMA.strip(), language="text")

    if "GOOGLE_GENAI_API_KEY" in st.secrets:
        st.success("Gemini API key found in st.secrets.")
    else:
        st.warning("Gemini API key not found. Please set GOOGLE_GENAI_API_KEY in .streamlit/secrets.toml.")

    st.text_input("Model (read-only)", value=MODEL_ID, disabled=True, key="assist_model")
    nl_prompt = st.text_area("Natural language request", height=160, placeholder="e.g., Find 5 companies and the deposits they own.")
    gen_btn = st.button("Generate Cypher", key="assist_gen_btn")

    if gen_btn:
        t0 = perf_counter()
        try:
            spinner_message = random.choice(SPINNER_MESSAGES)
            with st.spinner(spinner_message):
                t1 = perf_counter()
                cypher = generate_cypher_with_gemini(nl_prompt, SCHEMA)
                t2 = perf_counter()
            st.session_state["generated_cypher"] = cypher
            st.success("Cypher generated.")
            st.code(cypher, language="cypher")
            total_ms = int((t2 - t0) * 1000)
            model_ms = int((t2 - t1) * 1000)
            st.caption(f"Total elapsed: {total_ms} ms  ·  Model generation time: {model_ms} ms")
            st.balloons()
        except Exception as e:
            st.error(f"Generation failed: {e}")

    if "generated_cypher" in st.session_state and not gen_btn:
        st.subheader("Last generated Cypher")
        st.code(st.session_state["generated_cypher"], language="cypher")

# --- Query Runner Tab ---
with tab_query:
    st.subheader("Execute a Cypher Query")
    driver = get_neo4j_driver()
    if driver:
        st.success("Successfully connected to Neo4j.")
    else:
        st.stop()

    cypher_input = st.text_area("Cypher Query", height=160, placeholder="MATCH (n) RETURN n LIMIT 5")
    params_input = st.text_area("Parameters (JSON format)", height=80, placeholder='{"name": "BHP"}')
    run_btn = st.button("Execute Query", key="query_run_btn")

    if run_btn:
        t0 = perf_counter()
        try:
            params = json.loads(params_input) if params_input.strip() else {}
            with st.spinner("Executing query in Neo4j..."):
                t1 = perf_counter()
                result = run_cypher_query(driver, cypher_input, params)
                t2 = perf_counter()
            st.success("Query executed.")
            st.json(result)
            total_ms = int((t2 - t0) * 1000)
            query_ms = int((t2 - t1) * 1000)
            st.caption(f"Total elapsed: {total_ms} ms  ·  Database query time: {query_ms} ms")
            st.balloons()
        except json.JSONDecodeError:
            st.error("Invalid JSON in parameters. Please check the format.")
        except Exception as e:
            st.error(f"Query failed: {e}")