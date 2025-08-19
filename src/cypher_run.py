#!/usr/bin/env python3
import os
from neo4j import GraphDatabase, basic_auth

NEO4J_URI  = os.getenv("NEO4J_URI",  "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASS = os.getenv("NEO4J_PASS", "neo4jroot")
NEO4J_DB   = os.getenv("NEO4J_DB",   "neo4j")
CYPHER_FILE = os.getenv("CYPHER_FILE", "./src/import.cypher")

def load_statements(path: str):
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()

    # strip BOM if present
    text = text.lstrip("\ufeff")

    # split by semicolons into individual statements
    parts = [p.strip() for p in text.split(";")]
    # keep only non-empty statements
    return [p for p in parts if p]

def main():
    stmts = load_statements(CYPHER_FILE)
    driver = GraphDatabase.driver(NEO4J_URI, auth=basic_auth(NEO4J_USER, NEO4J_PASS))
    with driver.session(database=NEO4J_DB) as session:
        for s in stmts:
            session.run(s)  # autocommit per statement
    driver.close()

if __name__ == "__main__":
    main()
