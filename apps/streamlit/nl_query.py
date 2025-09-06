import streamlit as st

st.set_page_config(page_title="Neo4j 前端原型：模式区分演示", page_icon="🕸️", layout="wide")

st.title("Neo4j 前端原型：模式区分演示")
st.caption("本页面仅用于展示不同的“模式区分”UI 方案，无任何后台功能。")

# 简单样式用于“卡片”展示
st.markdown("""
<style>
.card {
  padding: 1rem;
  border: 1px solid #e9ecef;
  border-radius: 0.5rem;
  background: #f8f9fa;
}
.card h3 { margin-top: 0; }
.card.assistant { background: #f5f8ff; border-color: #d6e4ff; }
.card.query { background: #f6fff6; border-color: #d2f4d2; }
</style>
""", unsafe_allow_html=True)

# 方式一：侧边栏模式切换（单选）
st.sidebar.header("方式一：侧边栏模式切换")
sidebar_mode = st.sidebar.radio(
    "选择模式",
    options=["🧠 Cypher 编写助手", "🔎 查询执行"],
    index=0,
    key="sidebar_mode",
)
st.subheader("方式一：侧边栏单选")
st.info(f"当前选择：{sidebar_mode}（演示用，不触发任何功能）")

# 方式二：主区标签页（Tabs）
st.subheader("方式二：主区顶部标签页")
tab_assist, tab_query = st.tabs(["🧠 Cypher 编写助手", "🔎 查询执行"])

with tab_assist:
    st.markdown('<div class="card assistant">', unsafe_allow_html=True)
    st.markdown("### 🧠 Cypher 编写助手")
    st.write("在此输入自然语言需求（演示占位）：")
    st.text_area("自然语言输入", height=120, placeholder="例如：查找名称包含 'BHP' 的节点")
    st.code("MATCH (n:Name) WHERE n.nameText CONTAINS 'BHP' RETURN n LIMIT 25", language="cypher")
    st.button("生成 Cypher（演示）", disabled=True)
    st.button("执行查询（演示）", disabled=True)
    st.markdown('</div>', unsafe_allow_html=True)

with tab_query:
    st.markdown('<div class="card query">', unsafe_allow_html=True)
    st.markdown("### 🔎 查询执行")
    st.write("在此输入 Cypher（演示占位）：")
    st.text_area("Cypher 输入", height=120, placeholder="MATCH (n) RETURN n LIMIT 10")
    st.text_area("参数 JSON（可选）", height=80, placeholder='{"term": "BHP"}')
    st.button("执行（演示）", disabled=True)
    st.json({"query": "...", "columns": ["..."], "data": [{"row": ["..."]}]})
    st.markdown('</div>', unsafe_allow_html=True)

# 方式三：左右“卡片”对比布局
st.subheader("方式三：左右卡片区分")
col1, col2 = st.columns(2)
with col1:
    st.markdown('<div class="card assistant">', unsafe_allow_html=True)
    st.markdown("### 🧠 Cypher 编写助手")
    st.caption("适用于将自然语言转换为 Cypher。")
    st.text_area("自然语言", height=100, placeholder="例如：统计项目数量…")
    st.button("仅生成（演示）", disabled=True)
    st.markdown('</div>', unsafe_allow_html=True)
with col2:
    st.markdown('<div class="card query">', unsafe_allow_html=True)
    st.markdown("### 🔎 查询执行")
    st.caption("适用于直接输入并运行 Cypher。")
    st.text_area("Cypher", height=100, placeholder="MATCH (n) RETURN count(n)")
    st.button("仅执行（演示）", disabled=True)
    st.markdown('</div>', unsafe_allow_html=True)

# 方式四：折叠面板（Expanders）
st.subheader("方式四：折叠面板（可按需展开其一）")
with st.expander("🧠 Cypher 编写助手"):
    st.write("用于自然语言到 Cypher 的辅助编辑区（演示）。")
    st.text_area("自然语言", height=100)
    st.code("// 生成的 Cypher（演示）", language="cypher")
with st.expander("🔎 查询执行"):
    st.write("用于直接输入 Cypher 并查看 JSON 结果（演示）。")
    st.text_area("Cypher", height=100)
    st.json({"columns": [], "data": []})

st.caption("以上示例仅展示 UI 布局与模式区分方式，不包含任何后