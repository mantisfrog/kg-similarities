import pandas as pd
from pathlib import Path

def match_projects():
    """
    从 ProjectData_Master.csv 中匹配给定的项目列表。
    匹配逻辑：只要给定的项目名被 'PROJECT_NAME' 或 'SYNONYMS' 列中的值包含，就算匹配。
    """
    # 定义要匹配的项目名称列表
    target_projects = [
        "Golden Grove", "Jaurdi", "Yandi", "Mount Keith", "Karlawinda",
        "Weld Range", "Ravensthorpe", "Iron Bridge", "Gruyere", "Roy Hill",
        "Lake Giles", "Wodgina", "Onslow", "Koolan Island", "Boddington",
        "Hemi", "Jundee", "Brockman 4", "Daisy Milano", "Greenbushes", "Bluebird"
    ]

    # 设置文件路径
    project_root = Path(__file__).resolve().parents[2]
    master_file_path = project_root / "data" / "master" / "ProjectData_Master.csv"
    output_file_path = project_root / "tests" / "testresult" / "matched_major_projects.csv"

    # 确保输出目录存在
    output_file_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"正在从 {master_file_path} 读取数据...")
    try:
        df_master = pd.read_csv(master_file_path)
    except FileNotFoundError:
        print(f"错误: 未找到主数据文件: {master_file_path}")
        return

    # 预处理：填充 SYNONYMS 列中的空值，并将列转换为字符串类型以便进行包含检查
    df_master['PROJECT_NAME'] = df_master['PROJECT_NAME'].astype(str)
    df_master['SYNONYMS'] = df_master['SYNONYMS'].fillna('').astype(str)

    results = []
    
    print("开始匹配项目...")
    # 遍历每个目标项目名称
    for target_name in target_projects:
        target_name_lower = target_name.lower()
        
        # 查找包含目标名称的行
        # 使用 str.contains() 进行不区分大小写的子字符串匹配
        mask = (
            df_master['PROJECT_NAME'].str.lower().str.contains(target_name_lower, na=False) |
            df_master['SYNONYMS'].str.lower().str.contains(target_name_lower, na=False)
        )
        
        matched_rows = df_master[mask]
        
        if not matched_rows.empty:
            for _, row in matched_rows.iterrows():
                # 准备输出行：第一列是目标项目名，后面是匹配到的所有列
                output_row = {'TARGET_PROJECT': target_name}
                output_row.update(row.to_dict())
                results.append(output_row)
        else:
            print(f" - 未找到 '{target_name}' 的匹配项")

    if not results:
        print("未找到任何匹配项。")
        return

    # 将结果转换为 DataFrame 并保存到 CSV
    df_results = pd.DataFrame(results)
    
    # 重新排列列，确保 TARGET_PROJECT 是第一列
    cols = ['TARGET_PROJECT'] + [col for col in df_master.columns if col != 'TARGET_PROJECT']
    df_results = df_results[cols]
    
    df_results.to_csv(output_file_path, index=False, encoding='utf-8')
    print(f"\n匹配完成。结果已保存到: {output_file_path}")
    print(f"总共找到 {len(df_results)} 条匹配记录。")

if __name__ == "__main__":
    match_projects()