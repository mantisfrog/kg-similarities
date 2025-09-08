#  Mineral Deposit Knowledge Graph Similarities 💎

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A knowledge graph application for analyzing mineral deposit data from Geoscience Australia, featuring interactive exploration and similarity calculations using Jaccard coefficients.

## 📋 Table of Contents

- [Purpose](#purpose-)
- [Ontology Overview](#ontology-overview-)
- [Prerequisites](#prerequisites-)
- [Installation & Deployment](#installation--deployment-)
- [Features](#features-)
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

-   Python 3.8+
-   [Neo4j Database](https://neo4j.com/download/) (Desktop or Server)
-   [Streamlit](https://streamlit.io/)
-   Required Python packages (see `requirements.txt`)

## Installation & Deployment 🚀

### 1. Clone the Repository

```bash
git clone <repository-url>
cd kg-similarities
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Setup Neo4j Database

1.  Install and start your Neo4j instance.
2.  Create a new database (e.g., `neo4j`).
3.  Configure your application's connection parameters (URI, user, password).

### 4. Import Data 📊

1.  Place your CSV files into the `import` directory of your Neo4j database instance. The required files are:
    -   `node_Name.csv`
    -   `node_Company.csv`
    -   `node_Commodity.csv`
    -   `node_Deposit.csv`
    -   `rel_Refers_to.csv`
    -   `rel_Has.csv`
    -   `rel_Owns.csv`

2.  Execute the import script `cypher/import.cypher`. You can do this by:
    -   Pasting the contents of the file into the Neo4j Browser and running it.
    -   Using `cypher-shell`:
        ```bash
        cat cypher/import.cypher | cypher-shell -u <user> -p <password> -d <database>
        ```

### 5. Launch the Application

```bash
streamlit run app.py
```

The application will be available at `http://localhost:8501` 🎉

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
