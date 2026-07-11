"""
Generate tier relationship CSV files for Neo4j import.
Creates TIER_RELATED relationships between categorical tier nodes with tier_distance property.
"""

import pandas as pd
from pathlib import Path
from typing import Dict, List, Tuple


def define_tier_rankings() -> Dict[str, Dict[str, Tuple[str, int]]]:
    """
    Define the ranking for each tier type.
    Returns dict of {tier_type: {tier_id: (tier_text, rank)}}
    """
    return {
        'TierMarketCap': {
            'tmc_2': ('MegaCap', 1),
            'tmc_1': ('LargeCap', 2),
            'tmc_4': ('MidCap', 3),
            'tmc_5': ('SmallCap', 4),
            'tmc_3': ('MicroCap', 5)
        },
        'TierRevenue': {
            'trv_1': ('HighRevenue', 1),
            'trv_4': ('UpperRevenue', 2),
            'trv_3': ('MidRevenue', 3),
            'trv_2': ('LowRevenue', 4),
            'trv_5': ('VeryLowRevenue', 5)
        },
        'TierAssets': {
            'tas_1': ('HeavyAsset', 1),
            'tas_2': ('LargeAsset', 2),
            'tas_5': ('MidAsset', 3),
            'tas_3': ('LightAsset', 4),
            'tas_4': ('MicroAsset', 5)
        },
        'GroupAssetTurnover': {
            'gat_1': ('HighTurnover', 1),
            'gat_3': ('MidTurnover', 2),
            'gat_2': ('LowTurnover', 3)
        },
        'GroupMarketToAsset': {
            'gma_2': ('HighValue', 1),
            'gma_1': ('FairValue', 2),
            'gma_3': ('LowValue', 3)
        },
        'ReservesScale': {
            'reservesScale_1': ('Tier 1 (Highest)', 1),
            'reservesScale_2': ('Tier 2', 2),
            'reservesScale_3': ('Tier 3', 3),
            'reservesScale_4': ('Tier 4 (Lowest)', 4)
        }
    }


def create_tier_relationships() -> None:
    """Generate CSV files for tier relationships."""
    
    tier_rankings = define_tier_rankings()
    # Get project root directory (2 levels up from this file)
    project_root = Path(__file__).parent.parent.parent
    output_dir = project_root / 'data' / 'graph'
    output_dir.mkdir(parents=True, exist_ok=True)
    
    total_relationships = 0
    
    for tier_type, tier_data in tier_rankings.items():
        relationships = []
        
        # Create unidirectional relationships from lower rank to higher rank only
        for tier1_id, (tier1_text, rank1) in tier_data.items():
            for tier2_id, (tier2_text, rank2) in tier_data.items():
                # Only create relationship if tier1 has lower rank (better tier)
                if rank1 < rank2:
                    tier_distance = rank2 - rank1
                    relationships.append({
                        ':START_ID': tier1_id,
                        ':END_ID': tier2_id,
                        'tier_distance:int': tier_distance
                    })
        
        # Save to CSV
        df = pd.DataFrame(relationships)
        output_file = output_dir / f'rel_TierRelated_{tier_type}.csv'
        df.to_csv(output_file, index=False)
        
        print(f"[OK] Created {output_file}")
        print(f"  - {len(relationships)} relationships")
        total_relationships += len(relationships)
    
    print(f"\n[OK] Total: {total_relationships} tier relationships created")
    print(f"[OK] Files saved to: {output_dir}")


def verify_tier_nodes() -> None:
    """Verify that tier node files exist and display their contents."""
    
    tier_types = [
        'TierMarketCap',
        'TierRevenue', 
        'TierAssets',
        'GroupAssetTurnover',
        'GroupMarketToAsset',
        'ReservesScale'
    ]
    
    print("\n=== Verifying Tier Node Files ===")
    
    for tier_type in tier_types:
        # Map tier type to actual file name
        if tier_type == 'TierMarketCap':
            filename = 'node_TierMarketCap.csv'
        elif tier_type == 'TierRevenue':
            filename = 'node_TierRevenue.csv'
        elif tier_type == 'TierAssets':
            filename = 'node_TierAssets.csv'
        elif tier_type == 'GroupAssetTurnover':
            filename = 'node_GroupAssetTurnover.csv'
        elif tier_type == 'GroupMarketToAsset':
            filename = 'node_GroupMarketToAsset.csv'
        elif tier_type == 'ReservesScale':
            filename = 'node_ReservesScale.csv'
        
        # Get project root directory (2 levels up from this file)
        project_root = Path(__file__).parent.parent.parent
        filepath = project_root / 'data' / 'graph' / filename
        
        if filepath.exists():
            df = pd.read_csv(filepath)
            print(f"\n[OK] {tier_type}: {len(df)} nodes")
            for _, row in df.iterrows():
                print(f"  - {row[0]}: {row[1]}")
        else:
            print(f"\n[ERROR] {tier_type}: File not found at {filepath}")


if __name__ == '__main__':
    print("=" * 60)
    print("Creating Tier Relationships for Neo4j Graph")
    print("=" * 60)
    
    # Verify source files
    verify_tier_nodes()
    
    print("\n" + "=" * 60)
    print("Generating Relationship CSV Files")
    print("=" * 60)
    
    # Create relationships
    create_tier_relationships()
    
    print("\n" + "=" * 60)
    print("Complete!")
    print("=" * 60)
    print("\nNext steps:")
    print("1. Update cypher/import.cypher to load these relationships")
    print("2. Run the updated import script in Neo4j")