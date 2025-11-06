# Company Similarity Path Queries

## Overview

These queries find the shortest paths and hop distances between any two companies through their nearest common nodes (commodities, tiers, locations, industry classifications, etc.).

## Quick Start

### Example: BHP Group Ltd and Evolution Mining Ltd

```cypher
docker exec -i neo4j cypher-shell -u neo4j -p neo4jroot < cypher/test_similarity.cypher
```

**Results:**
- **Shared Commodities**: 10 (Gold, Copper, etc.)
- **Shared States**: 4 (NSW, WA, SA, QLD)
- **Shared Country**: Australia
- **MarketCap Distance**: 1 tier (MegaCap ↔ LargeCap)
- **Revenue Distance**: 1 tier (HighRevenue ↔ UpperRevenue)
- **Assets Distance**: 2 tiers (HeavyAsset ↔ MidAsset)
- **Shortest Hop Distance**: 5 hops (through commodities)

## Understanding Hop Distances

### Path Structure and Hop Counts

Different types of connections have different hop distances:

#### 1. **Commodity Connection** - 5 hops
```
Company1 → OWNS → Project → HAS_COMMODITY → Commodity ← HAS_COMMODITY ← Project ← OWNS ← Company2
```
- Most common and direct business connection
- Shows actual operational overlap

#### 2. **Country Connection** - 3 hops
```
Company1 → DOMICILED_IN → Country ← DOMICILED_IN ← Company2
```
- Geographic/jurisdictional similarity
- Indicates same regulatory environment

#### 3. **Tier Connection** - 3 hops
```
Company1 → CATEGORISED_AS → TierNode ← TIER_RELATED → TierNode ← CATEGORISED_AS ← Company2
```
- Business size/scale similarity
- Includes tier_distance property showing how far apart

#### 4. **Industry Classification** - 3 hops
```
Company1 → CLASSIFIED_AS → GICSSubIndustry ← CLASSIFIED_AS ← Company2
```
- Sector/industry similarity
- Same business category

#### 5. **State Connection** - 7 hops
```
Company1 → OWNS → Project → LOCATED_IN → LGA → LOCATED_IN → State ← LOCATED_IN ← LGA ← LOCATED_IN ← Project ← OWNS ← Company2
```
- Regional operational overlap
- Projects in same state

## Query Files

### 1. [`cypher/test_similarity.cypher`](../cypher/test_similarity.cypher)
Simple hardcoded test for BHP and Evolution Mining.

### 2. [`cypher/query_company_similarity_paths.cypher`](../cypher/query_company_similarity_paths.cypher)
Comprehensive query suite with 5 different queries:

#### Query 1: All Common Nodes with Hop Distances
Finds all shortest paths up to 6 hops between companies.

#### Query 2: Shortest Paths by Category
Groups paths by type (Commodity, Tier, State, Country, Industry).

#### Query 3: Visual Graph
Returns paths for visualization in Neo4j Browser.

#### Query 4: Summary Statistics  
Counts all connections and determines shortest hop distance.

#### Query 5: Detailed Path Analysis
Shows the exact path with all intermediate nodes.

## How to Use

### Method 1: Edit Test File
1. Open [`cypher/test_similarity.cypher`](../cypher/test_similarity.cypher)
2. Change company names on line 2:
   ```cypher
   MATCH (c1:Company {name: 'Your Company 1'}), (c2:Company {name: 'Your Company 2'})
   ```
3. Run: `docker exec -i neo4j cypher-shell -u neo4j -p neo4jroot < cypher/test_similarity.cypher`

### Method 2: Neo4j Browser
1. Open Neo4j Browser at http://localhost:7474
2. Copy any query from [`query_company_similarity_paths.cypher`](../cypher/query_company_similarity_paths.cypher)
3. Replace `$company1` and `$company2` with actual company names
4. Execute

### Method 3: Python Script

Create a script to query any two companies:

```python
from neo4j import GraphDatabase

def find_company_similarity(company1, company2):
    driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "neo4jroot"))
    
    query = """
    MATCH (c1:Company {name: $company1}), (c2:Company {name: $company2})
    WITH c1, c2
    OPTIONAL MATCH (c1)-[:OWNS]->(:Project)-[:HAS_COMMODITY]->(comm:Commodity)<-[:HAS_COMMODITY]-(:Project)<-[:OWNS]-(c2)
    WITH c1, c2, count(DISTINCT comm) AS shared_commodities
    OPTIONAL MATCH (c1)-[:OWNS]->(:Project)-[:LOCATED_IN]->(:LGA)-[:LOCATED_IN]->(state:State)<-[:LOCATED_IN]-(:LGA)<-[:LOCATED_IN]-(:Project)<-[:OWNS]-(c2)
    WITH c1, c2, shared_commodities, count(DISTINCT state) AS shared_states
    OPTIONAL MATCH (c1)-[:DOMICILED_IN]->(country:Country)<-[:DOMICILED_IN]-(c2)
    WITH c1, c2, shared_commodities, shared_states, country.text AS shared_country
    OPTIONAL MATCH (c1)-[:CATEGORISED_AS]->(t1mc:TierMarketCap)-[rmc:TIER_RELATED]-(t2mc:TierMarketCap)<-[:CATEGORISED_AS]-(c2)
    OPTIONAL MATCH (c1)-[:CATEGORISED_AS]->(t1rev:TierRevenue)-[rrev:TIER_RELATED]-(t2rev:TierRevenue)<-[:CATEGORISED_AS]-(c2)
    OPTIONAL MATCH (c1)-[:CATEGORISED_AS]->(t1assets:TierAssets)-[rassets:TIER_RELATED]-(t2assets:TierAssets)<-[:CATEGORISED_AS]-(c2)
    RETURN 
      c1.name AS Company1,
      c2.name AS Company2,
      shared_commodities, shared_states, shared_country,
      t1mc.text + ' ↔ ' + t2mc.text AS marketcap_tiers,
      rmc.tier_distance AS marketcap_distance,
      t1rev.text + ' ↔ ' + t2rev.text AS revenue_tiers,
      rrev.tier_distance AS revenue_distance,
      t1assets.text + ' ↔ ' + t2assets.text AS assets_tiers,
      rassets.tier_distance AS assets_distance,
      CASE 
        WHEN shared_commodities > 0 THEN 5
        WHEN shared_country IS NOT NULL THEN 3
        WHEN rmc IS NOT NULL THEN 3
        WHEN shared_states > 0 THEN 7
        ELSE 99
      END AS shortest_hop_distance
    """
    
    with driver.session() as session:
        result = session.run(query, company1=company1, company2=company2)
        return result.single()
    
    driver.close()

# Example usage
result = find_company_similarity("BHP Group Ltd", "Evolution Mining Ltd")
print(f"Shortest hop distance: {result['shortest_hop_distance']}")
print(f"Shared commodities: {result['shared_commodities']}")
print(f"Market cap tiers: {result['marketcap_tiers']} (distance: {result['marketcap_distance']})")
```

## Interpreting Results

### Shortest Hop Distance Priority
The query determines the shortest path using this priority:
1. **5 hops**: Shared commodities (strongest operational connection)
2. **3 hops**: Same country OR tier connections
3. **7 hops**: Shared states (regional overlap)
4. **99**: No common nodes found

### Tier Distance Interpretation
- **0**: Exact same tier (same business scale)
- **1**: Adjacent tiers (similar scale)
- **2+**: Multiple tiers apart (different scale)

### Example Interpretation

For BHP and Evolution Mining:
- **Shortest path**: 5 hops through commodities
- **10 shared commodities**: Strong operational overlap (Gold, Copper, etc.)
- **4 shared states**: Significant regional overlap
- **Same country**: Australia (both ASX-listed)
- **MarketCap distance = 1**: Adjacent tiers (BHP larger, but comparable)
- **Revenue distance = 1**: Similar revenue scales
- **Assets distance = 2**: BHP has significantly more assets

**Conclusion**: These companies are highly similar with strong operational overlap despite size differences.

## Advanced Queries

### Find All Companies Within N Hops

```cypher
MATCH (c:Company {name: 'BHP Group Ltd'})
MATCH path = (c)-[*..5]->(other:Company)
WHERE c <> other
RETURN DISTINCT other.name AS Company, length(path) AS Hops
ORDER BY Hops, Company
LIMIT 20;
```

### Compare Multiple Companies

```cypher
UNWIND ['BHP Group Ltd', 'Rio Tinto Ltd', 'Fortescue Metals Group Ltd'] AS company_name
MATCH (c:Company {name: company_name})
OPTIONAL MATCH (c)-[:OWNS]->(:Project)-[:HAS_COMMODITY]->(comm:Commodity)
RETURN c.name AS Company, 
       collect(DISTINCT comm.name) AS Commodities,
       size(collect(DISTINCT comm)) AS Commodity_Count
ORDER BY Commodity_Count DESC;
```

### Find Most Similar Companies

```cypher
MATCH (target:Company {name: 'Evolution Mining Ltd'})
MATCH (other:Company)
WHERE target <> other

// Count shared commodities
OPTIONAL MATCH (target)-[:OWNS]->(:Project)-[:HAS_COMMODITY]->(comm:Commodity)<-[:HAS_COMMODITY]-(:Project)<-[:OWNS]-(other)
WITH target, other, count(DISTINCT comm) AS shared_comm

// Check tier similarity
OPTIONAL MATCH (target)-[:CATEGORISED_AS]->(t1:TierMarketCap)-[r:TIER_RELATED]-(t2:TierMarketCap)<-[:CATEGORISED_AS]-(other)

RETURN other.name AS Company,
       shared_comm AS Shared_Commodities,
       r.tier_distance AS Tier_Distance
ORDER BY shared_comm DESC, Tier_Distance ASC
LIMIT 10;
```

## Tips

1. **Start with commodities**: They provide the most direct operational connections
2. **Use tier distances**: Great for finding companies of similar scale
3. **Combine metrics**: Look at multiple dimensions (commodities + tiers + location)
4. **Visualize in Browser**: Use Query 3 for graph visualization
5. **Watch hop limits**: Keep paths under 8 hops to avoid performance issues

## Integration with Existing Analysis

These hop-based queries complement:
- **PathSim**: Use hop distances as path weights
- **Jaccard Similarity**: Compare node overlap across different hop distances  
- **Graph Embeddings**: Incorporate hop distances as edge features
- **Metapath2Vec**: Use common nodes as meta-path definitions

## Files Reference

- [`cypher/test_similarity.cypher`](../cypher/test_similarity.cypher) - Simple test query
- [`cypher/query_company_similarity_paths.cypher`](../cypher/query_company_similarity_paths.cypher) - Full query suite
- [`cypher/query_bhp_evolution_with_tiers.cypher`](../cypher/query_bhp_evolution_with_tiers.cypher) - Detailed tier analysis
- [`cypher/import.cypher`](../cypher/import.cypher) - Graph schema and import