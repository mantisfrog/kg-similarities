#  Mineral Deposit Knowledge Graph Similarities 💎

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A knowledge graph application for analyzing mineral deposit data from Geoscience Australia, featuring interactive exploration and similarity calculations using Jaccard coefficients.

## 📋 Table of Contents

- [Purpose](#purpose-)
- [Ontology Overview](#ontology-overview-)
- [Prerequisites](#prerequisites-)
- [Installation & Deployment](#installation--deployment-)
- [Features](#features-)
- [Frontend Example Queries](#frontend-example-queries-)
- [Usage Examples](#usage-examples-)
- [Data Sources](#data-sources-)
- [Contributing](#contributing-)
- [License](#license-)
- [Acknowledgments](#acknowledgments-)

## Purpose 🎯

This project transforms Geoscience Australia's Mineral Deposit dataset into a comprehensive knowledge graph. It enables researchers and analysts to:

- 🗺️ Explore relationships between mineral deposits, commodities, companies, and location names.
- ➗ Calculate similarities between deposits using Jaccard similarity metrics.
- 🖥️ Interactively query and visualize mineral deposit data via a Streamlit frontend.
- 📈 Analyze patterns in mineral distribution and ownership.

## Ontology Overview 🧬

The knowledge graph is built from the Geoscience Australia dataset, connecting deposits with their commodities, operating companies, and names.

### Entities (Nodes)

-   **(📍 Name)**: Location names and identifiers.
    -   `nameID`, `nameText`
-   **(🏢 Company)**: Mining companies and operators.
    -   `companyID`, `companyName`
-   **(⛏️ Commodity)**: Mineral commodities and resources.
    -   `commodityID`, `commoditySymbol`, `commodityDesc`, `commodityGroup`
-   **(🌍 Deposit)**: Mineral deposits with detailed geological information.
    -   `depositID`, `eno`, `state`, `location`, `operatingStatus`, `geologicAge`, `depositModelEnvironment`, `depositModelGroup`, `depositModelType`, `provinces`, `igneous`, `metallogenic`, `sedimentary`, `tectonic`

### Relationships (Edges)

-   `(:Name)-[:REFERS_TO]->(:Deposit)`: Connects a name to a deposit.
-   `(:Deposit)-[:HAS {role: string}]->(:Commodity)`: Links a deposit to a commodity, specifying the commodity's role (e.g., "Primary").
-   `(:Company)-[:OWNS]->(:Deposit)`: Shows which company owns a deposit.

## Prerequisites 🛠️

-   Python 3.9+
-   [Neo4j Database](https://neo4j.com/download/) (Desktop or Server)
-   [Streamlit](https://streamlit.io/)
-   Required Python packages (see `requirements.txt`)

⚠️ Important: Python >= 3.9 is required. Check your version:

```bash
python3 --version
```

## Installation & Deployment 🚀

### 1. Clone the Repository

```bash
git clone <repository-url>
cd kg-similarities
```

### 2. Make scripts executable (one-time) 🔐

```bash
chmod +x install.sh frontend.sh
```

### 3. Install and import via script ⚙️

```bash
./install.sh
```

- Installs Python dependencies and executes `cypher/import.cypher`.
- Ensure CSVs are in Neo4j’s `import` directory before running.

### 4. Configure API Keys 🔑

Create a `secrets.toml` file in the `apps/streamlit/.streamlit/` directory with your API keys (replace placeholders with actual values):

```toml
GOOGLE_GENAI_API_KEY = "{Your API Key}"
OPENAI_API_KEY = "{Your API Key}"
NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "neo4jroot"
```

This file is required for the Streamlit app to connect to Neo4j and use AI features.

### 5. Launch the frontend 🚀

```bash
./frontend.sh
```

The application will be available at `http://localhost:8501` 🎉

> Optional manual setup (only if not using scripts):
> - `pip install -r requirements.txt`
> - Import using Neo4j Browser or:
>   ```bash
>   cat cypher/import.cypher | cypher-shell -u <user> -p <password> -d <database>
>   ```
> - Start: `streamlit run app.py`

## Features ✨

### Interactive Exploration
- 🧭 Browse mineral deposits by location, commodity, or company.
- 🕸️ Visualize relationships in the knowledge graph.
- 🔍 Filter and search across all entity types.

### Similarity Analysis
- ➗ Calculate Jaccard similarity between mineral deposits.
- ⚖️ Compare deposits based on:
  - Commodity portfolios
  - Geological characteristics
  - Company ownership patterns

### Data Insights
- 📊 Analyze commodity distribution patterns.
- 💡 Identify similar deposit types.
- 📂 Explore company portfolios.

## Frontend Example Queries 🔎

Run these in the Streamlit UI (or Neo4j Browser) to verify end-to-end behavior.

1) Who are the top five companies that own the most gold mines?
Expected result:
```cypher
MATCH (comp:Company)-[:OWNS]->(d:Deposit)-[:HAS]->(c:Commodity)
WHERE toLower(c.commodityDesc) CONTAINS 'gold'
RETURN comp.companyName AS companyName, count(DISTINCT d.depositID) AS goldMineCount
ORDER BY goldMineCount DESC
LIMIT 5
```
Take off attributes ".companyName" in order to show visuals in Neo4j Browser(http://localhost:7474/browser/)

2) Find a path between a company containing 'bhp' and a company containing 'rio tinto'. The path goes through their deposits to a common commodity which must contain 'iron ore' in its description. Return the path and both companies.
Expected result:
```cypher
MATCH p = (comp:Company)-[:OWNS]->(d1:Deposit)-[:HAS]->(c:Commodity)<-[:HAS]-(d2:Deposit)<-[:OWNS]-(comp2:Company)
WHERE toLower(comp.companyName) CONTAINS 'bhp'
  AND toLower(comp2.companyName) CONTAINS 'rio tinto'
  AND toLower(c.commodityDesc) CONTAINS 'iron ore'
  AND comp <> comp2
RETURN p, comp, comp2;
```

Tip: For better match rate, use CONTAINS in prompt.

## Usage Examples 🧑‍💻

### Finding Similar Deposits
1. Select a deposit of interest.
2. Choose similarity criteria (commodities, geology, etc.).
3. View a ranked list of similar deposits with their Jaccard scores.
4. Explore detailed comparisons.

### Company Analysis
1. Search for a mining company.
2. View all owned deposits.
3. Analyze the company's commodity portfolio.
4. Compare with other companies.

### Commodity Exploration
1. Select a commodity type.
2. View all associated deposits.
3. Analyze the geographical distribution of the commodity.
4. Identify major producers.

## Data Sources 📚

-   **Primary Dataset**: Geoscience Australia Mineral Deposit Database
-   **Data Format**: CSV files with standardized schemas
-   **Update Frequency**: Based on Geoscience Australia data releases

## Contributing 🤝

1.  Fork the repository.
2.  Create a feature branch (`git checkout -b feature/AmazingFeature`).
3.  Commit your changes (`git commit -m 'Add some AmazingFeature'`).
4.  Push to the branch (`git push origin feature/AmazingFeature`).
5.  Open a Pull Request.

## License 📄

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## Acknowledgments 🙏

-   **Geoscience Australia** for providing the mineral deposit dataset.
-   The **Neo4j** community for graph database technologies.
-   The **Streamlit** team for the interactive web framework.
