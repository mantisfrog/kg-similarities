import pandas as pd
import geopandas as gpd

DEPOSITS_CSV_PATH = './data/processed/MineralDeposits.csv'
PROVINCES_SHP_PATH = './data/raw/116823_AGP_2018/ProvinceFullExtent.shp'
STATES_SHP_PATH   = './data/raw/STE_2021_AUST_SHP_GDA94/STE_2021_AUST_GDA94.shp'
OUTPUT_CSV_PATH   = './data/processed/Deposits_spatial.csv'

def process_deposits_with_provinces(deposits_path, provinces_path, output_path):
    """
    Spatially annotate deposits with province TYPE names and backfill missing STATE from ABS 2021 states.
    """
    try:
        print("Step 1/6: Loading data...")
        deposits_df = pd.read_csv(deposits_path)
        provinces_gdf = gpd.read_file(provinces_path)
        states_gdf = gpd.read_file(STATES_SHP_PATH)
        print(f"Loaded {len(deposits_df)} deposits, {len(provinces_gdf)} province polygons, {len(states_gdf)} state polygons.")

        deposits_df['original_index'] = range(len(deposits_df))

        print("Step 2/6: Building point geometries...")
        deposits_df.dropna(subset=['LONG_GDA94', 'LAT_GDA94'], inplace=True)
        deposits_gdf = gpd.GeoDataFrame(
            deposits_df,
            geometry=gpd.points_from_xy(deposits_df.LONG_GDA94, deposits_df.LAT_GDA94),
            crs="EPSG:4283"
        )

        print("Step 3/6: Filling missing STATE via spatial join...")
        states_gdf = states_gdf.to_crs(deposits_gdf.crs)
        state_missing_mask = deposits_gdf['STATE'].isna() | (deposits_gdf['STATE'].astype(str).str.strip() == '')
        deposits_missing_state = deposits_gdf.loc[state_missing_mask].copy()

        if not deposits_missing_state.empty:
            # point covered_by polygon (includes boundary)
            joined_states = gpd.sjoin(deposits_missing_state, states_gdf, how='left', predicate='covered_by')
            fill_map = (joined_states[['original_index', 'STE_NAME21']]
                        .dropna()
                        .drop_duplicates()
                        .groupby('original_index')['STE_NAME21']
                        .first()
                        .rename('_STATE_FILL'))
            deposits_df = deposits_df.merge(fill_map.reset_index(), on='original_index', how='left')
            state_is_blank = deposits_df['STATE'].isna() | (deposits_df['STATE'].astype(str).str.strip() == '')
            deposits_df.loc[state_is_blank, 'STATE'] = deposits_df.loc[state_is_blank, '_STATE_FILL']
            deposits_df.drop(columns=['_STATE_FILL'], inplace=True)
        else:
            print("All rows already have STATE; no filling needed.")

        deposits_gdf = gpd.GeoDataFrame(
            deposits_df,
            geometry=gpd.points_from_xy(deposits_df.LONG_GDA94, deposits_df.LAT_GDA94),
            crs="EPSG:4283"
        )

        print("Step 4/6: Provinces spatial join...")
        provinces_gdf = provinces_gdf.to_crs(deposits_gdf.crs)
        if 'TYPE' not in provinces_gdf.columns:
            raise KeyError("Shapefile missing TYPE field")
        if 'NAME' not in provinces_gdf.columns:
            raise KeyError("Shapefile missing NAME field")
        provinces_gdf['TYPE'] = provinces_gdf['TYPE'].astype(str).str.strip().str.lower()

        # point within polygon (strict interior; boundary not matched)
        joined_gdf = gpd.sjoin(deposits_gdf, provinces_gdf, how='left', predicate='within')
        print("Provinces spatial join done.")

        print("Step 5/6: Reshaping join results...")
        target_types_order = ["igneous", "metallogenic", "sedimentary", "tectonic"]
        filtered_join = joined_gdf[joined_gdf['TYPE'].isin(target_types_order)]
        result_df = filtered_join[['original_index', 'NAME', 'TYPE']].drop_duplicates()

        province_info = (result_df
            .groupby(['original_index', 'TYPE'])['NAME']
            .apply(lambda s: ','.join(sorted(set(s.dropna()))))
            .unstack('TYPE')
            .reset_index()
        )
        for t in target_types_order:
            if t not in province_info.columns:
                province_info[t] = None

        print("Step 6/6: Merging and saving...")
        final_df = pd.merge(deposits_df, province_info, on='original_index', how='left')
        columns_to_drop = ['original_index', 'ACCURACY_M', 'COMPANY_WEBSITES', 'DEPOSIT_MODEL']
        final_df.drop(columns=[c for c in columns_to_drop if c in final_df.columns], inplace=True)

        final_df.columns = [c.upper() for c in final_df.columns]
        desired_order = [
            "ENO", "DEPOSIT_NAME", "SYNONYMS", "STATE", "LONG_GDA94", "LAT_GDA94",
            "OPERATING_STATUS", "COMMODITY_PRIMARY", "COMMODITY_SECONDARY", "COMMODITY_NAMES",
            "COMPANIES", "GEOLOGIC_AGE", "DEPOSIT_MODEL_ENVIRONMENT", "DEPOSIT_MODEL_GROUP",
            "DEPOSIT_MODEL_TYPE", "PROVINCES", "IGNEOUS", "METALLOGENIC", "SEDIMENTARY", "TECTONIC"
        ]
        final_df = final_df[desired_order]

        final_df.to_csv(output_path, index=False, encoding='utf-8-sig')
        print(f"Done! Output saved to: {output_path}")

    except FileNotFoundError as e:
        print(f"Error: file not found - {e}. Check your paths.")
    except Exception as e:
        print(f"Error during processing: {e}")

if __name__ == "__main__":
    process_deposits_with_provinces(DEPOSITS_CSV_PATH, PROVINCES_SHP_PATH, OUTPUT_CSV_PATH)
