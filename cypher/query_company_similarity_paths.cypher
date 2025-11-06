// =================================================================
// Query: Find Shortest Paths Between Two Companies
// Shows hop distance through common nodes (commodities, tiers, locations, etc.)
// =================================================================

// Parameters:
// $company1: First company name (e.g., "BHP Group Ltd")
// $company2: Second company name (e.g., "Evolution Mining Ltd")

// =================================================================
// Query 1: All Common Nodes with Hop Distances
// =================================================================

MATCH (c1:Company), (c2:Company)
WHERE c1.name = $company1 AND c2.name = $company2

// Find all paths between companies (limited depth to avoid explosion)
MATCH path = shortestPath((c1)-[*..6]-(c2))
WHERE NONE(r IN relationships(path) WHERE type(r) = 'REFERS_TO_COMPANY' OR type(r) = 'REFERS_TO_PROJECT')

WITH c1, c2, path,
     length(path) AS hop_count,
     [n IN nodes(path) WHERE n <> c1 AND n <> c2 | labels(n)[0]] AS node_types,
     [n IN nodes(path) WHERE n <> c1 AND n <> c2 | COALESCE(n.name, n.text)] AS node_names,
     [r IN relationships(path) | type(r)] AS relationship_types

RETURN 
  c1.name AS Company1,
  c2.name AS Company2,
  hop_count AS Total_Hops,
  node_types AS Common_Node_Types,
  node_names AS Common_Node_Names,
  relationship_types AS Relationship_Path
ORDER BY hop_count, node_types
LIMIT 20;


// =================================================================
// Query 2: Shortest Paths by Category
// Groups paths by the type of common node
// =================================================================

MATCH (c1:Company {name: $company1}), (c2:Company {name: $company2})

// Find paths through different types of nodes
WITH c1, c2

// Paths through Commodities
OPTIONAL MATCH commodityPath = (c1)-[:OWNS]->(:Project)-[:HAS_COMMODITY]->(comm:Commodity)<-[:HAS_COMMODITY]-(:Project)<-[:OWNS]-(c2)
WITH c1, c2, collect(DISTINCT {
  type: 'Commodity',
  name: comm.name,
  hops: 5,
  path: commodityPath
}) AS commodity_paths

// Paths through Tier Categories (with tier distance)
OPTIONAL MATCH tierMCPath = (c1)-[:CATEGORISED_AS]->(t1:TierMarketCap)-[r:TIER_RELATED]-(t2:TierMarketCap)<-[:CATEGORISED_AS]-(c2)
WITH c1, c2, commodity_paths, collect(DISTINCT {
  type: 'TierMarketCap',
  name: t1.text + ' ↔ ' + t2.text,
  tier_distance: r.tier_distance,
  hops: 3,
  path: tierMCPath
}) AS tier_mc_paths

OPTIONAL MATCH tierRevPath = (c1)-[:CATEGORISED_AS]->(t1:TierRevenue)-[r:TIER_RELATED]-(t2:TierRevenue)<-[:CATEGORISED_AS]-(c2)
WITH c1, c2, commodity_paths, tier_mc_paths, collect(DISTINCT {
  type: 'TierRevenue',
  name: t1.text + ' ↔ ' + t2.text,
  tier_distance: r.tier_distance,
  hops: 3,
  path: tierRevPath
}) AS tier_rev_paths

OPTIONAL MATCH tierAssetsPath = (c1)-[:CATEGORISED_AS]->(t1:TierAssets)-[r:TIER_RELATED]-(t2:TierAssets)<-[:CATEGORISED_AS]-(c2)
WITH c1, c2, commodity_paths, tier_mc_paths, tier_rev_paths, collect(DISTINCT {
  type: 'TierAssets',
  name: t1.text + ' ↔ ' + t2.text,
  tier_distance: r.tier_distance,
  hops: 3,
  path: tierAssetsPath
}) AS tier_assets_paths

// Paths through State
OPTIONAL MATCH statePath = (c1)-[:OWNS]->(:Project)-[:LOCATED_IN]->(:LGA)-[:LOCATED_IN]->(state:State)<-[:LOCATED_IN]-(:LGA)<-[:LOCATED_IN]-(:Project)<-[:OWNS]-(c2)
WITH c1, c2, commodity_paths, tier_mc_paths, tier_rev_paths, tier_assets_paths, collect(DISTINCT {
  type: 'State',
  name: state.text,
  hops: 7,
  path: statePath
}) AS state_paths

// Paths through Country
OPTIONAL MATCH countryPath = (c1)-[:DOMICILED_IN]->(country:Country)<-[:DOMICILED_IN]-(c2)
WITH c1, c2, commodity_paths, tier_mc_paths, tier_rev_paths, tier_assets_paths, state_paths, collect(DISTINCT {
  type: 'Country',
  name: country.text,
  hops: 3,
  path: countryPath
}) AS country_paths

// Paths through Industry Classifications
OPTIONAL MATCH gicsPath = (c1)-[:CLASSIFIED_AS]->(gics:GICSSubIndustry)<-[:CLASSIFIED_AS]-(c2)
WITH c1, c2, commodity_paths, tier_mc_paths, tier_rev_paths, tier_assets_paths, state_paths, country_paths, collect(DISTINCT {
  type: 'GICSSubIndustry',
  name: gics.text,
  hops: 3,
  path: gicsPath
}) AS gics_paths

// Combine all paths
WITH c1, c2,
     commodity_paths + tier_mc_paths + tier_rev_paths + tier_assets_paths + state_paths + country_paths + gics_paths AS all_paths

UNWIND all_paths AS connection

RETURN 
  c1.name AS Company1,
  c2.name AS Company2,
  connection.type AS Connection_Type,
  connection.name AS Common_Node,
  connection.hops AS Hop_Count,
  connection.tier_distance AS Tier_Distance
ORDER BY connection.hops, connection.type, connection.name;


// =================================================================
// Query 3: Visual Graph - Shortest Paths
// Shows all shortest paths for visualization in Neo4j Browser
// =================================================================

MATCH (c1:Company {name: $company1}), (c2:Company {name: $company2})
MATCH paths = allShortestPaths((c1)-[*..8]-(c2))
WHERE NONE(r IN relationships(paths) WHERE type(r) = 'REFERS_TO_COMPANY' OR type(r) = 'REFERS_TO_PROJECT')

RETURN paths
LIMIT 50;


// =================================================================
// Query 4: Summary Statistics
// Counts connections by type
// =================================================================

MATCH (c1:Company {name: $company1}), (c2:Company {name: $company2})

WITH c1, c2

// Count commodities in common
OPTIONAL MATCH (c1)-[:OWNS]->(:Project)-[:HAS_COMMODITY]->(comm:Commodity)<-[:HAS_COMMODITY]-(:Project)<-[:OWNS]-(c2)
WITH c1, c2, count(DISTINCT comm) AS shared_commodities

// Count states in common
OPTIONAL MATCH (c1)-[:OWNS]->(:Project)-[:LOCATED_IN]->(:LGA)-[:LOCATED_IN]->(state:State)<-[:LOCATED_IN]-(:LGA)<-[:LOCATED_IN]-(:Project)<-[:OWNS]-(c2)
WITH c1, c2, shared_commodities, count(DISTINCT state) AS shared_states

// Check if same country
OPTIONAL MATCH (c1)-[:DOMICILED_IN]->(country:Country)<-[:DOMICILED_IN]-(c2)
WITH c1, c2, shared_commodities, shared_states, country.text AS shared_country

// Check tier connections
OPTIONAL MATCH (c1)-[:CATEGORISED_AS]->(t1mc:TierMarketCap)-[rmc:TIER_RELATED]-(t2mc:TierMarketCap)<-[:CATEGORISED_AS]-(c2)
OPTIONAL MATCH (c1)-[:CATEGORISED_AS]->(t1rev:TierRevenue)-[rrev:TIER_RELATED]-(t2rev:TierRevenue)<-[:CATEGORISED_AS]-(c2)
OPTIONAL MATCH (c1)-[:CATEGORISED_AS]->(t1assets:TierAssets)-[rassets:TIER_RELATED]-(t2assets:TierAssets)<-[:CATEGORISED_AS]-(c2)

// Check industry classification overlap
OPTIONAL MATCH (c1)-[:CLASSIFIED_AS]->(gics:GICSSubIndustry)<-[:CLASSIFIED_AS]-(c2)

RETURN 
  c1.name AS Company1,
  c2.name AS Company2,
  shared_commodities AS Shared_Commodities,
  shared_states AS Shared_States,
  shared_country AS Shared_Country,
  t1mc.text + ' → ' + t2mc.text AS MarketCap_Tiers,
  rmc.tier_distance AS MarketCap_Distance,
  t1rev.text + ' → ' + t2rev.text AS Revenue_Tiers,
  rrev.tier_distance AS Revenue_Distance,
  t1assets.text + ' → ' + t2assets.text AS Assets_Tiers,
  rassets.tier_distance AS Assets_Distance,
  gics.text AS Shared_Industry,
  CASE 
    WHEN shared_commodities > 0 THEN 5
    WHEN shared_country IS NOT NULL THEN 3
    WHEN rmc IS NOT NULL THEN 3
    WHEN shared_states > 0 THEN 7
    ELSE 99
  END AS Shortest_Hop_Distance;


// =================================================================
// Query 5: Detailed Path Analysis
// Shows the actual shortest path with all intermediate nodes
// =================================================================

MATCH (c1:Company {name: $company1}), (c2:Company {name: $company2})
MATCH path = shortestPath((c1)-[*..6]-(c2))
WHERE NONE(r IN relationships(path) WHERE type(r) = 'REFERS_TO_COMPANY' OR type(r) = 'REFERS_TO_PROJECT')

WITH path, length(path) AS hops,
     [n IN nodes(path) | COALESCE(n.name, n.text, labels(n)[0])] AS path_nodes,
     [r IN relationships(path) | type(r)] AS path_rels

RETURN 
  hops AS Total_Hops,
  path_nodes AS Path,
  path_rels AS Relationships,
  path
ORDER BY hops
LIMIT 10;