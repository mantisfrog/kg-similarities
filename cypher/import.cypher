// Clear existing data (optional, for a clean import)
MATCH (n) DETACH DELETE n;

// Disable schema constraints during import for faster performance (APOC feature)
CALL apoc.schema.assert(
    {}, // no constraints
    {
        Name: ["nameID"],
        Company: ["companyID"],
        Commodity: ["commodityID"],
        Deposit: ["depositID"]
    }
);

// Load and create Node_Name
LOAD CSV WITH HEADERS FROM 'file:///node_Name.csv' AS row
MERGE (n:Name {nameID: row.`nameID:ID`})
SET n.nameText = row.`nameText:string`;

// Load and create Node_Company
LOAD CSV WITH HEADERS FROM 'file:///node_Company.csv' AS row
MERGE (c:Company {companyID: row.`companyID:ID`})
SET c.companyName = row.`companyName:string`; 

// Load and create Node_Commodity
LOAD CSV WITH HEADERS FROM 'file:///node_Commodity.csv' AS row
MERGE (c:Commodity {commodityID: row.`commodityID:ID`})
SET c.commoditySymbol = row.`commoditySymbol:string`,
    c.commodityDesc = row.`commodityName:string`,
    c.commodityGroup = row.`commodityGroup:string`;

// Load and create Node_Deposit
LOAD CSV WITH HEADERS FROM 'file:///node_Deposit.csv' AS row
MERGE (d:Deposit {depositID: row.`depositID:ID`})
SET d.eno = toInteger(row.`ENO:int`),
    d.state = row.`STATE:string`,
    d.location = row.`LOCATION:string`,
    d.operatingStatus = row.`OPERATING_STATUS:string`,
    d.geologicAge = row.`GEOLOGIC_AGE:string`,
    d.depositModelEnvironment = row.`DEPOSIT_MODEL_ENVIRONMENT:string`,
    d.depositModelGroup = row.`DEPOSIT_MODEL_GROUP:string`,
    d.depositModelType = row.`DEPOSIT_MODEL_TYPE:string`,
    d.provinces = row.`PROVINCES:string`,
    d.igneous = row.`IGNEOUS:string`,
    d.metallogenic = row.`METALLOGENIC:string`,
    d.sedimentary = row.`SEDIMENTARY:string`,
    d.tectonic = row.`TECTONIC:string`;

// Create rel_Refers_to relationships
LOAD CSV WITH HEADERS FROM 'file:///rel_Refers_to.csv' AS row
MATCH (n:Name {nameID: row.`:START_ID`})
MATCH (d:Deposit {depositID: row.`:END_ID`})
MERGE (n)-[:REFERS_TO]->(d);

// Create rel_Has relationships
LOAD CSV WITH HEADERS FROM 'file:///rel_Has.csv' AS row
MATCH (d:Deposit {depositID: row.`:START_ID`})
MATCH (c:Commodity {commodityID: row.`:END_ID`})
MERGE (d)-[:HAS {role: row.`ROLE:string`}]->(c);

// Create rel_Owns relationships
LOAD CSV WITH HEADERS FROM 'file:///rel_Owns.csv' AS row
MATCH (c:Company {companyID: row.`:START_ID`})
MATCH (d:Deposit {depositID: row.`:END_ID`})
MERGE (c)-[:OWNS]->(d);

// Re-enable schema constraints after import (APOC feature)
CALL apoc.schema.assert(
    {
        Name: ["nameID"],
        Company: ["companyID"],
        Commodity: ["commodityID"],
        Deposit: ["depositID"]
    },
    {} // no indexes
);

