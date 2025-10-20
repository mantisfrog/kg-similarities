import pandas as pd
from neo4j import GraphDatabase
from torch_geometric.data import HeteroData
import torch
import os
import sys
from pathlib import Path

# Add project root to sys.path to allow importing from src
project_root = Path(__file__).resolve().parents[2]
sys.path.append(str(project_root))

from src import config

# Neo4j connection settings from config file
URI = config.NEO4J_URI
AUTH = (config.NEO4J_USER, config.NEO4J_PASSWORD)

# Graph schema definitions are now imported from the config file
NODE_LABELS = config.NODE_LABELS
RELATION_TYPES = config.RELATION_TYPES

def get_node_data(driver, label, id_prop):
    """Fetches node IDs from Neo4j and creates mappings for a given label."""
    query = f"MATCH (n:{label}) RETURN n.{id_prop} AS id"
    with driver.session() as session:
        result = session.run(query)
        df = pd.DataFrame([record.data() for record in result])
    
    if df.empty:
        return {}, pd.Series(dtype=object)

    # Map Neo4j ID to a zero-based integer index for PyG
    neo4j_id_to_pyg_idx = {id_val: i for i, id_val in enumerate(df['id'])}
    
    # Create a Series to map PyG index back to Neo4j ID
    pyg_idx_to_neo4j_id = pd.Series(list(df['id']))
    
    return neo4j_id_to_pyg_idx, pyg_idx_to_neo4j_id

def get_edge_data(driver, src_label, rel_type, dst_label, src_id_prop, dst_id_prop):
    """Fetches relationships from Neo4j for a given edge type.

    Note: For (Project)-[:HAS_COMMODITY]->(Commodity), only main products are included
    by filtering relationship property `role = 'Primary'` so metapath walks reflect
    primary commodities only.
    """
    query = f"MATCH (s:{src_label})-[r:{rel_type}]->(d:{dst_label})"
    # Restrict commodity links to main products only
    if rel_type == 'HAS_COMMODITY':
        query += " WHERE r.role = 'Primary'"
    query += f" RETURN s.{src_id_prop} AS source, d.{dst_id_prop} AS target"
    with driver.session() as session:
        result = session.run(query)
        df = pd.DataFrame([record.data() for record in result])
    return df

def neo4j_to_heterodata(uri, auth):
    """Constructs a PyG HeteroData object from a Neo4j graph."""
    driver = GraphDatabase.driver(uri, auth=auth)
    hetero_data = HeteroData()
    
    # 1. Fetch all nodes and create mappings
    node_mappings = {}  # Stores {node_label: {neo4j_id: pyg_idx}}
    id_series_mappings = {}  # Stores {node_label: Series of neo4j_ids indexed by pyg_idx}
    
    for label, id_prop in NODE_LABELS.items():
        print(f"Extracting nodes for label: {label}")
        mapping, id_series = get_node_data(driver, label, id_prop)
        node_mappings[label] = mapping
        id_series_mappings[label] = id_series
        # Set the number of nodes for the label. No features (x) are needed for metapath2vec.
        hetero_data[label].num_nodes = len(mapping)
        print(f"  - Found {len(mapping)} {label} nodes.")

    # 2. Fetch all relationships and convert to PyG edge_index format
    for src_label, rel_type, dst_label in RELATION_TYPES:
        print(f"Extracting edges for relationship: ({src_label})-[:{rel_type}]->({dst_label})")
        df_edges = get_edge_data(
            driver, 
            src_label, rel_type, dst_label, 
            NODE_LABELS[src_label], NODE_LABELS[dst_label]
        )
        
        if not df_edges.empty:
            # Map Neo4j IDs to PyG integer indices
            src_indices = [node_mappings[src_label][neo4j_id] for neo4j_id in df_edges['source']]
            dst_indices = [node_mappings[dst_label][neo4j_id] for neo4j_id in df_edges['target']]
            
            # Create the forward edge_index
            edge_index = torch.tensor([src_indices, dst_indices], dtype=torch.long)
            hetero_data[src_label, rel_type.lower(), dst_label].edge_index = edge_index
            print(f"  - Found {edge_index.shape[1]} edges for ({src_label})-[:{rel_type}]->({dst_label}).")

            # Create the reverse edge_index for metapath traversal
            rev_edge_index = torch.tensor([dst_indices, src_indices], dtype=torch.long)
            hetero_data[dst_label, f'rev_{rel_type.lower()}', src_label].edge_index = rev_edge_index
            print(f"  - Added {rev_edge_index.shape[1]} reverse edges for ({dst_label})-[:rev_{rel_type.lower()}]->({src_label}).")
        else:
            print(f"  - No edges found for ({src_label})-[:{rel_type}]->({dst_label}).")

    driver.close()
    return hetero_data, id_series_mappings

if __name__ == "__main__":
    # Print connection info for debugging
    print(f"Attempting to connect to Neo4j at {URI} with user {AUTH[0]}...")

    try:
        # Generate the HeteroData object and ID mappings
        data, id_maps = neo4j_to_heterodata(URI, AUTH)
        print("\nSuccessfully loaded graph into PyG HeteroData object!")
        print(data)

        # Example: show original Neo4j IDs for the first few Company nodes
        if 'Company' in id_maps and not id_maps['Company'].empty:
            print(f"\nExample Neo4j Company IDs for PyG indices 0-4: {id_maps['Company'].head()}")
        
        # Add this code to show Project examples too
        if 'Project' in id_maps and not id_maps['Project'].empty:
            print(f"\nExample Neo4j Project IDs for PyG indices 0-4: {id_maps['Project'].head()}")
        
        # Save the data and mappings to disk for later use
        torch.save(data, config.HETERO_DATA_PATH)
        torch.save(id_maps, config.ID_MAPS_PATH)
        print(f"\nGraph data and ID mappings saved to '{config.HETERO_DATA_PATH}' and '{config.ID_MAPS_PATH}'")

    except Exception as e:
        print(f"\nFailed to connect to Neo4j or process graph data: {e}")
        print("Please ensure Neo4j is running and accessible at the specified URI, and the credentials are correct.")
