import streamlit as st

# Import Gemini SDK (pip install google-genai)
try:
    from google import genai
except Exception:
    genai = None

# Basic Streamlit page config
st.set_page_config(page_title="Neo4j Frontend: Cypher Assistant (Tabs)", page_icon="🕸️", layout="wide")
st.title("Neo4j Frontend: Cypher Assistant (Tabs)")
st.caption("API key is read from st.secrets only. Model is fixed to gemini-2.5-flash-preview-05-20.")

# Static schema context shown to the user
SCHEMA = """
Graph schema (simplified):

Nodes:
- Name(nameID UNIQUE, nameText)
- Company(companyID UNIQUE, companyName)
- Commodity(commodityID UNIQUE, commoditySymbol, commodityDesc, commodityGroup)
- Deposit(depositID UNIQUE, eno:int, state, location, operatingStatus, geologicAge,
          depositModelEnvironment, depositModelGroup, depositModelType, provinces,
          igneous, metallogenic, sedimentary, tectonic)

Relationships:
- (Name)-[:REFERS_TO]->(Deposit)
- (Deposit)-[:HAS {role}]->(Commodity)
- (Company)-[:OWNS]->(Deposit)
"""

# Fixed Gemini model
MODEL_ID = "gemini-2.5-flash-preview-05-20"

def _read_secret_api_key() -> str | None:
    """Read the Gemini API key strictly from Streamlit secrets."""
    try:
        return st.secrets["GOOGLE_GENAI_API_KEY"]
    except Exception:
        return None

def generate_cypher_with_gemini(nl_prompt: str, schema_text: str) -> str:
    """Generate a Cypher query from natural language using Gemini."""
    if genai is None:
        raise RuntimeError("google-genai is not installed. Run: pip install google-genai")
    api_key = _read_secret_api_key()
    if not api_key:
        raise RuntimeError("Missing API key. Configure GOOGLE_GENAI_API_KEY in .streamlit/secrets.toml")

    client = genai.Client(api_key=api_key)

    sys_hint = (
        "You are a Cypher assistant for Neo4j 5. Respond with a single Cypher query only, "
        "no explanations, no markdown fences.\n"
        "Use the provided schema. Prefer read-only queries unless the user explicitly requests writes.\n"
        "Use property names exactly as in schema (e.g., Name.nameText, Company.companyName, "
        "Commodity.commoditySymbol/commodityDesc/commodityGroup, Deposit.* fields).\n"
        "If filtering by substring, use CONTAINS; for case-insensitive use toLower().\n"
        "Limit results with LIMIT when reasonable."
    )
    prompt = f"{sys_hint}\n\nSchema:\n{schema_text}\n\nUser request:\n{nl_prompt}\n\nReturn only the Cypher."

    # Minimal and valuable generation settings for code-like outputs
    generation_config = genai.types.GenerateContentConfig(
        temperature=0.1,        # lower randomness for more deterministic code
        max_output_tokens=1024, # reasonable cap for a single query
    )

    resp = client.models.generate_content(
        model=MODEL_ID,
        contents=prompt,
        generation_config=generation_config,
    )

    text = getattr(resp, "text", "") or getattr(resp, "output_text", "") or ""
    text = text.strip()

    # Remove potential code fences if present
    if text.startswith("```"):
        lines = [ln for ln in text.strip("`").splitlines()]
        if lines and lines[0].strip().lower() == "cypher":
            lines = lines[1:]
        text = "\n".join(lines).strip()

    return text

# Tabs layout: keep only the "Method 2" UI
tab_assist, tab_query = st.tabs(["Cypher Assistant", "Query Runner (placeholder)"])

with tab_assist:
    st.subheader("Cypher Assistant")
    st.caption("Enter natural language and generate a Cypher query using the provided schema.")

    with st.expander("View current schema"):
        st.code(SCHEMA.strip(), language="text")

    api_key_present = _read_secret_api_key() is not None
    if api_key_present:
        st.success("Gemini API key found in st.secrets.")
    else:
        st.warning("Gemini API key not found. Please set GOOGLE_GENAI_API_KEY in .streamlit/secrets.toml.")

    st.text_input("Model (read-only)", value=MODEL_ID, disabled=True)

    nl_prompt = st.text_area(
        "Natural language request",
        height=160,
        placeholder="e.g., Find Name nodes whose nameText contains 'BHP' and return the nodes and the count",
    )
    gen_btn = st.button("Generate Cypher")

    if gen_btn:
        try:
            cypher = generate_cypher_with_gemini(nl_prompt, SCHEMA)
            st.session_state["generated_cypher"] = cypher
            st.success("Cypher generated.")
            st.code(cypher, language="cypher")
        except Exception as e:
            st.error(f"Generation failed: {e}")

    if "generated_cypher" in st.session_state and not gen_btn:
        st.subheader("Last generated Cypher")
        st.code(st.session_state["generated_cypher"], language="cypher")

with tab_query:
    st.subheader("Query Runner (placeholder)")
    st.caption("This tab can be wired to Neo4j execution and JSON serialization later.")
    st.text_area("Cypher (placeholder)", height=120, placeholder="MATCH (n) RETURN n LIMIT 10")
    st.button("Execute (disabled)", disabled=True)