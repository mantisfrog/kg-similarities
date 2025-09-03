import csv
import json
from pathlib import Path
from neo4j import GraphDatabase

# Neo4j connection details from docker-compose.yaml
URI = "bolt://localhost:7687"
AUTH = ("neo4j", "neo4jroot")

# Path to the directory containing CVs
script_dir = Path(__file__).parent
CVS_DIR = script_dir / '..' / 'testdata' / 'CVs'
OUTPUT_JSON_PATH = script_dir / '..' / 'testresult' / 'search_results.json'

def search_names_in_neo4j(driver, names):
    """
    Search for Name nodes in Neo4j.
    """
    with driver.session() as session:
        query = """
        UNWIND $names as name_to_search
        MATCH (n:Name)
        WHERE toLower(n.nameText) CONTAINS toLower(name_to_search)
        RETURN n, name_to_search
        """
        result = session.run(query, names=names)
        
        records = []
        for record in result:
            node = record["n"]
            node_as_dict = {
                "element_id": node.element_id,
                "labels": list(node.labels),
                "properties": dict(node)
            }
            records.append((node_as_dict, record["name_to_search"]))

        return {
            "query": query.strip(),
            "columns": ["n", "name_to_search"],
            "records": records
        }

def main():
    """
    Main function to read CVs and query Neo4j.
    """
    try:
        driver = GraphDatabase.driver(URI, auth=AUTH)
        driver.verify_connectivity()
        aggregated = { "results": [], "errors": [] }

        # Iterate over each file in the CVs directory
        for file_path in CVS_DIR.iterdir():
            if not file_path.is_file() or file_path.suffix != '.csv':
                continue
            filename = file_path.name
            try:
                with open(file_path, 'r', encoding='utf-8-sig') as csvfile:
                    reader = csv.reader(csvfile)
                    # Read all search terms from the current CSV file
                    search_terms = [row[0] for row in reader if row] # Assumes name is in the first column
                    
                    if not search_terms:
                        aggregated["results"].append({
                            "file": filename,
                            "search_results": []
                        })
                        continue

                    neo4j_result = search_names_in_neo4j(driver, search_terms)
                    
                    # Group found nodes by the search term
                    matches_by_term = {}
                    for node_dict, term in neo4j_result["records"]:
                        if term not in matches_by_term:
                            matches_by_term[term] = []
                        matches_by_term[term].append(node_dict)

                    # Build the desired structure for each search term
                    term_results = []
                    for term in search_terms:
                        matches = matches_by_term.get(term, [])
                        term_results.append({
                            "search_term": term,
                            "match_count": len(matches),
                            "matches": matches
                        })

                    aggregated["results"].append({
                        "file": filename,
                        "search_results": term_results
                    })
            except Exception as e:
                aggregated["errors"].append({
                    "file": filename,
                    "message": str(e)
                })

        # Final JSON output -> write to file
        OUTPUT_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(OUTPUT_JSON_PATH, 'w', encoding='utf-8') as f:
            json.dump(aggregated, f, ensure_ascii=False, indent=2)
        print(f"Wrote results to {OUTPUT_JSON_PATH}")
    except Exception as e:
        error_payload = {
            "results": [],
            "errors": [{"message": f"Connection or runtime error: {str(e)}"}]
        }
        OUTPUT_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(OUTPUT_JSON_PATH, 'w', encoding='utf-8') as f:
            json.dump(error_payload, f, ensure_ascii=False, indent=2)
        print(f"Error occurred. Details written to {OUTPUT_JSON_PATH}")
    finally:
        if 'driver' in locals() and driver:
            driver.close()
            # print("Neo4j connection closed.")

if __name__ == "__main__":
    main()
