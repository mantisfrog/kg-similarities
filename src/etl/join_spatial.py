import pandas as pd
import geopandas as gpd
from pathlib import Path

# --- Start of Modification ---

# Define the project root directory relative to the script's location.
script_dir = Path(__file__).resolve().parent
project_root = script_dir.parent.parent

# Define absolute paths for input and output files.
DEPOSITS_CSV_PATH = project_root / 'data/processed/MineralDeposits.csv'
PROVINCES_SHP_PATH = project_root / 'data/raw/shp/116823_AGP_2018/ProvinceFullExtent.shp'
STATES_SHP_PATH = project_root / 'data/raw/shp/STE_2021_AUST_SHP_GDA94/STE_2021_AUST_GDA94.shp'
OUTPUT_CSV_PATH = project_root / 'data/master/ProjectData_Master.csv'


# --- End of Modification ---

def process_deposits_with_provinces(deposits_path, provinces_path, output_path):
    """
    Enriches deposit data by spatially joining it with province and state shapefiles.
    It identifies which province polygons a deposit falls into and backfills missing state data.
    """
    try:
        # Ensure the output directory exists.
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        print("Step 1/6: Loading data...")
        deposits_df = pd.read_csv(deposits_path)
        provinces_gdf = gpd.read_file(provinces_path)
        states_gdf = gpd.read_file(STATES_SHP_PATH)
        print(f"Loaded {len(deposits_df)} deposits, {len(provinces_gdf)} province polygons, {len(states_gdf)} state polygons.")

        # Create a unique index to reliably merge data back after joins.
        deposits_df['original_index'] = range(len(deposits_df))

        print("Step 2/6: Building point geometries...")
        # Remove deposits that lack coordinate data.
        deposits_df.dropna(subset=['LONG_GDA94', 'LAT_GDA94'], inplace=True)
        # Convert the pandas DataFrame to a GeoDataFrame.
        deposits_gdf = gpd.GeoDataFrame(
            deposits_df,
            geometry=gpd.points_from_xy(deposits_df.LONG_GDA94, deposits_df.LAT_GDA94),
            crs="EPSG:4283"  # Set the coordinate reference system to GDA94.
        )

        print("Step 3/6: Filling missing STATE via spatial join...")
        # Ensure the states shapefile uses the same CRS as the deposits.
        states_gdf = states_gdf.to_crs(deposits_gdf.crs)
        # Identify deposits with missing state information.
        state_missing_mask = deposits_gdf['STATE'].isna() | (deposits_gdf['STATE'].astype(str).str.strip() == '')
        deposits_missing_state = deposits_gdf.loc[state_missing_mask].copy()

        if not deposits_missing_state.empty:
            # Perform a spatial join to find which state polygon contains each point.
            joined_states = gpd.sjoin(deposits_missing_state, states_gdf, how='left', predicate='covered_by')
            
            # Create a map from the original index to the state name found.
            fill_map = (joined_states[['original_index', 'STE_NAME21']]
                        .dropna()
                        .drop_duplicates()
                        .groupby('original_index')['STE_NAME21']
                        .first()
                        .rename('_STATE_FILL'))
            
            # Merge the found state names back into the original dataframe.
            deposits_df = deposits_df.merge(fill_map.reset_index(), on='original_index', how='left')
            state_is_blank = deposits_df['STATE'].isna() | (deposits_df['STATE'].astype(str).str.strip() == '')
            deposits_df.loc[state_is_blank, 'STATE'] = deposits_df.loc[state_is_blank, '_STATE_FILL']
            deposits_df.drop(columns=['_STATE_FILL'], inplace=True)
        else:
            print("All rows already have STATE; no filling needed.")

        # Re-create the GeoDataFrame with the updated state information.
        deposits_gdf = gpd.GeoDataFrame(
            deposits_df,
            geometry=gpd.points_from_xy(deposits_df.LONG_GDA94, deposits_df.LAT_GDA94),
            crs="EPSG:4283"
        )

        print("Step 4/6: Provinces spatial join...")
        # Ensure the provinces shapefile uses the same CRS.
        provinces_gdf = provinces_gdf.to_crs(deposits_gdf.crs)
        # Validate required columns in the provinces shapefile.
        if 'TYPE' not in provinces_gdf.columns:
            raise KeyError("Shapefile missing TYPE field")
        if 'NAME' not in provinces_gdf.columns:
            raise KeyError("Shapefile missing NAME field")
        provinces_gdf['TYPE'] = provinces_gdf['TYPE'].astype(str).str.strip().str.lower()

        # Spatially join deposits with provinces to find intersections.
        joined_gdf = gpd.sjoin(deposits_gdf, provinces_gdf, how='left', predicate='within')
        print("Provinces spatial join done.")

        print("Step 5/6: Reshaping join results...")
        target_types_order = ["igneous", "metallogenic", "sedimentary", "tectonic"]
        # Filter for the province types we are interested in.
        filtered_join = joined_gdf[joined_gdf['TYPE'].isin(target_types_order)]
        result_df = filtered_join[['original_index', 'NAME', 'TYPE']].drop_duplicates()

        # Pivot the data: group by deposit and create a separate column for each province type.
        province_info = (result_df
            .groupby(['original_index', 'TYPE'])['NAME']
            .apply(lambda s: ','.join(sorted(set(s.dropna())))) # Aggregate province names
            .unstack('TYPE')
            .reset_index()
        )
        # Ensure all target columns exist, even if no deposits were found for a type.
        for t in target_types_order:
            if t not in province_info.columns:
                province_info[t] = None

        print("Step 6/6: Merging and saving...")
        # Merge the pivoted province data back to the main deposits dataframe.
        final_df = pd.merge(deposits_df, province_info, on='original_index', how='left')
        
        # Remove temporary or unneeded columns.
        columns_to_drop = ['original_index', 'ACCURACY_M', 'COMPANY_WEBSITES', 'DEPOSIT_MODEL']
        final_df.drop(columns=[c for c in columns_to_drop if c in final_df.columns], inplace=True)

        # Standardize column names to uppercase.
        final_df.columns = [c.upper() for c in final_df.columns]
        
        # Rename DEPOSIT_NAME to PROJECT_NAME
        if 'DEPOSIT_NAME' in final_df.columns:
            final_df.rename(columns={'DEPOSIT_NAME': 'PROJECT_NAME'}, inplace=True)
        
        # --- START: Modified section to standardize STATE column ---
        print("Standardizing STATE column values...")
        # Map full state names to their standard abbreviations.
        state_map = {
            'Western Australia': 'WA',
            'Queensland': 'QLD',
            'South Australia': 'SA',
            'New South Wales': 'NSW',
            'Tasmania': 'TAS',
            'Victoria': 'VIC',
            'Northern Territory': 'NT',
            'Australian Capital Territory': 'ACT',
            'Indian Ocean Territories': 'IOT'
        }
        if 'STATE' in final_df.columns:
            final_df['STATE'] = final_df['STATE'].str.strip().replace(state_map)
        # --- END: Modified section ---

        # Define the final column order for the output CSV.
        desired_order = [
            "ENO", "PROJECT_NAME", "SYNONYMS", "STATE", "LONG_GDA94", "LAT_GDA94",
            "OPERATING_STATUS", "COMMODITY_PRIMARY", "COMMODITY_SECONDARY", "COMMODITY_NAMES",
            "COMPANIES", "GEOLOGIC_AGE", "DEPOSIT_MODEL_ENVIRONMENT", "DEPOSIT_MODEL_GROUP",
            "DEPOSIT_MODEL_TYPE", "PROVINCES", "IGNEOUS", "METALLOGENIC", "SEDIMENTARY", "TECTONIC"
        ]
        # Ensure all desired columns exist in the final DataFrame.
        for col in desired_order:
            if col not in final_df.columns:
                final_df[col] = None

        # Apply the desired column order.
        final_df = final_df[desired_order]

        # Save the enriched data to a new CSV file.
        final_df.to_csv(output_path, index=False, encoding='utf-8-sig')
        print(f"Done! Output saved to: {output_path}")

    except FileNotFoundError as e:
        print(f"Error: file not found - {e}. Check your paths.")
    except Exception as e:
        print(f"Error during processing: {e}")

# Main execution block.
if __name__ == "__main__":
    process_deposits_with_provinces(DEPOSITS_CSV_PATH, PROVINCES_SHP_PATH, OUTPUT_CSV_PATH)