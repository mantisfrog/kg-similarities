import argparse
import json
import sys
from pathlib import Path
from textwrap import dedent

import pandas as pd
from neo4j import GraphDatabase

# Add project root to sys.path to allow imports from src
project_root = Path(__file__).resolve().parents[2]
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from src import config

def get_weighted_jaccard_query(mode_config, find_top_n=False):
    """Dynamically builds the Cypher query for weighted Jaccard similarity.

    Note: Avoids using the deprecated id(n); instead, uses stable business primary keys
    (from the config.NODE_LABELS <label> -> <id_property> mapping) to eliminate
    Neo4j deprecation warnings and improve readability/portability.
    """
    target_label = mode_config['target_label']
    target_id_prop = mode_config['target_id_prop']
    
    call_clauses = []
    score_calculations = []
    total_weight = sum(n['weight'] for n in mode_config['neighbors'])

    for i, neighbor in enumerate(mode_config['neighbors'], 1):
        neighbor_label = neighbor['neighbor_label']
        relationship = neighbor['relationship']
        weight = neighbor['weight']
        # Use stable primary key instead of deprecated id(n)
        id_prop = config.NODE_LABELS.get(neighbor_label)
        if not id_prop:
            raise ValueError(f"Missing NODE_LABELS mapping for label '{neighbor_label}'")

        call_clauses.append(dedent(f"""
            CALL (source, other) {{
                OPTIONAL MATCH (source){relationship}(n{i}:{neighbor_label})
                WITH apoc.coll.toSet(collect(n{i}.{id_prop})) AS s_set, source, other
                OPTIONAL MATCH (other){relationship}(n{i}:{neighbor_label})
                WITH s_set, apoc.coll.toSet(collect(n{i}.{id_prop})) AS o_set
                RETURN CASE
                    WHEN size(apoc.coll.union(s_set, o_set)) = 0 THEN 0.0
                    ELSE 1.0 * size(apoc.coll.intersection(s_set, o_set)) / size(apoc.coll.union(s_set, o_set))
                END AS score{i}
            }}
        """))
        score_calculations.append(f"score{i} * {weight}")

    # Build the main query body
    match_other_clause = (f"MATCH (other:{target_label})"
                          if find_top_n
                          else f"MATCH (other:{target_label} {{{target_id_prop}: $id2}})")

    # Build name lookup clause (only in Top-N mode)
    name_lookup_clause = ""
    if find_top_n:
        name_label = mode_config['name_label']
        name_rel = mode_config['name_relationship']
        name_lookup_clause = f"OPTIONAL MATCH (other_name:{name_label}){name_rel}(other)"

    full_query = f"""
        MATCH (source:{target_label} {{{target_id_prop}: $id1}})
        {match_other_clause}
        WHERE source <> other

        {''.join(call_clauses)}

        WITH other, {', '.join([f'score{i}' for i in range(1, len(mode_config["neighbors"]) + 1)])}
        {name_lookup_clause}
        
        RETURN
            other.{target_id_prop} AS entity_id,
            { "other_name.text AS name," if find_top_n else "" }
            ({ ' + '.join(score_calculations) }) / {total_weight} AS weighted_jaccard_similarity
    """
    return full_query

def get_entity_name(driver, mode_config, entity_id):
    """Fetches the name of a single entity."""
    query = f"""
        MATCH (target:{mode_config['target_label']} {{{mode_config['target_id_prop']}: $entity_id}})
        OPTIONAL MATCH (name:{mode_config['name_label']}){mode_config['name_relationship']}(target)
        RETURN name.text AS name
    """
    with driver.session(database="neo4j") as session:
        result = session.run(query, entity_id=entity_id)
        record = result.single()
        return record['name'] if record and record['name'] else "N/A"

def calculate_similarity_for_pair(driver, mode_config, id1, id2):
    """Calculates the weighted Jaccard similarity between two specified entities."""
    query = get_weighted_jaccard_query(mode_config, find_top_n=False)
    with driver.session(database="neo4j") as session:
        result = session.run(query, id1=id1, id2=id2)
        record = result.single()
        return record['weighted_jaccard_similarity'] if record else None

def find_top_similar(driver, mode_config, source_id, limit):
    """Finds the Top N most similar entities to a source entity."""
    query = get_weighted_jaccard_query(mode_config, find_top_n=True)
    query += "\nORDER BY weighted_jaccard_similarity DESC\nLIMIT $limit"
    
    with driver.session(database="neo4j") as session:
        result = session.run(query, id1=source_id, id2=None, limit=limit)
        records = [record.data() for record in result]
        return pd.DataFrame(records)

def main():
    parser = argparse.ArgumentParser(description="Calculate weighted Jaccard similarity and find top similar items.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("-c", "--company", action="store_true", help="Set mode to company.")
    group.add_argument("-p", "--project", action="store_true", help="Set mode to project.")
    parser.add_argument("entity_id1", type=str, help="The ID of the first entity.")
    parser.add_argument("entity_id2", type=str, help="The ID of the second entity.")
    parser.add_argument("--limit", type=int, default=5, help="Number of top similar items to return (default: 5).")
    args = parser.parse_args()

    mode = "company" if args.company else "project"

    config_path = Path(__file__).parent / "jaccard_config.json"
    if not config_path.exists():
        print(f"Error: Configuration file not found at {config_path}", file=sys.stderr)
        sys.exit(1)

    with open(config_path, 'r') as f:
        jaccard_config = json.load(f)

    mode_config = jaccard_config[mode]

    # Validate that the sum of weights is 10
    total_weight = sum(n['weight'] for n in mode_config['neighbors'])
    if not abs(total_weight - 10.0) < 1e-9:
        print(f"Error: The sum of weights for '{mode}' mode in config is {total_weight}, but it must be 10.", file=sys.stderr)
        sys.exit(1)

    driver = None
    try:
        driver = GraphDatabase.driver(config.NEO4J_URI, auth=(config.NEO4J_USER, config.NEO4J_PASSWORD))
        driver.verify_connectivity()
        print("✅ Successfully connected to Neo4j.")

        name1 = get_entity_name(driver, mode_config, args.entity_id1)
        name2 = get_entity_name(driver, mode_config, args.entity_id2)

        # 1. Calculate similarity between the two input IDs
        print(f"\n🔍 Calculating similarity between '{name1}' ({args.entity_id1}) and '{name2}' ({args.entity_id2})...")
        pair_similarity = calculate_similarity_for_pair(driver, mode_config, args.entity_id1, args.entity_id2)
        
        print("\n" + "="*60)
        print("Similarity Between Provided IDs")
        print("="*60)
        if pair_similarity is not None:
            print(f"-> Weighted Jaccard Similarity: {pair_similarity:.4f}")
        else:
            print("Could not calculate similarity. Check if IDs are correct.")
        
        # 2. Find the top N most similar to the first ID
        print(f"\n🔍 Finding top {args.limit} most similar entities for '{name1}' ({args.entity_id1})...")
        top_similar_df = find_top_similar(driver, mode_config, args.entity_id1, args.limit)

        print("\n" + "="*60)
        print(f"Top {args.limit} Similar Entities for '{name1}'")
        print("="*60)
        if top_similar_df.empty:
            print("No similar items found.")
        else:
            # Ensure column order
            if 'name' in top_similar_df.columns:
                top_similar_df = top_similar_df[['entity_id', 'name', 'weighted_jaccard_similarity']]
            print(top_similar_df.to_string(index=False))

    except Exception as e:
        print(f"\nAn error occurred: {e}", file=sys.stderr)
    finally:
        if driver:
            driver.close()
            print("\n🔌 Connection to Neo4j closed.")

if __name__ == "__main__":
    main()
