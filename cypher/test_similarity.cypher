// Test query for BHP Group Ltd and Evolution Mining Ltd
MATCH (c1:Company {name: 'BHP Group Ltd'}), (c2:Company {name: 'Evolution Mining Ltd'})

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
  t1mc.text + ' ↔ ' + t2mc.text AS MarketCap_Tiers,
  rmc.tier_distance AS MarketCap_Distance,
  t1rev.text + ' ↔ ' + t2rev.text AS Revenue_Tiers,
  rrev.tier_distance AS Revenue_Distance,
  t1assets.text + ' ↔ ' + t2assets.text AS Assets_Tiers,
  rassets.tier_distance AS Assets_Distance,
  gics.text AS Shared_Industry,
  CASE 
    WHEN shared_commodities > 0 THEN 5
    WHEN shared_country IS NOT NULL THEN 3
    WHEN rmc IS NOT NULL THEN 3
    WHEN shared_states > 0 THEN 7
    ELSE 99
  END AS Shortest_Hop_Distance;