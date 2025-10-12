import pandas as pd
import sys
from pathlib import Path

# 将项目根目录添加到 sys.path 以允许从 src 导入
project_root = Path(__file__).resolve().parents[2]
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from src import config
from src.utils.generate_node_rel import generate_node_csv, generate_rel_csv

def create_category_nodes_and_rels(df: pd.DataFrame, column_name: str, node_label: str, id_prefix: str):
    """
    为公司分组数据中的单个分类列生成节点和关系 CSV 文件。
    此函数创建 (Company)-[:CATEGORISED_AS]->(CategoryNode) 关系。

    Args:
        df (pd.DataFrame): 包含公司分组数据的 DataFrame。
        column_name (str): 要处理的列名 (例如, 'Tier_MarketCap')。
        node_label (str): 图中新节点的标签 (例如, 'TierMarketCap')。
        id_prefix (str): 用于为新节点生成唯一 ID 的短前缀 (例如, 'tmc_')。
    """
    print(f"\n正在为 '{column_name}' 生成节点和关系...")

    # 1. 准备 DataFrame：选择相关列并删除缺少此分类值的行。
    df_category = df[["companyID", column_name]].dropna(subset=[column_name]).copy()
    df_category[column_name] = df_category[column_name].astype(str).str.strip()

    if df_category.empty:
        print(f"未找到 '{column_name}' 的数据。正在跳过。")
        return

    # 2. 为每个唯一的分类值创建节点。
    unique_values_df = pd.DataFrame(df_category[column_name].unique(), columns=['text:string'])
    value_to_id_map = generate_node_csv(
        df_nodes=unique_values_df,
        id_col_name=f'{node_label.lower()}ID:ID',
        id_prefix=id_prefix,
        value_col_for_mapping='text:string',
        output_dir=config.GRAPH_DIR,
        filename=f"node_{node_label}.csv"
    )

    # 3. 创建 Company 节点和新分类节点之间的关系。
    relationships = []
    for _, row in df_category.iterrows():
        company_id = row['companyID']
        category_value = row[column_name]
        
        # 在创建关系之前，确保分类值存在于我们的映射中
        if category_value in value_to_id_map:
            relationships.append({
                ':START_ID': company_id,
                ':END_ID': value_to_id_map[category_value]
            })

    # 4. 将关系保存到 CSV 文件。
    # 图中的关系类型将是 :CATEGORISED_AS，由 Cypher 脚本处理。
    generate_rel_csv(
        relationships, 
        config.GRAPH_DIR, 
        f"rel_CategorisedAs_{node_label}.csv"
    )

def create_country_to_country_group_rels():
    """
    专门处理 Country 和 CountryGroup 之间的关系。
    它加载公司主数据以获取国家信息，并将其与分组数据连接，
    从而创建 (Country)-[:PART_OF]->(CountryGroup) 的关系。
    """
    print("\n正在为 'Country' 和 'CountryGroup' 生成节点和关系...")

    try:
        # 1. 加载所需数据
        source_file = config.DATA_DIR / "raw" / "company" / "company_group.csv"
        company_groups_df = pd.read_csv(source_file, usecols=["companyID", "CountryGroup"])
        
        master_company_df = pd.read_csv(config.MASTER_COMPANY_CSV, usecols=["companyID", "Country of Domicile"])
        
        # 加载已生成的国家节点以获取国家名称到ID的映射
        country_nodes_df = pd.read_csv(config.GRAPH_DIR / "node_Country.csv")
        country_name_to_id = pd.Series(country_nodes_df['countryID:ID'].values, index=country_nodes_df['text:string']).to_dict()

    except FileNotFoundError as e:
        print(f"错误: 找不到所需文件: {e.filename}。请确保 'generate_company_graph_csv.py' 已经运行。", file=sys.stderr)
        return

    # 2. 合并数据以建立 Country -> CountryGroup 的映射
    df_merged = pd.merge(company_groups_df, master_company_df, on="companyID")
    df_country_to_group = df_merged[["Country of Domicile", "CountryGroup"]].dropna().drop_duplicates()

    if df_country_to_group.empty:
        print("未找到 'CountryGroup' 的数据或无法映射到国家。正在跳过。")
        return

    # 3. 生成 CountryGroup 节点
    unique_groups_df = pd.DataFrame(df_country_to_group["CountryGroup"].unique(), columns=['text:string'])
    group_to_id_map = generate_node_csv(
        df_nodes=unique_groups_df,
        id_col_name='countrygroupID:ID',
        id_prefix='cg_',
        value_col_for_mapping='text:string',
        output_dir=config.GRAPH_DIR,
        filename="node_CountryGroup.csv"
    )

    # 4. 创建 (Country)-[:PART_OF]->(CountryGroup) 关系
    relationships = []
    for _, row in df_country_to_group.iterrows():
        country_name = row["Country of Domicile"]
        group_name = row["CountryGroup"]

        if country_name in country_name_to_id and group_name in group_to_id_map:
            relationships.append({
                ':START_ID': country_name_to_id[country_name],
                ':END_ID': group_to_id_map[group_name]
            })

    # 5. 保存关系文件
    generate_rel_csv(
        relationships,
        config.GRAPH_DIR,
        "rel_Country_PartOf_CountryGroup.csv"
    )

def main():
    """
    主函数，用于读取公司分组数据并为图导入生成所有必需的节点和关系文件。
    """
    print("开始公司分类过程...")
    
    # 确保输出目录存在
    config.GRAPH_DIR.mkdir(parents=True, exist_ok=True)

    # 加载源 CSV 文件
    try:
        source_file = config.DATA_DIR / "raw" / "company" / "company_group.csv"
        company_groups_df = pd.read_csv(source_file)
        print(f"已从 {source_file} 加载数据")
    except FileNotFoundError:
        print(f"错误: 在 {source_file} 未找到源文件", file=sys.stderr)
        sys.exit(1)

    # 定义要从 CSV 处理的类别。
    # 格式: { 'csv中的列名': ('图中的节点标签', '节点的id前缀') }
    # CountryGroup 已被移除，将通过一个专门的函数单独处理
    categories = {
        'Tier_MarketCap': ('TierMarketCap', 'tmc_'),
        'Tier_Revenue': ('TierRevenue', 'trv_'),
        'Tier_Assets': ('TierAssets', 'tas_'),
        'Group_AssetTurnover': ('GroupAssetTurnover', 'gat_'),
        'Group_MarketToAsset': ('GroupMarketToAsset', 'gma_'),
    }

    # 处理每个定义的类别
    for column, (label, prefix) in categories.items():
        if column in company_groups_df.columns:
            create_category_nodes_and_rels(company_groups_df, column, label, prefix)
        else:
            print(f"警告: 在 CSV 中未找到列 '{column}'。正在跳过。")

    # 单独处理 CountryGroup，创建 Country -> CountryGroup 的关系
    create_country_to_country_group_rels()

    print("\n已成功生成所有公司类别的节点和关系文件。")

if __name__ == "__main__":
    main()