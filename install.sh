#!/usr/bin/env bash

set -e

run_with_spinner() {
    local message="$1"
    local command_to_run="$2"
    local spin='|/-\'
    echo -n "$message "
    local tmp_output
    tmp_output=$(mktemp)
    eval "$command_to_run" > "$tmp_output" 2>&1 &
    local pid=$!
    while kill -0 $pid 2>/dev/null; do
        for i in $(seq 0 3); do
            echo -ne "\r$message ${spin:$i:1}"
            sleep 0.1
        done
    done
    wait $pid
    local exit_code=$?
    if [ $exit_code -eq 0 ]; then
        echo -e "\r$message ✅"
        rm -f "$tmp_output"
    else
        echo -e "\r$message ❌"
        echo -e "\n--- Error Log ---"
        cat "$tmp_output"
        echo "-----------------"
        rm -f "$tmp_output"
        exit 1
    fi
}

echo -e "\n🚀 Starting the KG Environment Setup..."

# [1/5] Python Environment Setup
echo -e "\n🐍 [1/5] Setting up Python virtual environment..."
run_with_spinner "  -> Creating Python virtual environment..." "python3 -m venv .venv"
source .venv/bin/activate
run_with_spinner "  -> Installing Python dependencies..." "pip install -r requirements.txt"
echo "✅ Python environment is ready."

# [2/5] Neo4j Docker Setup
echo -e "\n🐳 [2/5] Setting up Neo4j Docker container..."
run_with_spinner "  -> Pulling Neo4j Docker image (neo4j:5.26.12)..." "docker pull neo4j:5.26.12"
echo "  -> Starting Neo4j container via Docker Compose..."
docker compose up -d
echo -e "\n✅ Docker services started."

# [3/5] Process Project Data
echo -e "\n📊 [3/5] Processing Project datasets..."
run_with_spinner "  -> Converting project JSON to CSV..." "python ./src/etl/populate_projects.py"
run_with_spinner "  -> Enriching project data with geospatial information..." "python ./src/feature/enrich_geospatial.py"
run_with_spinner "  -> Generating project graph CSVs..." "python ./src/etl/generate_project_graph_csv.py"
run_with_spinner "  -> Categorising commodities..." "python ./src/feature/categorise_commodity.py"
echo "✅ Project data processed."

# [4/5] Process Company Data
echo -e "\n🏢 [4/5] Processing Company datasets..."
echo "  -> Running company data ETL pipeline (output will be displayed below)..."
python src/etl/populate_bloomberg_company.py && \
       python src/etl/merge_company_data.py && \
       python src/etl/match_names_json_bloomberg_linkedin.py && \
       python src/etl/find_former_names.py && \
       python src/etl/add_company_alias.py && \
       python src/etl/generate_company_graph_csv.py && \
       python src/feature/categorise_company.py && \
       python src/feature/generate_categorise_reserves_node.py
echo "✅ Company data processed."

# [5/5] Load Graph into Neo4j
echo -e "\n🧩 [5/5] Loading all data into Neo4j..."

# Fix permissions for import directory
echo "  -> Adding permissions for ./neo4j-docker directory..."
if [ -d "./neo4j-docker" ]; then
    sudo chmod -R 777 ./neo4j-docker
    echo "✅ Permissions Added."
else
    echo "🟡 Directory ./neo4j-docker not found, skipping permission fix."
fi

# Copy all generated CSVs to import folder
if [ -d "./neo4j-docker/import" ]; then
    echo "  -> Cleaning import directory..."
    rm -f ./neo4j-docker/import/*
    echo "  -> Copying graph CSVs to Neo4j import directory..."
    cp ./data/graph/*.csv ./neo4j-docker/import/
    echo "✅ Graph CSV files copied."
else
    echo "🟡 Directory ./neo4j-docker/import not found, skipping copy."
fi

# Run the Cypher script to load data
run_with_spinner "  -> Loading data via Cypher script..." "python ./src/etl/load_cypher.py"
echo "✅ Graph import process complete."


BOLD="\033[1m"
GREEN="\033[32m"
BLUE="\033[34m"
UNDERLINE="\033[4m"
RESET="\033[0m"

echo -e "\n${GREEN}${BOLD} All steps completed successfully! Your Neo4j environment is ready.${RESET}"
echo -e "   You can access the Neo4j Browser at: ${BOLD}${UNDERLINE}${BLUE}http://localhost:7474${RESET}"

# --- Optional: Start Model Training ---
echo -e "\n🧠 ${BOLD}[Optional] Start Model Training${RESET}"
echo -e "The environment is set up. You can now train the embedding model."
echo -e "⚠️  ${BOLD}Warning:${RESET} The default training process can take several hours."
echo -e "   You can adjust hyperparameters in ${BOLD}analysis/train_metapath2vec.py${RESET} or by using environment variables"
echo -e "   (e.g., MP2V_EPOCHS=5) for a shorter run."

while true; do
    read -p "Do you want to start the training now? (y/n): " yn
    case $yn in
        [Yy]* )
            echo -e "\n🚀 Starting training process..."

            echo -e "\n[1/2] Creating PyG HeteroData object from Neo4j..."
            run_with_spinner "  -> Running create_heterodata.py..." "python src/analysis/create_heterodata.py"

            echo -e "\n[2/2] Training MetaPath2Vec model..."
            echo "  -> Running train_metapath2vec.py (this will take a while, progress will be shown below)..."
            python src/analysis/train_metapath2vec.py

            echo -e "\n${GREEN}${BOLD}✅ Training finished successfully!${RESET}"
            break;;
        [Nn]* )
            echo -e "\nSkipping training. You can run it later with the following commands:"
            echo -e "   ${BOLD}source .venv/bin/activate${RESET}"
            echo -e "   ${BOLD}python src/analysis/create_heterodata.py${RESET}"
            echo -e "   ${BOLD}python src/analysis/train_metapath2vec.py${RESET}"
            exit;;
        * ) echo "Please answer yes (y) or no (n).";;
    esac
done

echo -e "\nSetup and training process complete."