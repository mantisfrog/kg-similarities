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

try:
    import openai
except Exception:
    openai = None

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

GEMINI_MODEL_ID = get_secret("GEMINI_MODEL_ID", "gemini-2.5-flash-preview-05-20")
OPENAI_MODEL_ID = get_secret("OPENAI_MODEL_ID", "gpt-5-mini-2025-08-07")
# OPENAI_MODEL_ID = get_secret("OPENAI_MODEL_ID", "gpt-5-mini-2025-08-07")

# The initial model selection logic is now handled interactively in the status bar.
# The following lines are replaced by the new implementation at the bottom of the file.
# # Determine which model to use based on available API keys
# def get_active_model():
#     openai_api_key = get_secret("OPENAI_API_KEY")
#     gemini_api_key = get_secret("GOOGLE_GENAI_API_KEY")
    
#     if openai_api_key and (openai is not None):
#         return {"provider": "openai", "model_id": OPENAI_MODEL_ID}
#     elif gemini_api_key and (genai is not None):
#         return {"provider": "gemini", "model_id": GEMINI_MODEL_ID}
#     else:
#         return None

# active_model = get_active_model()
# MODEL_PROVIDER = active_model["provider"] if active_model else None
# MODEL_ID = active_model["model_id"] if active_model else "No model available"

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

def generate_cypher_with_gemini(nl_prompt: str, schema_text: str) -> dict:
    """
    Generates Cypher using Gemini and returns both raw and processed text.
    """
    if genai is None:
        raise RuntimeError("google-genai is not installed. Run: pip install google-genai")
    api_key = get_secret("GOOGLE_GENAI_API_KEY")
    if not api_key:
        raise RuntimeError("Missing API key. Set env GOOGLE_GENAI_API_KEY or configure it in .streamlit/secrets.toml")
    client = genai.Client(api_key=api_key)
    sys_hint = (
        "You are a Cypher assistant for Neo4j 5.\n"
        "Use the provided schema.\n"
        "Use property names exactly as in schema (e.g., Name.nameText, Company.companyName).\n"
        "Use CONTAINS for companyName and commodityDesc.\n"
        "For case-insensitive use toLower().\n"
        "Use c,d,n,comp as aliases for Commodity, Deposit, Name, Company respectively.\n"
        "Use p for path variables.\n"
        "For paths connecting two nodes via common intermediates, use patterns like (n1)-->(intermediate)<--(n2).\n"
        "For complex paths through multiple nodes, break down into clear segments with aliases.\n"
        "Check your results before outputting."
    )
    prompt = f"{sys_hint}\n\nSchema:\n{schema_text}\n\nUser request:\n{nl_prompt}\n\nReturn only the Cypher."
    config = genai.types.GenerateContentConfig(temperature=0.1, max_output_tokens=512)
    resp = client.models.generate_content(model=GEMINI_MODEL_ID, contents=prompt, config=config)
    
    raw_text = getattr(resp, "text", "") or getattr(resp, "output_text", "") or ""
    
    processed_text = raw_text.strip()
    if processed_text.startswith("```"):
        lines = [ln for ln in processed_text.strip("`").splitlines() if ln.strip().lower() != "cypher"]
        processed_text = "\n".join(lines).strip()
        
    return {"raw_text": raw_text, "cypher": processed_text}

def generate_cypher_with_openai(nl_prompt: str, schema_text: str) -> dict:
    """
    Generates Cypher using OpenAI and returns both raw and processed text.
    """
    if openai is None:
        raise RuntimeError("openai is not installed. Run: pip install openai")
    api_key = get_secret("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("Missing API key. Set env OPENAI_API_KEY or configure it in .streamlit/secrets.toml")
    
    openai.api_key = api_key
    
    sys_hint = (
        "You are a Cypher assistant for Neo4j 5.\n"
        "Use the provided schema.\n"
        "Use property names exactly as in schema (e.g., Name.nameText, Company.companyName).\n"
        "Use CONTAINS for companyName and commodityDesc.\n"
        "For case-insensitive use toLower().\n"
        "Use c,d,n,comp as aliases for Commodity, Deposit, Name, Company respectively.\n"
        "Use p for path variables.\n"
        "For paths connecting two nodes via common intermediates, use patterns like (n1)-->(intermediate)<--(n2).\n"
        "For complex paths through multiple nodes, break down into clear segments with aliases.\n"
        "Check your results before outputting."
    )
    
    prompt = f"Schema:\n{schema_text}\n\nUser request:\n{nl_prompt}\n\nReturn only the Cypher."
    
    response = openai.chat.completions.create(
        model=OPENAI_MODEL_ID,
        messages=[
            {"role": "system", "content": sys_hint},
            {"role": "user", "content": prompt}
        ],
        temperature=1
    )
    
    raw_text = response.choices[0].message.content
    
    processed_text = raw_text.strip()
    if processed_text.startswith("```"):
        lines = [ln for ln in processed_text.strip("`").splitlines() if ln.strip().lower() != "cypher"]
        processed_text = "\n".join(lines).strip()
        
    return {"raw_text": raw_text, "cypher": processed_text}

def generate_cypher(nl_prompt: str, schema_text: str) -> dict:
    """
    Routes to the appropriate LLM based on available API keys and preferences.
    """
    if MODEL_PROVIDER == "openai":
        return generate_cypher_with_openai(nl_prompt, schema_text)
    elif MODEL_PROVIDER == "gemini":
        return generate_cypher_with_gemini(nl_prompt, schema_text)
    else:
        raise RuntimeError("No valid API keys found for either OpenAI or Gemini")

def generate_similarity_explanation(data_for_llm: str) -> str:
    """
    Generates a similarity explanation using the selected LLM.
    """
    prompt = f"""
You are an expert data scientist specializing in geological data. Your task is to calculate the similarity between two deposits based on their shared commodities using the Weighted Jaccard Similarity index.

Here is the data for the two deposits:
---
{data_for_llm}
---

Follow these instructions precisely:
1.  **Identify the commodities** for each deposit from the data provided.
2.  **Assign weights** to each commodity based on its role:
    - `Primary` role has a weight of 1.0.
    - `Secondary` role has a weight of 0.5.
    - Any other role has a weight of 0.1.
3.  **Calculate the Weighted Jaccard Similarity**. The formula is:
    J_w(A, B) = sum(min(w_i_A, w_i_B) for i in intersection(A, B)) / sum(max(w_i_A, w_i_B) for i in union(A, B))
    Where `w_i_A` is the weight of commodity `i` in deposit A (0 if not present) and `w_i_B` is the weight of commodity `i` in deposit B (0 if not present).
4.  **Show your work step-by-step**:
    - List the commodities and their weights for each deposit.
    - Identify the intersection and union of the commodities.
    - Calculate the numerator (sum of minimum weights for intersecting commodities).
    - Calculate the denominator (sum of maximum weights for union commodities).
    - Calculate the final similarity score.
5.  **Provide a concluding summary** of the similarity score.

Present the entire response clearly.
"""
    if MODEL_PROVIDER == "openai":
        if openai is None:
            raise RuntimeError("OpenAI library not installed.")
        openai.api_key = get_secret("OPENAI_API_KEY")
        response = openai.chat.completions.create(
            model=MODEL_ID,
            messages=[{"role": "user", "content": prompt}],
            temperature=1
        )
        return response.choices[0].message.content
    elif MODEL_PROVIDER == "gemini":
        if genai is None:
            raise RuntimeError("Google GenAI library not installed.")
        api_key = get_secret("GOOGLE_GENAI_API_KEY")
        client = genai.Client(api_key=api_key)
        config = genai.types.GenerateContentConfig(temperature=0.1)
        resp = client.models.generate_content(model=MODEL_ID, contents=prompt, config=config)
        return getattr(resp, "text", "") or getattr(resp, "output_text", "") or ""
    else:
        raise RuntimeError("No valid LLM provider configured.")

st.title("Neo4j AI Assistant")

driver = get_neo4j_driver()
gemini_api_key = get_secret("GOOGLE_GENAI_API_KEY")
openai_api_key = get_secret("OPENAI_API_KEY")

# --- Model Selection UI & State Management ---
OPENAI_DISPLAY_NAME = f"OpenAI ({OPENAI_MODEL_ID})"
GEMINI_DISPLAY_NAME = f"Gemini ({GEMINI_MODEL_ID})"

model_options = []
if openai_api_key and openai is not None:
    model_options.append(OPENAI_DISPLAY_NAME)
if gemini_api_key and genai is not None:
    model_options.append(GEMINI_DISPLAY_NAME)

# Initialize session state for the selected model if it doesn't exist
if "selected_model" not in st.session_state and model_options:
    # Default to OpenAI if available, otherwise the first option
    st.session_state.selected_model = OPENAI_DISPLAY_NAME if OPENAI_DISPLAY_NAME in model_options else model_options[0]

if model_options:
    col1, _ = st.columns([1, 2])  # Use columns to constrain selectbox width
    with col1:
        # The selectbox now reads from and writes to st.session_state
        st.selectbox(
            "Select LLM Model",
            model_options,
            key="selected_model", # Bind the selectbox to a key in session_state
        )
    
    # Update global variables based on the persistent session state
    if st.session_state.selected_model == OPENAI_DISPLAY_NAME:
        MODEL_PROVIDER = "openai"
        MODEL_ID = OPENAI_MODEL_ID
    else:  # Gemini
        MODEL_PROVIDER = "gemini"
        MODEL_ID = GEMINI_MODEL_ID
else:
    MODEL_PROVIDER = None
    MODEL_ID = "No model available"
    st.warning("No LLM API keys found. Please configure `OPENAI_API_KEY` or `GOOGLE_GENAI_API_KEY` to enable AI features.")

# --- Custom Tab Navigation ---
# Initialize active_tab in session state if it doesn't exist
if "active_tab" not in st.session_state:
    st.session_state.active_tab = "Cypher Generator"

# Create custom tab buttons
col1, col2, col3 = st.columns(3)
with col1:
    cypher_gen_selected = st.button(
        "📝 Cypher Generator", 
        use_container_width=True,
        type="primary" if st.session_state.active_tab == "Cypher Generator" else "secondary"
    )
    if cypher_gen_selected:
        st.session_state.active_tab = "Cypher Generator"
        st.rerun()

with col2:
    ai_query_selected = st.button(
        "🔍 AI-Powered Query", 
        use_container_width=True,
        type="primary" if st.session_state.active_tab == "AI-Powered Query" else "secondary"
    )
    if ai_query_selected:
        st.session_state.active_tab = "AI-Powered Query"
        st.rerun()

with col3:
    similarity_selected = st.button(
        "🧮 Similarity Calculator", 
        use_container_width=True,
        type="primary" if st.session_state.active_tab == "Similarity Calculator" else "secondary"
    )
    if similarity_selected:
        st.session_state.active_tab = "Similarity Calculator"
        st.rerun()

# Create a horizontal line to separate tabs from content
st.markdown("---")

# Conditional rendering based on active tab
if st.session_state.active_tab == "Cypher Generator":
    st.subheader("Generate Cypher from Natural Language")
    with st.expander("View current schema"):
        st.code(SCHEMA.strip(), language="text")

    with st.form("assist_form"):
        nl_prompt_assist = st.text_input(
            "Natural language request",
            placeholder="e.g., Return the company nodes that include BHP and Rio Tinto.",
            key="nl_assist",
        )
        gen_btn = st.form_submit_button("Generate Cypher")

    if gen_btn:
        t0 = perf_counter()
        try:
            spinner_message = random.choice(SPINNER_MESSAGES)
            with st.spinner(spinner_message):
                t1 = perf_counter()
                response_data = generate_cypher(nl_prompt_assist, SCHEMA)
                cypher = response_data["cypher"]
                raw_response = response_data["raw_text"]
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

elif st.session_state.active_tab == "AI-Powered Query":
    st.subheader("Query with Natural Language")
    with st.expander("View current schema"):
        st.code(SCHEMA.strip(), language="text")

    with st.form("runner_form"):
        nl_prompt_runner = st.text_input(
            "Natural language request",
            placeholder="e.g., Which company owns the deposit named 'Golden Grove'?",
            key="nl_runner",
        )
        run_btn = st.form_submit_button("Run AI Query")

    if run_btn:
        if not driver:
            st.error("Cannot run query: Neo4j connection failed. Check console for details.")
            st.stop()
        t0 = perf_counter()
        try:
            spinner_message = random.choice(SPINNER_MESSAGES)
            with st.spinner(spinner_message):
                t1 = perf_counter()
                response_data = generate_cypher(nl_prompt_runner, SCHEMA)
                cypher_query = response_data["cypher"]
                raw_response = response_data["raw_text"]
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

elif st.session_state.active_tab == "Similarity Calculator":
    st.subheader("Calculate Deposit Similarity")
    with st.expander("View current schema"):
        st.code(SCHEMA.strip(), language="text")

    with st.form("similarity_form"):
        col1, col2 = st.columns(2)
        with col1:
            deposit1_eno = st.text_input(
                "Deposit 1 (eno)",
                placeholder="Enter 6-digit eno",
                key="deposit1_eno",
            )
        with col2:
            deposit2_eno = st.text_input(
                "Deposit 2 (eno)",
                placeholder="Enter 6-digit eno",
                key="deposit2_eno",
            )
        
        calc_btn = st.form_submit_button("Calculate Similarity")

    if calc_btn:
        if not driver:
            st.error("Cannot run query: Neo4j connection failed.")
        elif not MODEL_PROVIDER:
            st.error("Cannot run calculation: LLM not configured.")
        elif deposit1_eno and deposit2_eno:
            try:
                # Convert eno to integer for the query
                eno1 = int(deposit1_eno)
                eno2 = int(deposit2_eno)

                with st.spinner(f"Fetching data and calculating similarity for deposits {eno1} and {eno2}..."):
                    # 1. Run Cypher query to get commodities for both deposits
                    query = """
                    MATCH (d1:Deposit {eno: $eno1})-[r1:HAS]->(c1:Commodity)
                    RETURN d1.eno AS eno, r1.role AS role, c1.commoditySymbol AS symbol
                    UNION ALL
                    MATCH (d2:Deposit {eno: $eno2})-[r2:HAS]->(c2:Commodity)
                    RETURN d2.eno AS eno, r2.role AS role, c2.commoditySymbol AS symbol
                    """
                    params = {"eno1": eno1, "eno2": eno2}
                    query_result = run_cypher_query(driver, query, params)

                    if not query_result["records"]:
                        st.error("Could not find data for one or both of the specified deposits.")
                    else:
                        # Display raw query result first
                        st.subheader("Raw Data from Neo4j")
                        st.json(query_result["records"])

                        # 2. Format data for the LLM
                        data_for_llm = ""
                        for record in query_result["records"]:
                            data_for_llm += f"Deposit eno: {record['eno']}, Commodity: {record['symbol']}, Role: {record['role']}\n"

                        # 3. Call LLM to get the explanation
                        explanation = generate_similarity_explanation(data_for_llm)

                        # 4. Display the LLM result
                        st.subheader("Similarity Calculation by LLM")
                        st.markdown(explanation)
                        st.success("Similarity calculation complete!")

            except ValueError:
                st.error("Invalid eno. Please enter valid 6-digit numbers.")
            except Exception as e:
                st.error(f"An error occurred: {e}")
        else:
            st.warning("Please enter both deposit eno numbers.")

st.divider()

# --- Status Bar ---
status_col1, status_col2, status_col3, status_col4 = st.columns(4)

with status_col1:
    if MODEL_PROVIDER:
        st.caption(f"🧠 Using: {MODEL_ID}")
    else:
        st.caption("🧠 Model: Not available")

with status_col2:
    if gemini_api_key:
        st.caption("🟢 Gemini API Key: Found")
    else:
        st.caption("🔴 Gemini API Key: Not Found")
with status_col3:
    if openai_api_key:
        st.caption("🟢 OpenAI API Key: Found")
    else:
        st.caption("🔴 OpenAI API Key: Not Found")
with status_col4:
    if driver:
        st.caption("🟢 Neo4j Connection: Active")
    else:
        st.caption("🔴 Neo4j Connection: Failed")
