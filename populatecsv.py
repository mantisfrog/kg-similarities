import json
import pandas as pd
import argparse
import os

def convert_json_to_csv(input_json_path, output_csv_path):
    """
    Converts a GeoJSON FeatureCollection from a JSON file to a CSV file,
    ensuring all fields from the original JSON are preserved in a flat structure.

    Args:
        input_json_path (str): The file path for the input JSON file.
        output_csv_path (str): The file path for the output CSV file.
    """
    # 检查输入文件是否存在
    if not os.path.exists(input_json_path):
        print(f"错误: 在 '{input_json_path}' 未找到输入文件")
        return

    # 从文件加载JSON数据
    with open(input_json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # 提取要素列表
    features = data.get('features', [])
    if not features:
        print("警告: JSON文件中未找到任何要素。")
        return

    # 处理每个要素以提取所有数据
    records = []
    for feature in features:
        # 创建一个新字典来保存扁平化的数据
        record = {}

        # 1. 添加顶层字段 (id, type, geometry_name)
        record['id'] = feature.get('id')
        # 将'type'重命名为'feature_type'以避免与geometry中的type混淆
        record['feature_type'] = feature.get('type')
        record['geometry_name'] = feature.get('geometry_name')

        # 2. 处理嵌套的 'geometry' 对象
        geometry = feature.get('geometry', {})
        if geometry:
            record['geometry_type'] = geometry.get('type')
            coordinates = geometry.get('coordinates')
            if coordinates and isinstance(coordinates, list) and len(coordinates) == 2:
                record['longitude'] = coordinates[0]
                record['latitude'] = coordinates[1]
            else:
                # 如果坐标格式不符合预期，将其作为字符串存储
                record['coordinates_raw'] = str(coordinates)
        
        # 3. 添加 'properties' 对象中的所有字段
        properties = feature.get('properties', {})
        if properties:
            record.update(properties)

        records.append(record)

    # 从处理后的记录创建 pandas DataFrame
    df = pd.DataFrame(records)

    # (可选) 重新排列列的顺序，使关键信息更靠前
    # 将id和name等关键列放在前面
    preferred_order = [
        'id', 'feature_type', 'DEPOSIT_NAME', 'longitude', 'latitude', 
        'geometry_name', 'geometry_type', 'STATE', 'OPERATING_STATUS', 
        'COMMODITY_NAMES'
    ]
    # 获取所有其他列
    remaining_cols = [col for col in df.columns if col not in preferred_order]
    # 组合成新的列顺序
    new_order = preferred_order + remaining_cols
    # 应用新的列顺序
    df = df[new_order]

    # 将DataFrame保存为CSV文件
    df.to_csv(output_csv_path, index=False, encoding='utf-8-sig')
    print(f"成功将 '{input_json_path}' 转换为 '{output_csv_path}'，并保留了所有字段。")

if __name__ == '__main__':
    # 设置参数解析器
    parser = argparse.ArgumentParser(description='将GeoJSON文件转换为保留所有字段的CSV文件。')
    parser.add_argument('input_json', help='输入JSON文件的路径。')
    parser.add_argument('output_csv', help='输出CSV文件的路径。')

    # 解析命令行参数
    args = parser.parse_args()

    # 调用转换函数
    convert_json_to_csv(args.input_json, args.output_csv)