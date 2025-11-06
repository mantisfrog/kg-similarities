// =================================================================
// Query: BHP Group Ltd and Evolution Mining Ltd Connected by Commodities
// Shows Gold and Copper connections with tier relationship distances
// =================================================================

// Main query showing companies connected through Gold and Copper with tier comparisons
MATCH (bhp:Company {name: 'BHP Group Ltd'})-[:OWNS]->(bhpProject:Project)-[:HAS_COMMODITY]->(commodity:Commodity)<-[:HAS_COMMODITY]-(evolProject:Project)<-[:OWNS]-(evol:Company {name: 'Evolution Mining Ltd'})
WHERE commodity.name IN ['Gold', 'Copper'] OR commodity.symbol IN ['Au', 'Cu']

// Get tier categorizations for both companies
OPTIONAL MATCH (bhp)-[:CATEGORISED_AS]->(bhpTierMC:TierMarketCap)
OPTIONAL MATCH (evol)-[:CATEGORISED_AS]->(evolTierMC:TierMarketCap)
OPTIONAL MATCH (bhpTierMC)-[rMC:TIER_RELATED]->(evolTierMC)

OPTIONAL MATCH (bhp)-[:CATEGORISED_AS]->(bhpTierRev:TierRevenue)
OPTIONAL MATCH (evol)-[:CATEGORISED_AS]->(evolTierRev:TierRevenue)
OPTIONAL MATCH (bhpTierRev)-[rRev:TIER_RELATED]->(evolTierRev)

OPTIONAL MATCH (bhp)-[:CATEGORISED_AS]->(bhpTierAssets:TierAssets)
OPTIONAL MATCH (evol)-[:CATEGORISED_AS]->(evolTierAssets:TierAssets)
OPTIONAL MATCH (bhpTierAssets)-[rAssets:TIER_RELATED]->(evolTierAssets)

OPTIONAL MATCH (bhp)-[:CATEGORISED_AS]->(bhpAssetTO:GroupAssetTurnover)
OPTIONAL MATCH (evol)-[:CATEGORISED_AS]->(evolAssetTO:GroupAssetTurnover)
OPTIONAL MATCH (bhpAssetTO)-[rATO:TIER_RELATED]->(evolAssetTO)

OPTIONAL MATCH (bhp)-[:CATEGORISED_AS]->(bhpMarketAsset:GroupMarketToAsset)
OPTIONAL MATCH (evol)-[:CATEGORISED_AS]->(evolMarketAsset:GroupMarketToAsset)
OPTIONAL MATCH (bhpMarketAsset)-[rMTA:TIER_RELATED]->(evolMarketAsset)

OPTIONAL MATCH (bhpProject)-[:CATEGORISED_AS]->(bhpReserves:ReservesScale)
OPTIONAL MATCH (evolProject)-[:CATEGORISED_AS]->(evolReserves:ReservesScale)
OPTIONAL MATCH (bhpReserves)-[rRes:TIER_RELATED]->(evolReserves)

// Get location information
OPTIONAL MATCH (bhpProject)-[:LOCATED_IN]->(bhpLGA:LGA)-[:LOCATED_IN]->(bhpState:State)
OPTIONAL MATCH (evolProject)-[:LOCATED_IN]->(evolLGA:LGA)-[:LOCATED_IN]->(evolState:State)

RETURN DISTINCT
  // Companies
  bhp.name AS BHP_Company,
  evol.name AS Evolution_Company,
  
  // Commodity connection
  commodity.name AS Commodity,
  commodity.symbol AS Symbol,
  
  // Projects
  bhpProject.name AS BHP_Project,
  evolProject.name AS Evolution_Project,
  
  // Location
  bhpState.text AS BHP_State,
  evolState.text AS Evolution_State,
  
  // Market Cap Tier Comparison
  bhpTierMC.text AS BHP_MarketCap_Tier,
  evolTierMC.text AS Evolution_MarketCap_Tier,
  rMC.tier_distance AS MarketCap_Tier_Distance,
  CASE 
    WHEN rMC.tier_distance = 0 THEN 'EXACT MATCH'
    WHEN rMC.tier_distance = 1 THEN 'Adjacent Tier'
    WHEN rMC.tier_distance > 1 THEN rMC.tier_distance + ' tiers apart'
    ELSE 'No connection'
  END AS MarketCap_Relationship,
  
  // Revenue Tier Comparison
  bhpTierRev.text AS BHP_Revenue_Tier,
  evolTierRev.text AS Evolution_Revenue_Tier,
  rRev.tier_distance AS Revenue_Tier_Distance,
  CASE 
    WHEN rRev.tier_distance = 0 THEN 'EXACT MATCH'
    WHEN rRev.tier_distance = 1 THEN 'Adjacent Tier'
    WHEN rRev.tier_distance > 1 THEN rRev.tier_distance + ' tiers apart'
    ELSE 'No connection'
  END AS Revenue_Relationship,
  
  // Assets Tier Comparison
  bhpTierAssets.text AS BHP_Assets_Tier,
  evolTierAssets.text AS Evolution_Assets_Tier,
  rAssets.tier_distance AS Assets_Tier_Distance,
  CASE 
    WHEN rAssets.tier_distance = 0 THEN 'EXACT MATCH'
    WHEN rAssets.tier_distance = 1 THEN 'Adjacent Tier'
    WHEN rAssets.tier_distance > 1 THEN rAssets.tier_distance + ' tiers apart'
    ELSE 'No connection'
  END AS Assets_Relationship,
  
  // Asset Turnover Comparison
  bhpAssetTO.text AS BHP_AssetTurnover,
  evolAssetTO.text AS Evolution_AssetTurnover,
  rATO.tier_distance AS AssetTurnover_Distance,
  
  // Market to Asset Comparison
  bhpMarketAsset.text AS BHP_MarketToAsset,
  evolMarketAsset.text AS Evolution_MarketToAsset,
  rMTA.tier_distance AS MarketToAsset_Distance,
  
  // Reserves Scale Comparison (Project Level)
  bhpReserves.text AS BHP_ReservesScale,
  evolReserves.text AS Evolution_ReservesScale,
  rRes.tier_distance AS ReservesScale_Distance,
  CASE 
    WHEN rRes.tier_distance = 0 THEN 'Same Scale'
    WHEN rRes.tier_distance = 1 THEN 'Adjacent Scale'
    WHEN rRes.tier_distance > 1 THEN rRes.tier_distance + ' scales apart'
    ELSE 'No connection'
  END AS ReservesScale_Relationship

ORDER BY Commodity, BHP_Project;


// =================================================================
// Alternative Query: Visual Graph Representation
// Shows all nodes and tier relationships for visualization
// =================================================================

MATCH path1 = (bhp:Company {name: 'BHP Group Ltd'})-[:OWNS]->(bhpProject:Project)-[:HAS_COMMODITY]->(commodity:Commodity)<-[:HAS_COMMODITY]-(evolProject:Project)<-[:OWNS]-(evol:Company {name: 'Evolution Mining Ltd'})
WHERE commodity.name IN ['Gold', 'Copper'] OR commodity.symbol IN ['Au', 'Cu']

// Company tier categorizations
OPTIONAL MATCH pathBhpTiers = (bhp)-[:CATEGORISED_AS]->(bhpTier)
WHERE bhpTier:TierMarketCap OR bhpTier:TierRevenue OR bhpTier:TierAssets OR 
      bhpTier:GroupAssetTurnover OR bhpTier:GroupMarketToAsset

OPTIONAL MATCH pathEvolTiers = (evol)-[:CATEGORISED_AS]->(evolTier)
WHERE evolTier:TierMarketCap OR evolTier:TierRevenue OR evolTier:TierAssets OR 
      evolTier:GroupAssetTurnover OR evolTier:GroupMarketToAsset

// Tier relationships between company tiers
OPTIONAL MATCH pathTierRels = (bhpTier)-[tierRel:TIER_RELATED]-(evolTier)
WHERE (bhp)-[:CATEGORISED_AS]->(bhpTier) AND (evol)-[:CATEGORISED_AS]->(evolTier)

// Project tier categorizations
OPTIONAL MATCH pathBhpProjTier = (bhpProject)-[:CATEGORISED_AS]->(bhpReserves:ReservesScale)
OPTIONAL MATCH pathEvolProjTier = (evolProject)-[:CATEGORISED_AS]->(evolReserves:ReservesScale)
OPTIONAL MATCH pathReservesRel = (bhpReserves)-[resRel:TIER_RELATED]-(evolReserves)

// Location paths
OPTIONAL MATCH pathBhpLoc = (bhpProject)-[:LOCATED_IN]->(bhpLGA:LGA)-[:LOCATED_IN]->(bhpState:State)
OPTIONAL MATCH pathEvolLoc = (evolProject)-[:LOCATED_IN]->(evolLGA:LGA)-[:LOCATED_IN]->(evolState:State)

RETURN path1, 
       pathBhpTiers, pathEvolTiers, pathTierRels,
       pathBhpProjTier, pathEvolProjTier, pathReservesRel,
       pathBhpLoc, pathEvolLoc
LIMIT 100;


// =================================================================
// Query: Summary Statistics
// Shows tier distance statistics between the companies
// =================================================================

MATCH (bhp:Company {name: 'BHP Group Ltd'})-[:OWNS]->(bhpProject:Project)-[:HAS_COMMODITY]->(commodity:Commodity)<-[:HAS_COMMODITY]-(evolProject:Project)<-[:OWNS]-(evol:Company {name: 'Evolution Mining Ltd'})
WHERE commodity.name IN ['Gold', 'Copper'] OR commodity.symbol IN ['Au', 'Cu']

// Unidirectional relationships - match in either direction
OPTIONAL MATCH (bhp)-[:CATEGORISED_AS]->(bhpTierMC:TierMarketCap)-[rMC:TIER_RELATED]-(evolTierMC:TierMarketCap)<-[:CATEGORISED_AS]-(evol)
OPTIONAL MATCH (bhp)-[:CATEGORISED_AS]->(bhpTierRev:TierRevenue)-[rRev:TIER_RELATED]-(evolTierRev:TierRevenue)<-[:CATEGORISED_AS]-(evol)
OPTIONAL MATCH (bhp)-[:CATEGORISED_AS]->(bhpTierAssets:TierAssets)-[rAssets:TIER_RELATED]-(evolTierAssets:TierAssets)<-[:CATEGORISED_AS]-(evol)
OPTIONAL MATCH (bhp)-[:CATEGORISED_AS]->(bhpAssetTO:GroupAssetTurnover)-[rATO:TIER_RELATED]-(evolAssetTO:GroupAssetTurnover)<-[:CATEGORISED_AS]-(evol)
OPTIONAL MATCH (bhp)-[:CATEGORISED_AS]->(bhpMarketAsset:GroupMarketToAsset)-[rMTA:TIER_RELATED]-(evolMarketAsset:GroupMarketToAsset)<-[:CATEGORISED_AS]-(evol)

WITH commodity,
     count(DISTINCT bhpProject) AS bhp_project_count,
     count(DISTINCT evolProject) AS evol_project_count,
     collect(DISTINCT {category: 'MarketCap', distance: rMC.tier_distance}) AS mc_distances,
     collect(DISTINCT {category: 'Revenue', distance: rRev.tier_distance}) AS rev_distances,
     collect(DISTINCT {category: 'Assets', distance: rAssets.tier_distance}) AS asset_distances,
     collect(DISTINCT {category: 'AssetTurnover', distance: rATO.tier_distance}) AS ato_distances,
     collect(DISTINCT {category: 'MarketToAsset', distance: rMTA.tier_distance}) AS mta_distances

RETURN 
  commodity.name AS Commodity,
  bhp_project_count AS BHP_Projects,
  evol_project_count AS Evolution_Projects,
  mc_distances[0].distance AS MarketCap_Tier_Distance,
  rev_distances[0].distance AS Revenue_Tier_Distance,
  asset_distances[0].distance AS Assets_Tier_Distance,
  ato_distances[0].distance AS AssetTurnover_Distance,
  mta_distances[0].distance AS MarketToAsset_Distance
ORDER BY Commodity;