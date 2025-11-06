# Tier Relationships in Neo4j Knowledge Graph

## Overview

This implementation adds `TIER_RELATED` relationships between categorical tier nodes in the knowledge graph. These relationships enable analysis of how companies compare across different categorical dimensions, even when they belong to different tiers.

## What Was Implemented

### 1. Tier Relationship Generation Script

**File:** `src/etl/create_tier_relationships.py`

This Python script generates CSV files containing tier relationships with distance calculations.

**Tier Categories Covered:**
- `TierMarketCap` (5 tiers: MegaCap → LargeCap → MidCap → SmallCap → MicroCap)
- `TierRevenue` (5 tiers: HighRevenue → UpperRevenue → MidRevenue → LowRevenue → VeryLowRevenue)
- `TierAssets` (5 tiers: HeavyAsset → LargeAsset → MidAsset → LightAsset → MicroAsset)
- `GroupAssetTurnover` (3 groups: HighTurnover → MidTurnover → LowTurnover)
- `GroupMarketToAsset` (3 groups: HighValue → FairValue → LowValue)
- `ReservesScale` (4 tiers: Tier 1 (Highest) → Tier 2 → Tier 3 → Tier 4 (Lowest))

**Output:** 84 tier relationships across 6 CSV files in `data/graph/`

### 2. Updated Import Script

**File:** `cypher/import.cypher`

Added Section 7 to load tier relationships into Neo4j with the following structure:
```cypher
(TierNode1)-[TIER_RELATED {tier_distance: 2}]->(TierNode2)
```

The `tier_distance` property indicates how many tiers apart the nodes are:
- `0` = Same tier (exact match)
- `1` = Adjacent tiers
- `2+` = Multiple tiers apart

### 3. Query Examples

**File:** `cypher/query_bhp_evolution_with_tiers.cypher`

Three comprehensive queries demonstrating tier relationship usage:

1. **Detailed Comparison Query**: Shows BHP and Evolution Mining with tier distances
2. **Visual Graph Query**: For Neo4j Browser visualization
3. **Summary Statistics Query**: Aggregated tier distance metrics

## How to Use

### Step 1: Generate Tier Relationship Files

```bash
cd src/etl
python create_tier_relationships.py
```

This creates 6 CSV files in `data/graph/`:
- `rel_TierRelated_TierMarketCap.csv`
- `rel_TierRelated_TierRevenue.csv`
- `rel_TierRelated_TierAssets.csv`
- `rel_TierRelated_GroupAssetTurnover.csv`
- `rel_TierRelated_GroupMarketToAsset.csv`
- `rel_TierRelated_ReservesScale.csv`

### Step 2: Load into Neo4j

The tier relationships are automatically loaded when you run the updated `cypher/import.cypher` script in Neo4j.

### Step 3: Query the Graph

Use the queries in `cypher/query_bhp_evolution_with_tiers.cypher`:

**Example: Basic tier comparison**
```cypher
MATCH (bhp:Company {name: 'BHP Group Ltd'})-[:CATEGORISED_AS]->(bhpTier:TierMarketCap)-[r:TIER_RELATED]->(evolTier:TierMarketCap)<-[:CATEGORISED_AS]-(evol:Company {name: 'Evolution Mining Ltd'})
RETURN bhpTier.text, evolTier.text, r.tier_distance;
```

**Example: Find companies in adjacent tiers**
```cypher
MATCH (c1:Company)-[:CATEGORISED_AS]->(t1:TierMarketCap)-[r:TIER_RELATED {tier_distance: 1}]->(t2:TierMarketCap)<-[:CATEGORISED_AS]-(c2:Company)
RETURN c1.name, t1.text, c2.name, t2.text;
```

## Relationship Structure

### Node Pattern
```
(Company)-[:CATEGORISED_AS]->(TierNode)
```

### Tier Relationship Pattern
```
(TierNode1)-[TIER_RELATED {tier_distance: N}]->(TierNode2)
```

### Complete Path Example
```
(BHP)-[:CATEGORISED_AS]->(MegaCap:TierMarketCap)-[TIER_RELATED {tier_distance: 3}]->(MidCap:TierMarketCap)<-[:CATEGORISED_AS]-(EvolutionMining)
```

## Benefits

1. **Quantified Comparisons**: Numeric tier distances enable similarity calculations
2. **Flexible Queries**: Can query for exact matches, adjacent tiers, or within N tiers
3. **Graph Visualization**: Tier relationships appear as edges in Neo4j Browser
4. **Embedding Integration**: Tier distances can inform graph embeddings and similarity metrics
5. **Discovery**: Find companies with similar tier profiles across multiple dimensions

## Query Use Cases

### 1. Find Similar Companies by Tier Profile
```cypher
MATCH (target:Company {name: 'Evolution Mining Ltd'})-[:CATEGORISED_AS]->(targetTier)
MATCH (similar:Company)-[:CATEGORISED_AS]->(similarTier)
WHERE target <> similar
  AND (targetTier)-[r:TIER_RELATED]->(similarTier)
  AND r.tier_distance <= 1
WITH similar, collect({category: labels(targetTier)[0], distance: r.tier_distance}) AS tier_profile
RETURN similar.name, tier_profile
ORDER BY size(tier_profile) DESC;
```

### 2. Commodity Connections with Tier Context
```cypher
MATCH (c1:Company)-[:OWNS]->(:Project)-[:HAS_COMMODITY]->(commodity:Commodity)<-[:HAS_COMMODITY]-(:Project)<-[:OWNS]-(c2:Company)
WHERE c1 <> c2
OPTIONAL MATCH (c1)-[:CATEGORISED_AS]->(t1:TierMarketCap)-[r:TIER_RELATED]->(t2:TierMarketCap)<-[:CATEGORISED_AS]-(c2)
RETURN c1.name, c2.name, commodity.name, r.tier_distance AS marketcap_distance;
```

### 3. Project Reserve Comparisons
```cypher
MATCH (p1:Project)-[:CATEGORISED_AS]->(r1:ReservesScale)-[rel:TIER_RELATED]->(r2:ReservesScale)<-[:CATEGORISED_AS]-(p2:Project)
WHERE rel.tier_distance = 1
RETURN p1.name, r1.text, p2.name, r2.text;
```

## Integration with Existing Analysis

These tier relationships complement existing graph analysis techniques:

- **PathSim**: Tier distances can weight meta-paths
- **Jaccard Similarity**: Consider tier overlap in addition to direct connections
- **Embeddings**: Use tier relationships as additional features in graph neural networks
- **Recommendations**: Find companies with similar tier profiles for competitive analysis

## Future Enhancements

Possible extensions:
1. Add cross-tier relationships (e.g., `TierMarketCap` to `TierRevenue` correlations)
2. Calculate tier centrality metrics
3. Weighted tier distances based on business domain knowledge
4. Temporal tier analysis (companies moving between tiers over time)

## Files Modified/Created

- ✅ `src/etl/create_tier_relationships.py` - Script to generate relationships
- ✅ `cypher/import.cypher` - Updated to load tier relationships
- ✅ `cypher/query_bhp_evolution_with_tiers.cypher` - Example queries
- ✅ `data/graph/rel_TierRelated_*.csv` - 6 relationship CSV files (84 total relationships)

## Questions?

For questions or issues, refer to:
- Main README: `README.md`
- Graph schema: `cypher/import.cypher`
- Example queries: `cypher/query_bhp_evolution_with_tiers.cypher`