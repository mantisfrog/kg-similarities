// =================================================================
// 1. Clean up the database
// =================================================================
MATCH (n) DETACH DELETE n;
CALL apoc.schema.assert({}, {});
// =================================================================
// 2. Create constraints
// =================================================================
// This creates a uniqueness constraint and index for the ID property of each node type
CREATE CONSTRAINT company_id_unique IF NOT EXISTS FOR (c:Company) REQUIRE c.companyID IS UNIQUE;
CREATE CONSTRAINT companyname_id_unique IF NOT EXISTS FOR (cn:CompanyName) REQUIRE cn.companyNameID IS UNIQUE;
CREATE CONSTRAINT project_id_unique IF NOT EXISTS FOR (p:Project) REQUIRE p.projectID IS UNIQUE;
CREATE CONSTRAINT projectname_id_unique IF NOT EXISTS FOR (pn:ProjectName) REQUIRE pn.projectNameID IS UNIQUE;
CREATE CONSTRAINT state_id_unique IF NOT EXISTS FOR (s:State) REQUIRE s.stateID IS UNIQUE;
CREATE CONSTRAINT lga_id_unique IF NOT EXISTS FOR (l:LGA) REQUIRE l.lgaID IS UNIQUE;
CREATE CONSTRAINT commodity_id_unique IF NOT EXISTS FOR (c:Commodity) REQUIRE c.commodityID IS UNIQUE;
CREATE CONSTRAINT commoditygroup_id_unique IF NOT EXISTS FOR (cg:CommodityGroup) REQUIRE cg.commodityGroupID IS UNIQUE;
CREATE CONSTRAINT country_id_unique IF NOT EXISTS FOR (c:Country) REQUIRE c.countryID IS UNIQUE;
CREATE CONSTRAINT icbsector_id_unique IF NOT EXISTS FOR (n:ICBSector) REQUIRE n.icbsectorID IS UNIQUE;
CREATE CONSTRAINT icbsubsector_id_unique IF NOT EXISTS FOR (n:ICBSubsector) REQUIRE n.icbsubsectorID IS UNIQUE;
CREATE CONSTRAINT gicsindustry_id_unique IF NOT EXISTS FOR (n:GICSIndustry) REQUIRE n.gicsindustryID IS UNIQUE;
CREATE CONSTRAINT gicssubindustry_id_unique IF NOT EXISTS FOR (n:GICSSubIndustry) REQUIRE n.gicssubindustryID IS UNIQUE;
CREATE CONSTRAINT bicsl3_id_unique IF NOT EXISTS FOR (n:BICSL3) REQUIRE n.bicsl3ID IS UNIQUE;
CREATE CONSTRAINT bicsl4_id_unique IF NOT EXISTS FOR (n:BICSL4) REQUIRE n.bicsl4ID IS UNIQUE;
CREATE CONSTRAINT bicsl5_id_unique IF NOT EXISTS FOR (n:BICSL5) REQUIRE n.bicsl5ID IS UNIQUE;
CREATE CONSTRAINT bicsl6_id_unique IF NOT EXISTS FOR (n:BICSL6) REQUIRE n.bicsl6ID IS UNIQUE;

// =================================================================
// 3. Import node data
// =================================================================

// Import Company nodes
LOAD CSV WITH HEADERS FROM 'file:///node_Company.csv' AS row
MERGE (c:Company {companyID: row.`companyID:ID`})
SET c.ticker = row.`Ticker:string`,
    c.acn = toInteger(row.`ACN:int`),
    c.marketCap = toFloat(row.`Market Cap:float`),
    c.revenue = toFloat(row.`Revenue:Y:float`),
    c.totalAssets = toFloat(row.`Tot Assets:Y:float`),
    c.employees = toInteger(row.`Number of Employees:LF:int`),
    c.description = row.`Company Description:string`,
    c.linkedinEmployees = toInteger(row.`Linkedin_empCount:int`),
    c.linkedinFollowers = toInteger(row.`Linkedin_Followers:int`);

// Import CompanyName nodes
LOAD CSV WITH HEADERS FROM 'file:///node_CompanyName.csv' AS row
MERGE (cn:CompanyName {companyNameID: row.`companyNameID:ID`})
SET cn.text = row.`text:string`;

// Import Country nodes
LOAD CSV WITH HEADERS FROM 'file:///node_Country.csv' AS row
MERGE (c:Country {countryID: row.`countryID:ID`})
SET c.text = row.`text:string`;

// Import Classification Nodes
LOAD CSV WITH HEADERS FROM 'file:///node_ICBSector.csv' AS row MERGE (n:ICBSector {icbsectorID: row.`icbsectorID:ID`}) SET n.text = row.`text:string`;
LOAD CSV WITH HEADERS FROM 'file:///node_ICBSubsector.csv' AS row MERGE (n:ICBSubsector {icbsubsectorID: row.`icbsubsectorID:ID`}) SET n.text = row.`text:string`;
LOAD CSV WITH HEADERS FROM 'file:///node_GICSIndustry.csv' AS row MERGE (n:GICSIndustry {gicsindustryID: row.`gicsindustryID:ID`}) SET n.text = row.`text:string`;
LOAD CSV WITH HEADERS FROM 'file:///node_GICSSubIndustry.csv' AS row MERGE (n:GICSSubIndustry {gicssubindustryID: row.`gicssubindustryID:ID`}) SET n.text = row.`text:string`;
LOAD CSV WITH HEADERS FROM 'file:///node_BICSL3.csv' AS row MERGE (n:BICSL3 {bicsl3ID: row.`bicsl3ID:ID`}) SET n.text = row.`text:string`;
LOAD CSV WITH HEADERS FROM 'file:///node_BICSL4.csv' AS row MERGE (n:BICSL4 {bicsl4ID: row.`bicsl4ID:ID`}) SET n.text = row.`text:string`;
LOAD CSV WITH HEADERS FROM 'file:///node_BICSL5.csv' AS row MERGE (n:BICSL5 {bicsl5ID: row.`bicsl5ID:ID`}) SET n.text = row.`text:string`;
LOAD CSV WITH HEADERS FROM 'file:///node_BICSL6.csv' AS row MERGE (n:BICSL6 {bicsl6ID: row.`bicsl6ID:ID`}) SET n.text = row.`text:string`;

// Import Project nodes
LOAD CSV WITH HEADERS FROM 'file:///node_Project.csv' AS row
MERGE (p:Project {projectID: row.`projectID:ID`})
SET p.eno = toInteger(row.`eno:int`),
    p.location = row.`location:point`,
    p.geologicAge = row.`geologicAge:string`,
    p.depositModelEnvironment = row.`depositModelEnvironment:string`,
    p.depositModelGroup = row.`depositModelGroup:string`,
    p.depositModelType = row.`depositModelType:string`,
    p.igneous = row.`igneous:string`,
    p.metallogenic = row.`metallogenic:string`,
    p.sedimentary = row.`sedimentary:string`,
    p.tectonic = row.`tectonic:string`;

// Import ProjectName nodes
LOAD CSV WITH HEADERS FROM 'file:///node_ProjectName.csv' AS row
MERGE (pn:ProjectName {projectNameID: row.`projectNameID:ID`})
SET pn.text = row.`text:string`;

// Import State nodes
LOAD CSV WITH HEADERS FROM 'file:///node_State.csv' AS row
MERGE (s:State {stateID: row.`stateID:ID`})
SET s.text = row.`text:string`;

// Import LGA nodes
LOAD CSV WITH HEADERS FROM 'file:///node_LGA.csv' AS row
MERGE (l:LGA {lgaID: row.`lgaID:ID`})
SET l.text = row.`text:string`;

// Import Commodity nodes
LOAD CSV WITH HEADERS FROM 'file:///node_Commodity.csv' AS row
MERGE (c:Commodity {commodityID: row.`commodityID:ID`})
SET c.symbol = row.`symbol:string`,
    c.name = row.`name:string`;

// Import CommodityGroup nodes
LOAD CSV WITH HEADERS FROM 'file:///node_CommodityGroup.csv' AS row
MERGE (cg:CommodityGroup {commodityGroupID: row.`commodityGroupID:ID`})
SET cg.name = row.`name:string`;

// =================================================================
// 4. Import relationship data
// =================================================================

// Import relationship: Company -> OWNS -> Project
LOAD CSV WITH HEADERS FROM 'file:///rel_Owns.csv' AS row
MATCH (start:Company {companyID: row.`:START_ID`})
MATCH (end:Project {projectID: row.`:END_ID`})
MERGE (start)-[:OWNS]->(end);

// Import relationship: CompanyName -> REFERS_TO_COMPANY -> Company
LOAD CSV WITH HEADERS FROM 'file:///rel_Refers_to_Company.csv' AS row
MATCH (start:CompanyName {companyNameID: row.`:START_ID`})
MATCH (end:Company {companyID: row.`:END_ID`})
MERGE (start)-[:REFERS_TO_COMPANY {type: row.`type:string`}]->(end);

// Import relationship: Company -> DOMICILED_IN -> Country
LOAD CSV WITH HEADERS FROM 'file:///rel_Domiciled_in.csv' AS row
MATCH (start:Company {companyID: row.`:START_ID`})
MATCH (end:Country {countryID: row.`:END_ID`})
MERGE (start)-[:DOMICILED_IN]->(end);

// Import Company -> Classification relationships with a unified :CLASSIFIED_AS type
LOAD CSV WITH HEADERS FROM 'file:///rel_Classified_as_ICBSector.csv' AS row
    MATCH (start:Company {companyID: row.`:START_ID`})
    MATCH (end:ICBSector {icbsectorID: row.`:END_ID`})
    MERGE (start)-[:CLASSIFIED_AS {scheme: 'ICB', level: 'Sector'}]->(end);

LOAD CSV WITH HEADERS FROM 'file:///rel_Classified_as_ICBSubsector.csv' AS row
    MATCH (start:Company {companyID: row.`:START_ID`})
    MATCH (end:ICBSubsector {icbsubsectorID: row.`:END_ID`})
    MERGE (start)-[:CLASSIFIED_AS {scheme: 'ICB', level: 'Subsector'}]->(end);

LOAD CSV WITH HEADERS FROM 'file:///rel_Classified_as_GICSIndustry.csv' AS row
    MATCH (start:Company {companyID: row.`:START_ID`})
    MATCH (end:GICSIndustry {gicsindustryID: row.`:END_ID`})
    MERGE (start)-[:CLASSIFIED_AS {scheme: 'GICS', level: 'Industry'}]->(end);

LOAD CSV WITH HEADERS FROM 'file:///rel_Classified_as_GICSSubIndustry.csv' AS row
    MATCH (start:Company {companyID: row.`:START_ID`})
    MATCH (end:GICSSubIndustry {gicssubindustryID: row.`:END_ID`})
    MERGE (start)-[:CLASSIFIED_AS {scheme: 'GICS', level: 'SubIndustry'}]->(end);

LOAD CSV WITH HEADERS FROM 'file:///rel_Classified_as_BICSL3.csv' AS row
    MATCH (start:Company {companyID: row.`:START_ID`})
    MATCH (end:BICSL3 {bicsl3ID: row.`:END_ID`})
    MERGE (start)-[:CLASSIFIED_AS {scheme: 'BICS', level: 'L3 Industry'}]->(end);

LOAD CSV WITH HEADERS FROM 'file:///rel_Classified_as_BICSL4.csv' AS row
    MATCH (start:Company {companyID: row.`:START_ID`})
    MATCH (end:BICSL4 {bicsl4ID: row.`:END_ID`})
    MERGE (start)-[:CLASSIFIED_AS {scheme: 'BICS', level: 'L4 Sub Industry'}]->(end);

LOAD CSV WITH HEADERS FROM 'file:///rel_Classified_as_BICSL5.csv' AS row
    MATCH (start:Company {companyID: row.`:START_ID`})
    MATCH (end:BICSL5 {bicsl5ID: row.`:END_ID`})
    MERGE (start)-[:CLASSIFIED_AS {scheme: 'BICS', level: 'L5 Segment'}]->(end);

LOAD CSV WITH HEADERS FROM 'file:///rel_Classified_as_BICSL6.csv' AS row
    MATCH (start:Company {companyID: row.`:START_ID`})
    MATCH (end:BICSL6 {bicsl6ID: row.`:END_ID`})
    MERGE (start)-[:CLASSIFIED_AS {scheme: 'BICS', level: 'L6 Segment'}]->(end);

// Import Hierarchical Classification relationships
LOAD CSV WITH HEADERS FROM 'file:///rel_Part_of_ICBSubsector.csv' AS row MATCH (start:ICBSubsector {icbsubsectorID: row.`:START_ID`}) MATCH (end:ICBSector {icbsectorID: row.`:END_ID`}) MERGE (start)-[:PART_OF]->(end);
LOAD CSV WITH HEADERS FROM 'file:///rel_Part_of_GICSSubIndustry.csv' AS row MATCH (start:GICSSubIndustry {gicssubindustryID: row.`:START_ID`}) MATCH (end:GICSIndustry {gicsindustryID: row.`:END_ID`}) MERGE (start)-[:PART_OF]->(end);
LOAD CSV WITH HEADERS FROM 'file:///rel_Part_of_BICSL4.csv' AS row MATCH (start:BICSL4 {bicsl4ID: row.`:START_ID`}) MATCH (end:BICSL3 {bicsl3ID: row.`:END_ID`}) MERGE (start)-[:PART_OF]->(end);
LOAD CSV WITH HEADERS FROM 'file:///rel_Part_of_BICSL5.csv' AS row MATCH (start:BICSL5 {bicsl5ID: row.`:START_ID`}) MATCH (end:BICSL4 {bicsl4ID: row.`:END_ID`}) MERGE (start)-[:PART_OF]->(end);
LOAD CSV WITH HEADERS FROM 'file:///rel_Part_of_BICSL6.csv' AS row MATCH (start:BICSL6 {bicsl6ID: row.`:START_ID`}) MATCH (end:BICSL5 {bicsl5ID: row.`:END_ID`}) MERGE (start)-[:PART_OF]->(end);

// Import relationship: ProjectName -> REFERS_TO_PROJECT -> Project
LOAD CSV WITH HEADERS FROM 'file:///rel_Refers_to_Project.csv' AS row
MATCH (start:ProjectName {projectNameID: row.`:START_ID`})
MATCH (end:Project {projectID: row.`:END_ID`})
MERGE (start)-[:REFERS_TO_PROJECT]->(end);

// Import relationship: Project -> LOCATED_IN -> LGA
LOAD CSV WITH HEADERS FROM 'file:///rel_Project_Located_in_LGA.csv' AS row
MATCH (start:Project {projectID: row.`:START_ID`})
MATCH (end:LGA {lgaID: row.`:END_ID`})
MERGE (start)-[:LOCATED_IN]->(end);

// Import relationship: LGA -> LOCATED_IN -> State
LOAD CSV WITH HEADERS FROM 'file:///rel_LGA_Located_in_State.csv' AS row
MATCH (start:LGA {lgaID: row.`:START_ID`})
MATCH (end:State {stateID: row.`:END_ID`})
MERGE (start)-[:LOCATED_IN]->(end);

// Import relationship: Project -> HAS_COMMODITY -> Commodity
LOAD CSV WITH HEADERS FROM 'file:///rel_Has_Commodity.csv' AS row
MATCH (start:Project {projectID: row.`:START_ID`})
MATCH (end:Commodity {commodityID: row.`:END_ID`})
MERGE (start)-[:HAS_COMMODITY {role: row.`role:string`}]->(end);

// Import relationship: Commodity -> GROUPED_AS -> CommodityGroup
LOAD CSV WITH HEADERS FROM 'file:///rel_Grouped_as.csv' AS row
MATCH (start:Commodity {commodityID: row.`:START_ID`})
MATCH (end:CommodityGroup {commodityGroupID: row.`:END_ID`})
MERGE (start)-[:GROUPED_AS]->(end);