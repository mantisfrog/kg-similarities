// =================================================================
// 1. Clean up the database
// =================================================================
MATCH (n) DETACH DELETE n;
CALL apoc.schema.assert({}, {});
// =================================================================
// 2. Create constraints
// =================================================================
// This creates a uniqueness constraint and index for the ID property of each node type
CREATE CONSTRAINT project_id_unique IF NOT EXISTS FOR (p:Project) REQUIRE p.projectID IS UNIQUE;
CREATE CONSTRAINT projectname_id_unique IF NOT EXISTS FOR (pn:ProjectName) REQUIRE pn.projectNameID IS UNIQUE;
CREATE CONSTRAINT state_id_unique IF NOT EXISTS FOR (s:State) REQUIRE s.stateID IS UNIQUE;
CREATE CONSTRAINT commodity_id_unique IF NOT EXISTS FOR (c:Commodity) REQUIRE c.commodityID IS UNIQUE;

// =================================================================
// 3. Import node data
// =================================================================

// Import Project nodes
LOAD CSV WITH HEADERS FROM 'file:///node_Project.csv' AS row
MERGE (p:Project {projectID: row.`projectID:ID`})
SET p.eno = toInteger(row.`eno:int`),
    // Note: The location here is imported as a plain string.
    // To make it a true geospatial point type, the Python script should ideally generate separate lon/lat columns,
    // and then use SET p.location = point({longitude: toFloat(row.lon), latitude: toFloat(row.lat)}) here.
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

// Import Commodity nodes
LOAD CSV WITH HEADERS FROM 'file:///node_Commodity.csv' AS row
MERGE (c:Commodity {commodityID: row.`commodityID:ID`})
SET c.symbol = row.`symbol:string`,
    c.name = row.`name:string`;

// =================================================================
// 4. Import relationship data
// =================================================================

// Import relationship: ProjectName -> REFERS_TO_PROJECT -> Project
LOAD CSV WITH HEADERS FROM 'file:///rel_Refers_to.csv' AS row
MATCH (start:ProjectName {projectNameID: row.`:START_ID`})
MATCH (end:Project {projectID: row.`:END_ID`})
MERGE (start)-[:REFERS_TO_PROJECT]->(end);

// Import relationship: Project -> LOCATED_IN -> State
LOAD CSV WITH HEADERS FROM 'file:///rel_Located_in.csv' AS row
MATCH (start:Project {projectID: row.`:START_ID`})
MATCH (end:State {stateID: row.`:END_ID`})
MERGE (start)-[:LOCATED_IN]->(end);

// Import relationship: Project -> HAS_COMMODITY -> Commodity
LOAD CSV WITH HEADERS FROM 'file:///rel_Has_Commodity.csv' AS row
MATCH (start:Project {projectID: row.`:START_ID`})
MATCH (end:Commodity {commodityID: row.`:END_ID`})
MERGE (start)-[:HAS_COMMODITY {role: row.`role:string`}]->(end);