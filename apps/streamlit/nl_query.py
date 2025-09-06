import streamlit as st
import os
import random
import json
from time import perf_counter
from neo4j import GraphDatabase
from neo4j.graph import Node, Relationship, Path as Neo4jPath

try:
    from google import genai
except Exception:
    genai = None

def get_secret(name: str, default: str | None = None):
    val = os.getenv(name)
    if val:
        return val
    try:
        return st.secrets[name]
    except Exception:
        return default

st.set_page_config(page_title="Neo4j AI Assistant", page_icon="🕸️", layout="wide")

NEO4J_URI = get_secret("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = get_secret("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = get_secret("NEO4J_PASSWORD", "neo4jroot")

SCHEMA = """
Graph schema (simplified):
Nodes:
- Name(nameID UNIQUE, nameText)
- Company(companyID UNIQUE, companyName)
- Commodity(commodityID UNIQUE, commoditySymbol, commodityDesc, commodityGroup)
- Deposit(depositID UNIQUE, eno:int, state, location, operatingStatus, geologicAge, depositModelEnvironment, depositModelGroup, depositModelType, provinces, igneous, metallogenic, sedimentary, tectonic)
Relationships:
- (Name)-[:REFERS_TO]->(Deposit)
- (Deposit)-[:HAS {role}]->(Commodity)
- (Company)-[:OWNS]->(Deposit)
"""
MODEL_ID = "gemini-2.5-flash-preview-05-20"
SPINNER_MESSAGES = [
    "Contacting the AI overlords...", "Translating human thoughts into Cypher...", "Warming up the graph traversal engines...",
    "Asking the model nicely for a query...", "Reticulating splines... and nodes...", "Consulting the Neo4j oracles...",
    "Polishing the Cypher query...", "Don't worry, the AI is friendly... for now.",
]

@st.cache_resource
def get_neo4j_driver():
    try:
        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        driver.verify_connectivity()
        return driver
    except Exception:
        return None

def _serialize_value(v):
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
    with driver.session() as session:
        result = session.run(query, params or {})
        records = [r.data() for r in result]
        serialized_records = [_serialize_value(rec) for rec in records]
        summary = result.consume()
        counters = getattr(summary, "counters", None)
        counters_dict = getattr(counters, "__dict__", {}) if counters else {}
        return {"records": serialized_records, "summary": counters_dict}

def generate_cypher_with_gemini(nl_prompt: str, schema_text: str) -> str:
    if genai is None:
        raise RuntimeError("google-genai is not installed. Run: pip install google-genai")
    api_key = get_secret("GOOGLE_GENAI_API_KEY")
    if not api_key:
        raise RuntimeError("Missing API key. Set env GOOGLE_GENAI_API_KEY or configure it in .streamlit/secrets.toml")
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
        lines = [ln for ln in text.strip("`").splitlines() if ln.strip().lower() != "cypher"]
        text = "\n".join(lines).strip()
    return text

st.title("Neo4j AI Assistant")

driver = get_neo4j_driver()
api_key_probe = get_secret("GOOGLE_GENAI_API_KEY")

tab_assist, tab_runner = st.tabs(["📝 Cypher Generator", "🔍 AI-Powered Query"])

with tab_assist:
    st.subheader("Generate Cypher from Natural Language")
    with st.expander("View current schema"):
        st.code(SCHEMA.strip(), language="text")

    nl_prompt_assist = st.text_area(
        "Natural language request",
        height=160,
        placeholder="e.g., Return the company nodes that include BHP and Rio Tinto.",
        key="nl_assist",
    )
    gen_btn = st.button("Generate Cypher", key="assist_gen_btn")

    if gen_btn:
        t0 = perf_counter()
        try:
            spinner_message = random.choice(SPINNER_MESSAGES)
            with st.spinner(spinner_message):
                t1 = perf_counter()
                cypher = generate_cypher_with_gemini(nl_prompt_assist, SCHEMA)
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

with tab_runner:
    st.subheader("Query with Natural Language")
    with st.expander("View current schema"):
        st.code(SCHEMA.strip(), language="text")

    nl_prompt_runner = st.text_area(
        "Natural language request",
        height=160,
        placeholder="e.g., Which company owns the deposit named 'Golden Grove'?",
        key="nl_runner",
    )
    run_btn = st.button("Run AI Query", key="runner_run_btn")

    if run_btn:
        if not driver:
            st.error("Cannot run query: Neo4j connection failed. Check console for details.")
            st.stop()
        t0 = perf_counter()
        try:
            spinner_message = random.choice(SPINNER_MESSAGES)
            with st.spinner(spinner_message):
                t1 = perf_counter()
                cypher_query = generate_cypher_with_gemini(nl_prompt_runner, SCHEMA)
                t2 = perf_counter()
                result = run_cypher_query(driver, cypher_query)
                t3 = perf_counter()
            st.success("AI query executed successfully.")
            with st.expander("View Generated Cypher"):
                st.code(cypher_query, language="cypher")
            st.json(result)
            total_ms = int((t3 - t0) * 1000)
            model_ms = int((t2 - t1) * 1000)
            db_ms = int((t3 - t2) * 1000)
            st.caption(f"Total: {total_ms} ms  ·  AI generation: {model_ms} ms  ·  Database query: {db_ms} ms")
            st.balloons()
        except Exception as e:
            st.error(f"Query execution failed: {e}")

st.divider()
status_col1, status_col2, status_col3 = st.columns(3)
with status_col1:
    st.caption(f"🧠 Model: {MODEL_ID}")
with status_col2:
    if api_key_probe:
        st.caption("🟢 Gemini API Key: Found")
    else:
        st.caption("🔴 Gemini API Key: Not Found")
with status_col3:
    if driver:
        st.caption("🟢 Neo4j Connection: Active")
    else:
        st.caption("🔴 Neo4j Connection: Failed")
