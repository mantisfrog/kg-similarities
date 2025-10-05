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
        df_master['SYNONYMS'] = df_master['SYNONYMS'].fillna('')

        # 4. Reorder columns, placing SYNONYMS column after Company Name
        print("Reordering columns...")
        cols = list(df_master.columns)
        # Pop the SYNONYMS column
        synonyms_col = cols.pop(cols.index('SYNONYMS'))
        # Find the index of 'Company Name' and insert 'SYNONYMS' after it
        company_name_index = cols.index('Company Name')
        cols.insert(company_name_index + 1, synonyms_col)
        df_master = df_master[cols]

        # 5. Integrate former names from former_names.csv
        print("Integrating former names...")
        try:
            former_names_path = project_root / "data" / "raw" / "company" / "former_names.csv"
            print(f"Reading former names data: {former_names_path}")
            df_former_names = pd.read_csv(former_names_path)

            # Set companyID as index for efficient lookups
            df_master.set_index('companyID', inplace=True)

            for _, row in df_former_names.iterrows():
                company_id = row['ID']
                # Check if the company_id from former_names exists in the master dataframe
                if company_id in df_master.index:
                    # Get current company name and synonyms
                    company_name = df_master.loc[company_id, 'Company Name']
                    existing_synonyms_str = df_master.loc[company_id, 'SYNONYMS']

                    # Create a set of existing names (union of Company Name and SYNONYMS) for case-insensitive checking
                    existing_names_set = {str(company_name).lower()}
                    if pd.notna(existing_synonyms_str) and existing_synonyms_str:
                        existing_names_set.update([s.strip().lower() for s in existing_synonyms_str.split(',')])

                    # Get new potential names and find ones that are not already present
                    former_names_list = [name.strip() for name in str(row['MatchedNames']).split(',')]
                    names_to_add = []
                    for name in former_names_list:
                        # Case-insensitive exact match check
                        if name.lower() not in existing_names_set:
                            names_to_add.append(name)
                            # Add to the set to avoid adding duplicates from the same row in former_names.csv
                            existing_names_set.add(name.lower())
                    
                    # If there are new names to add, append them to the SYNONYMS column
                    if names_to_add:
                        new_synonyms_str = ', '.join(names_to_add)
                        if existing_synonyms_str:
                            df_master.loc[company_id, 'SYNONYMS'] = existing_synonyms_str + ', ' + new_synonyms_str
                        else:
                            df_master.loc[company_id, 'SYNONYMS'] = new_synonyms_str
            
            # Reset index to bring companyID back as a column before saving
            df_master.reset_index(inplace=True)

        except FileNotFoundError:
            print(f"Warning: former_names.csv not found at {former_names_path}. Skipping integration.", file=sys.stderr)
            # If the file was not found, we might have set the index, so we should reset it.
            if 'companyID' not in df_master.columns:
                 df_master.reset_index(inplace=True)

        # 6. Save the final master file
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