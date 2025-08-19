// ========= 1) Constraints =========
CREATE CONSTRAINT deposit_eno IF NOT EXISTS
FOR (d:Deposit) REQUIRE d.ENO IS UNIQUE;

CREATE CONSTRAINT commodity_name IF NOT EXISTS
FOR (c:Commodity) REQUIRE c.name IS UNIQUE;

// ========= 2) Create Deposit nodes =========
CALL () {
  LOAD CSV WITH HEADERS FROM 'file:///Deposits_spatial.csv' AS row FIELDTERMINATOR ','
  MERGE (d:Deposit {ENO: row.ENO})
  SET
    d.name             = row.DEPOSIT_NAME,
    d.DEPOSIT_NAME     = row.DEPOSIT_NAME,
    d.SYNONYMS         = row.SYNONYMS,
    d.STATE            = row.STATE,
    d.LONG_GDA94       = CASE WHEN row.LONG_GDA94 IS NULL OR trim(row.LONG_GDA94) = '' THEN NULL ELSE toFloat(row.LONG_GDA94) END,
    d.LAT_GDA94        = CASE WHEN row.LAT_GDA94  IS NULL OR trim(row.LAT_GDA94)  = '' THEN NULL ELSE toFloat(row.LAT_GDA94)  END,
    d.OPERATING_STATUS = row.OPERATING_STATUS,
    d.COMPANIES        = row.COMPANIES,
    d.COMMODITY_NAMES  = row.COMMODITY_NAMES
} IN TRANSACTIONS OF 1000 ROWS;


// ========= 3) Create PRIMARY relationships =========
CALL () {
  LOAD CSV WITH HEADERS FROM 'file:///Deposits_spatial.csv' AS row FIELDTERMINATOR ','
  WITH row,
    CASE
      WHEN row.COMMODITY_PRIMARY IS NULL OR trim(row.COMMODITY_PRIMARY) = '' THEN []
      ELSE [x IN split(row.COMMODITY_PRIMARY, ',') | trim(x)]
    END AS prims
  MATCH (d:Deposit {ENO: row.ENO})
  UNWIND prims AS p
  WITH d, p WHERE p <> ''
  MERGE (c:Commodity {name: p})
  MERGE (d)-[r:HAS_COMMODITY]->(c)
  ON CREATE SET r.role = 'PRIMARY'
} IN TRANSACTIONS OF 1000 ROWS;


// ========= 4) Create SECONDARY relationships =========
CALL () {
  LOAD CSV WITH HEADERS FROM 'file:///Deposits_spatial.csv' AS row FIELDTERMINATOR ','
  WITH row,
    CASE
      WHEN row.COMMODITY_SECONDARY IS NULL OR trim(row.COMMODITY_SECONDARY) = '' THEN []
      ELSE [x IN split(row.COMMODITY_SECONDARY, ',') | trim(x)]
    END AS secs
  MATCH (d:Deposit {ENO: row.ENO})
  UNWIND secs AS s
  WITH d, s WHERE s <> ''
  MERGE (c:Commodity {name: s})
  MERGE (d)-[r:HAS_COMMODITY]->(c)
  ON CREATE SET r.role = 'SECONDARY'
  ON MATCH SET r.role = r.role
} IN TRANSACTIONS OF 1000 ROWS;
  