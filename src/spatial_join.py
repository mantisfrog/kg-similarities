import pandas as pd
import geopandas as gpd

DEPOSITS_CSV_PATH = './data/MineralDeposits.csv'
PROVINCES_SHP_PATH = './raw/116823_AGP_2018/ProvinceFullExtent.shp'
OUTPUT_CSV_PATH = './data/Deposits_spatial.csv'

def process_deposits_with_provinces(deposits_path, provinces_path, output_path):
    """
    Load deposits (CSV) and provinces (shapefile), spatially join them,
    and write deposits annotated with tectonic/igneous/sedimentary province names to CSV.
    """
    try:
        # 1) Load data
        print("Step 1/5: Loading data...")
        deposits_df = pd.read_csv(deposits_path)
        provinces_gdf = gpd.read_file(provinces_path)
        print(f"Loaded {len(deposits_df)} deposits and {len(provinces_gdf)} province polygons.")

        # Stable key to merge back results later
        deposits_df['original_index'] = range(len(deposits_df))

        # 2) Build GeoDataFrame for deposits (GDA94 = EPSG:4283)
        print("Step 2/5: Building point geometries...")
        deposits_df.dropna(subset=['LONG_GDA94', 'LAT_GDA94'], inplace=True)
        deposits_gdf = gpd.GeoDataFrame(
            deposits_df,
            geometry=gpd.points_from_xy(deposits_df.LONG_GDA94, deposits_df.LAT_GDA94),
            crs="EPSG:4283"
        )

        # 3) Spatial join (ensure same CRS)
        print("Step 3/5: Performing spatial join (this may take a while)...")
        provinces_gdf = provinces_gdf.to_crs(deposits_gdf.crs)
        joined_gdf = gpd.sjoin(deposits_gdf, provinces_gdf, how='left', predicate='within')
        print("Spatial join done.")

        # 4) Pivot matched province names into columns by TYPE
        print("Step 4/5: Reshaping join results...")
        target_types = ["tectonic", "igneous", "sedimentary"]
        filtered_join = joined_gdf[joined_gdf['TYPE'].isin(target_types)]
        result_df = filtered_join[['original_index', 'NAME', 'TYPE']].drop_duplicates()

        province_info = result_df.pivot_table(
            index='original_index',
            columns='TYPE',
            values='NAME',
            aggfunc='first'  # if multiple matches of same TYPE, keep first
        ).reset_index()

        # Ensure all target columns exist even if missing in data
        for t_type in target_types:
            if t_type not in province_info.columns:
                province_info[t_type] = None

        # 5) Merge back and save
        print("Step 5/5: Merging and saving...")
        final_df = pd.merge(deposits_df, province_info, on='original_index', how='left')
        # Define cols to drop
        columns_to_drop = ['original_index', 'ACCURACY_M', 'COMPANY_WEBSITES', 'DEPOSIT_MODEL']
        final_df.drop(columns=[col for col in columns_to_drop if col in final_df.columns], inplace=True)
        # Convert all column headers to uppercase before saving
        final_df.columns = [col.upper() for col in final_df.columns]
        final_df.to_csv(output_path, index=False, encoding='utf-8-sig')
        print(f"Done! Output saved to: {output_path}")

    except FileNotFoundError as e:
        print(f"Error: file not found - {e}. Check your paths.")
    except Exception as e:
        print(f"Error during processing: {e}")

if __name__ == "__main__":
    process_deposits_with_provinces(DEPOSITS_CSV_PATH, PROVINCES_SHP_PATH, OUTPUT_CSV_PATH)
