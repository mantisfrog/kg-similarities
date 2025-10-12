import csv
import sys
from pathlib import Path

# 将项目根目录添加到 sys.path 以允许从 src 导入
# __file__ is in tests/scripts/, so we need to go up two levels (parents[2])
project_root = Path(__file__).resolve().parents[2] 
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from src import config

def diagnose_csv(file_path: Path):
    """
    逐行诊断CSV文件，查找可能导致解析错误的常见问题。
    """
    print(f"--- 开始诊断文件: {file_path} ---")
    
    if not file_path.exists():
        print(f"错误: 文件不存在！", file=sys.stderr)
        return

    found_issues = False
    try:
        with open(file_path, 'r', encoding='utf-8', newline='') as f:
            # 使用csv模块进行更严格的解析
            reader = csv.reader(f)
            
            try:
                header = next(reader)
                header_len = len(header)
                print(f"文件头包含 {header_len} 列: {header}")
                
                # 找到 'COMPANIES' 列的索引
                companies_col_index = -1
                if 'COMPANIES' in header:
                    companies_col_index = header.index('COMPANIES')
                
            except StopIteration:
                print("错误: 文件为空！", file=sys.stderr)
                return

            # 逐行检查
            for i, row in enumerate(reader):
                line_num = i + 2  # +1 for header, +1 for 0-based index

                # 1. 检查列数是否匹配
                if len(row) != header_len:
                    print(f"\n[严重问题] 第 {line_num} 行: 列数不匹配！")
                    print(f"  > 期望列数: {header_len}, 实际列数: {len(row)}")
                    print(f"  > 行内容: {row}")
                    found_issues = True
                    # 当列数不匹配时，通常意味着前面的行有解析错误（如未闭合的引号或内部换行符）
                    # 此时当前行的内容可能是上一行的一部分
                    continue

                # 2. 检查 'COMPANIES' 列是否有内部换行符
                if companies_col_index != -1:
                    company_cell = row[companies_col_index]
                    if '\n' in company_cell or '\r' in company_cell:
                        print(f"\n[严重问题] 第 {line_num} 行: 'COMPANIES' 列包含内部换行符！")
                        print(f"  > 这极有可能是导致行合并错误的根源。")
                        print(f"  > 内容: {repr(company_cell)}") # repr()会显示\n等特殊字符
                        found_issues = True

                # 3. 检查所有单元格的非ASCII字符
                for j, cell in enumerate(row):
                    non_ascii_chars = {char for char in cell if ord(char) > 127}
                    if non_ascii_chars:
                        print(f"\n[信息] 第 {line_num} 行, 第 {j+1} 列 ('{header[j]}'): 发现非ASCII字符。")
                        print(f"  > 字符: {', '.join(non_ascii_chars)}")
                        print(f"  > 完整内容: {cell}")
                        found_issues = True

    except csv.Error as e:
        # 这个错误通常在有未闭合的引号时触发
        print(f"\n[致命错误] CSV解析在第 {reader.line_num} 行附近失败: {e}", file=sys.stderr)
        print("  > 这几乎总是由一个未闭合的双引号 `\"` 引起的。", file=sys.stderr)
        found_issues = True
    except UnicodeDecodeError as e:
        print(f"\n[致命错误] 文件编码错误: {e}", file=sys.stderr)
        print("  > 文件可能不是UTF-8编码。请检查文件并以UTF-8格式重新保存。", file=sys.stderr)
        found_issues = True


    print("\n--- 诊断完成 ---")
    if not found_issues:
        print("未发现明显的格式问题。")
    else:
        print("诊断发现一个或多个问题。请根据上面的日志修复CSV文件。")


if __name__ == "__main__":
    diagnose_csv(config.MASTER_PROJECT_CSV)