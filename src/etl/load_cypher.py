from pathlib import Path
from neo4j import GraphDatabase
import sys

# Add project root to sys.path to allow importing from src
project_root = Path(__file__).resolve().parents[2]
sys.path.append(str(project_root))

from src import config

def run_cypher_file(file_path):
    """
    Connects to Neo4j and runs the Cypher commands from a specified file.
    """
    # Connection details from config
    uri = config.NEO4J_URI
    username = config.NEO4J_USER
    password = config.NEO4J_PASSWORD

    # Read the Cypher script from the file
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            cypher_script = f.read()
    except FileNotFoundError:
        print(f"Error: The Cypher script file was not found at '{file_path}'")
        return

    print(f"Connecting to Neo4j at {uri}...")
    driver = None
    try:
        driver = GraphDatabase.driver(uri, auth=(username, password))
        driver.verify_connectivity()
        print("Connection successful. Executing Cypher script...")

        with driver.session() as session:
            # Split the script into individual statements and execute them
            # This is a basic split; for more complex scripts, a proper parser might be needed
            statements = [stmt.strip() for stmt in cypher_script.split(';') if stmt.strip()]
            for i, statement in enumerate(statements):
                print(f"\n--- Executing statement {i+1} ---")
                print(statement)
                session.run(statement)
                print("Statement executed successfully.")
        
        print("\n✅ All Cypher commands executed successfully.")

    except Exception as e:
        print(f"An error occurred: {e}")
        # In case of an error, it's good practice to print the failed statement
        # if 'statement' in locals():
        #     print(f"Failed statement:\n{statement}")
    finally:
        if driver:
            driver.close()
            print("Connection closed.")

if __name__ == "__main__":
    cypher_file_path = config.CYPHER_FILE

    if not cypher_file_path.exists():
        print(f"Error: The file '{cypher_file_path}' was not found.")
    else:
        run_cypher_file(cypher_file_path)