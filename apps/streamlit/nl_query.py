import streamlit as st

# 使用新版 SDK：pip install google-genai
try:
    from google import genai
except Exception:
    genai = None

st.set_page_config(page_title="Neo4j 前端：Cypher 编写助手（Tabs）", page_icon="🕸️", layout="wide")
st.title("Neo4j 前端：Cypher 编写助手（Tabs 布局）")
st.caption("API 仅从 st.secrets 读取，模型固定为 gemini-2.5-flash-preview-05-20。")

# ---- Schema（来自 import.cypher 的结构摘要）----
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

MODEL_ID = "gemini-2.5-flash-preview-05-20"

def _read_secret_api_key() -> str | None:
    try:
        return st.secrets["GOOGLE_GENAI_API_KEY"]
    except Exception:
        return None

def generate_cypher_with_gemini(nl_prompt: str, schema_text: str) -> str:
    if genai is None:
        raise RuntimeError("未安装 google-genai，请先执行：pip install google-genai")
    api_key = _read_secret_api_key()
    if not api_key:
        raise RuntimeError("缺少 Gemini API Key，请在 .streamlit/secrets.toml 配置 GOOGLE_GENAI_API_KEY")

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

    # 仅设置最必要参数：降低随机性 + 合理长度
    config = genai.types.GenerateContentConfig(
        temperature=0.1,
        max_output_tokens=1024,
    )

    resp = client.models.generate_content(
        model=MODEL_ID,
        contents=prompt,
        config=config,
    )

    text = getattr(resp, "output_text", None) or getattr(resp, "text", "") or ""
    text = text.strip()

    # 清理可能出现的代码围栏
    if text.startswith("```"):
        lines = [ln for ln in text.strip("`").splitlines()]
        if lines and lines[0].strip().lower() == "cypher":
            lines = lines[1:]
        text = "\n".join(lines).strip()

    return text

# ---- Tabs：仅保留 方式二 ----
tab_assist, tab_query = st.tabs(["🧠 Cypher 编写助手", "🔎 查询执行（占位）"])

with tab_assist:
    st.subheader("🧠 Cypher 编写助手")
    st.caption("输入自然语言，基于给定 Schema 生成 Cypher。")

    with st.expander("查看当前 Schema"):
        st.code(SCHEMA.strip(), language="text")

    # 仅从 secrets 读取 API Key，并显示状态
    api_key_present = _read_secret_api_key() is not None
    if api_key_present:
        st.success("已从 st.secrets 读取 Gemini API Key")
    else:
        st.warning("未读取到 Gemini API Key。请在 .streamlit/secrets.toml 配置 GOOGLE_GENAI_API_KEY")

    st.text_input("模型（只读）", value=MODEL_ID, disabled=True)

    nl_prompt = st.text_area("自然语言需求", height=160, placeholder="例如：查找名称包含 'BHP' 的 Name 节点，并返回节点与数量")
    gen_btn = st.button("生成 Cypher")

    if gen_btn:
        try:
            cypher = generate_cypher_with_gemini(nl_prompt, SCHEMA)
            st.session_state["generated_cypher"] = cypher
            st.success("已生成 Cypher")
            st.code(cypher, language="cypher")
        except Exception as e:
            st.error(f"生成失败：{e}")

    if "generated_cypher" in st.session_state and not gen_btn:
        st.subheader("上次生成的 Cypher")
        st.code(st.session_state["generated_cypher"], language="cypher")

with tab_query:
    st.subheader("🔎 查询执行（占位）")
    st.caption("后续可接入 Neo4j 执行与 JSON 序列化。当前为占位展示。")
    st.text_area("Cypher（占位）", height=120, placeholder="MATCH (n) RETURN n LIMIT 10")
    st.button("执行（禁用）", disabled=True)