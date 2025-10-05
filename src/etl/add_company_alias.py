import pandas as pd
from pathlib import Path
import sys

def create_master_company_data():
    """
    Reads the processed company data and synonym matching data, merges them,
    adds unique company IDs, and creates a master company data file.
    """
    try:
        # Define project root directory and file paths
        # __file__ is the path of the current script
        # .resolve() gets the absolute path
        # .parents[2] goes up two levels to the project root /home/wbi/repos/kg-similarities
        project_root = Path(__file__).resolve().parents[2]
        merged_company_data_path = project_root / "data" / "processed" / "CompanyData_Merged.csv"
        matches_scores_graph_path = project_root / "data" / "processed" / "Matches_Scores_Graph.csv"
        output_path = project_root / "data" / "master" / "CompanyData_Master.csv"

        # Read input CSV files
        print(f"Reading merged company data: {merged_company_data_path}")
        df_merged = pd.read_csv(merged_company_data_path)
        
        print(f"Reading match data: {matches_scores_graph_path}")
        df_matches = pd.read_csv(matches_scores_graph_path)

        # 1. Add companyID column on the leftmost side
        print("Adding companyID...")
        df_merged.insert(0, 'companyID', [f'comp_{i+1}' for i in range(len(df_merged))])

        # 2. Prepare synonyms from the match file
        print("Processing synonyms...")
        # Filter rows where Matched_Name and Graph_Company_Name are different
        df_synonyms = df_matches[df_matches['Matched_Name'] != df_matches['Graph_Company_Name']].copy()

        # Aggregate all synonyms for each company
        # Use sorted(list(set(x))) to ensure synonyms are unique and ordered
        synonyms_agg = df_synonyms.groupby(['Matched_Name', 'Matched_Source'])['Graph_Company_Name'].apply(
            lambda x: ', '.join(sorted(list(set(x))))
        ).reset_index()
        
        synonyms_agg.rename(columns={'Graph_Company_Name': 'SYNONYMS'}, inplace=True)

        # 3. Merge synonyms into the master dataframe
        print("Merging synonyms into company data...")
        df_master = pd.merge(
            df_merged,
            synonyms_agg,
            left_on=['Company Name', 'Source'],
            right_on=['Matched_Name', 'Matched_Source'],
            how='left'
        )

        # Clean up extra columns after merge
        df_master.drop(columns=['Matched_Name', 'Matched_Source'], inplace=True)

        # Replace NaN values in SYNONYMS column with empty strings
        df_master['SYNONYMS'].fillna('', inplace=True)

        # 4. Reorder columns, placing SYNONYMS column after Company Name
        print("Reordering columns...")
        cols = list(df_master.columns)
        # Pop the SYNONYMS column
        synonyms_col = cols.pop(cols.index('SYNONYMS'))
        # Find the index of 'Company Name' and insert 'SYNONYMS' after it
        company_name_index = cols.index('Company Name')
        cols.insert(company_name_index + 1, synonyms_col)
        df_master = df_master[cols]

        # 5. Save the final master file
        print(f"Saving master data file to: {output_path}")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        df_master.to_csv(output_path, index=False, encoding='utf-8-sig')

        print("Master company data file created successfully.")

    except FileNotFoundError as e:
        print(f"Error: File not found - {e}", file=sys.stderr)
    except Exception as e:
        print(f"An unknown error occurred: {e}", file=sys.stderr)

if __name__ == "__main__":
    create_master_company_data()