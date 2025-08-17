import pandas as pd
import geopandas as gpd

# --- 文件路径配置 ---
# 请将这里的路径替换成您的实际文件路径
# 您的CSV文件
DEPOSITS_CSV_PATH = './data/MineralDeposits.csv'
# ProvinceFullExtent.shp 文件的完整路径
PROVINCES_SHP_PATH = './raw/116823_AGP_2018/ProvinceFullExtent.shp'
# 输出的CSV文件路径
OUTPUT_CSV_PATH = './data/Deposits2.csv'
# --------------------

def process_deposits_with_provinces(deposits_path, provinces_path, output_path):
    """
    读取矿床CSV文件，并根据地理省份shapefile为其添加地质体系信息。
    """
    try:
        # 1. 加载数据
        print("步骤 1/5: 正在加载数据...")
        deposits_df = pd.read_csv(deposits_path)
        provinces_gdf = gpd.read_file(provinces_path)
        print(f"成功加载 {len(deposits_df)} 条矿床数据和 {len(provinces_gdf)} 个地质省数据。")

        # 为原始数据创建一个唯一ID，便于后续数据合并
        deposits_df['original_index'] = range(len(deposits_df))

        # 2. 准备矿床点数据
        print("步骤 2/5: 正在转换坐标点...")
        # 去除没有有效坐标的行
        deposits_df.dropna(subset=['LONG_GDA94', 'LAT_GDA94'], inplace=True)
        
        # 将pandas DataFrame转换为GeoDataFrame
        # CRS 'EPSG:4283' 对应 GDA94
        deposits_gdf = gpd.GeoDataFrame(
            deposits_df,
            geometry=gpd.points_from_xy(deposits_df.LONG_GDA94, deposits_df.LAT_GDA94),
            crs="EPSG:4283"
        )

        # 3. 执行空间连接
        print("步骤 3/5: 正在执行空间连接 (这可能需要一些时间)...")
        # 确保两个图层的坐标系一致
        provinces_gdf = provinces_gdf.to_crs(deposits_gdf.crs)
        
        # 使用sjoin找出每个点所在的所有多边形
        joined_gdf = gpd.sjoin(deposits_gdf, provinces_gdf, how='left', predicate='within')
        print("空间连接完成。")

        # 4. 处理连接结果，将长数据转换为宽数据
        print("步骤 4/5: 正在整理匹配结果...")
        # 筛选出我们需要的地质体系类型
        target_types = ['tectonic', 'igneous', 'sedimentary']
        filtered_join = joined_gdf[joined_gdf['TYPE'].isin(target_types)]

        # 提取需要的列，并去除重复项（一个点可能位于同一个省的多个部分）
        result_df = filtered_join[['original_index', 'NAME', 'TYPE']].drop_duplicates()

        # 使用pivot_table将TYPE列转换为单独的列
        province_info = result_df.pivot_table(
            index='original_index',
            columns='TYPE',
            values='NAME',
            aggfunc='first' # 如果一个点匹配到多个同类型省份，只取第一个
        ).reset_index()
        
        # 确保所有目标列都存在
        for t_type in target_types:
            if t_type not in province_info.columns:
                province_info[t_type] = None

        # 5. 合并回原始数据并保存
        print("步骤 5/5: 正在合并数据并保存...")
        # 将处理好的地质省信息合并回最原始的DataFrame
        final_df = pd.merge(deposits_df, province_info, on='original_index', how='left')
        
        # 删除临时的索引列
        final_df.drop(columns=['original_index'], inplace=True)

        # 保存到新的CSV文件
        final_df.to_csv(output_path, index=False, encoding='utf-8-sig')
        print(f"处理完成！结果已保存到: {output_path}")

    except FileNotFoundError as e:
        print(f"错误：文件未找到 - {e}。请检查您的文件路径配置。")
    except Exception as e:
        print(f"处理过程中发生错误: {e}")

# --- 运行主程序 ---
if __name__ == "__main__":
    process_deposits_with_provinces(DEPOSITS_CSV_PATH, PROVINCES_SHP_PATH, OUTPUT_CSV_PATH)