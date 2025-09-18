MATCH (n) DETACH DELETE n;
CREATE CONSTRAINT Company_companyID IF NOT EXISTS FOR (c:Company) REQUIRE c.companyID IS UNIQUE;
CREATE CONSTRAINT Commodity_commodityID IF NOT EXISTS FOR (c:Commodity) REQUIRE c.commodityID IS UNIQUE;
CREATE CONSTRAINT Deposit_depositID IF NOT EXISTS FOR (d:Deposit) REQUIRE d.depositID IS UNIQUE;
CREATE CONSTRAINT DepositName_depositNameID IF NOT EXISTS FOR (n:DepositName) REQUIRE n.depositNameID IS UNIQUE;
CREATE CONSTRAINT CompanyName_companyNameID IF NOT EXISTS FOR (n:CompanyName) REQUIRE n.companyNameID IS UNIQUE;

// Load and create Node_Company
LOAD CSV WITH HEADERS FROM 'file:///node_Company.csv' AS row
MERGE (c:Company {companyID: row.`companyID:ID`});

// Load and create Node_CompanyName
LOAD CSV WITH HEADERS FROM 'file:///node_CompanyName.csv' AS row
MERGE (n:CompanyName {companyNameID: row.`companyNameID:ID`})
SET n.companyNameText = row.`companyNameText:string`;

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

// Load and create Node_DepositName
LOAD CSV WITH HEADERS FROM 'file:///node_DepositName.csv' AS row
MERGE (n:DepositName {depositNameID: row.`depositNameID:ID`})
SET n.depositNameText = row.`depositNameText:string`;

// Create rel_Refers_to_Deposit relationships
LOAD CSV WITH HEADERS FROM 'file:///rel_Refers_to_Deposit.csv' AS row
MATCH (n:DepositName {depositNameID: row.`:START_ID`})
MATCH (d:Deposit {depositID: row.`:END_ID`})
MERGE (n)-[:REFERS_TO_DEPOSIT]->(d);

// Create rel_Refers_to_Company relationships
LOAD CSV WITH HEADERS FROM 'file:///rel_Refers_to_Company.csv' AS row
MATCH (n:CompanyName {companyNameID: row.`:START_ID`})
MATCH (c:Company {companyID: row.`:END_ID`})
MERGE (n)-[:REFERS_TO_COMPANY]->(c);

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
