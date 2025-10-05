// =================================================================
// 1. 清理数据库 (可选，确保从一个干净的状态开始)
// =================================================================
MATCH (n) DETACH DELETE n;

// =================================================================
// 2. 创建约束 (为了数据完整性和导入性能，至关重要)
// =================================================================
// 这会为每种节点的 ID 属性创建唯一性约束和索引
CREATE CONSTRAINT project_id_unique IF NOT EXISTS FOR (p:Project) REQUIRE p.projectID IS UNIQUE;
CREATE CONSTRAINT projectname_id_unique IF NOT EXISTS FOR (pn:ProjectName) REQUIRE pn.projectNameID IS UNIQUE;
CREATE CONSTRAINT state_id_unique IF NOT EXISTS FOR (s:State) REQUIRE s.stateID IS UNIQUE;
CREATE CONSTRAINT commodity_id_unique IF NOT EXISTS FOR (c:Commodity) REQUIRE c.commodityID IS UNIQUE;
CREATE CONSTRAINT company_id_unique IF NOT EXISTS FOR (c:Company) REQUIRE c.companyID IS UNIQUE;

// =================================================================
// 3. 导入节点数据
// =================================================================

// 导入 Project 节点
LOAD CSV WITH HEADERS FROM 'file:///node_Project.csv' AS row
MERGE (p:Project {projectID: row.`projectID:ID`})
SET p.eno = toInteger(row.`eno:int`),
    // 注意：这里的 location 是作为一个普通字符串导入的。
    // 要使其成为真正的地理空间 point 类型，Python 脚本最好生成独立的 lon/lat 列，
    // 然后在这里使用 SET p.location = point({longitude: toFloat(row.lon), latitude: toFloat(row.lat)})
    p.location = row.`location:point`,
    p.geologicAge = row.`geologicAge:string`,
    p.depositModelEnvironment = row.`depositModelEnvironment:string`,
    p.depositModelGroup = row.`depositModelGroup:string`,
    p.depositModelType = row.`depositModelType:string`,
    p.igneous = row.`igneous:string`,
    p.metallogenic = row.`metallogenic:string`,
    p.sedimentary = row.`sedimentary:string`,
    p.tectonic = row.`tectonic:string`;

// 导入 ProjectName 节点
LOAD CSV WITH HEADERS FROM 'file:///node_ProjectName.csv' AS row
MERGE (pn:ProjectName {projectNameID: row.`projectNameID:ID`})
SET pn.text = row.`text:string`;

// 导入 State 节点
LOAD CSV WITH HEADERS FROM 'file:///node_State.csv' AS row
MERGE (s:State {stateID: row.`stateID:ID`})
SET s.text = row.`text:string`;

// 导入 Commodity 节点
LOAD CSV WITH HEADERS FROM 'file:///node_Commodity.csv' AS row
MERGE (c:Commodity {commodityID: row.`commodityID:ID`})
SET c.symbol = row.`symbol:string`,
    c.name = row.`name:string`;

// 导入 Company 节点
LOAD CSV WITH HEADERS FROM 'file:///node_Company.csv' AS row
MERGE (c:Company {companyID: row.`companyID:ID`})
SET c.name = row.`name:string`;

// =================================================================
// 4. 导入关系数据
// =================================================================

// 导入关系: ProjectName -> REFERS_TO_PROJECT -> Project
LOAD CSV WITH HEADERS FROM 'file:///rel_Refers_to.csv' AS row
MATCH (start:ProjectName {projectNameID: row.`:START_ID`})
MATCH (end:Project {projectID: row.`:END_ID`})
MERGE (start)-[:REFERS_TO_PROJECT]->(end);

// 导入关系: Project -> LOCATED_IN -> State
LOAD CSV WITH HEADERS FROM 'file:///rel_Located_in.csv' AS row
MATCH (start:Project {projectID: row.`:START_ID`})
MATCH (end:State {stateID: row.`:END_ID`})
MERGE (start)-[:LOCATED_IN]->(end);

// 导入关系: Project -> HAS_COMMODITY -> Commodity
LOAD CSV WITH HEADERS FROM 'file:///rel_Has_Commodity.csv' AS row
MATCH (start:Project {projectID: row.`:START_ID`})
MATCH (end:Commodity {commodityID: row.`:END_ID`})
MERGE (start)-[:HAS_COMMODITY {role: row.`role:string`}]->(end);

// 导入关系: Company -> OWNS -> Project
LOAD CSV WITH HEADERS FROM 'file:///rel_Owns.csv' AS row
MATCH (start:Company {companyID: row.`:START_ID`})
MATCH (end:Project {projectID: row.`:END_ID`})
MERGE (start)-[:OWNS]->(end);