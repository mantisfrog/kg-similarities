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

echo -e "\n🚀 Starting the Neo4j Environment Setup..."

# [0/7] Create venv (no spinner for activate)
run_with_spinner "🆕 [0/7] Creating Python virtual environment..." "python3 -m venv .venv"
source .venv/bin/activate

# [1/7] Install dependencies
run_with_spinner "🐍 [1/7] Installing Python dependencies..." "pip install -r requirements.txt"

# [2/7] Pull Neo4j image
echo -e "\n🐳 [2/7] Pulling Neo4j Docker image..."
docker pull neo4j:5.26.12
echo "✅ Image pull complete."

# [3/7] Start Neo4j container
echo -e "\n🚀 [3/7] Starting Neo4j container via Docker Compose..."
docker compose up -d
# Wait for Neo4j to initialize
echo ""
for i in {9..0}; do
    echo -ne "\nAllowing Neo4j to initialize... $i second(s) \r"
    sleep 1
done
echo -e "\n✅ Docker services started."

echo " "

# [4/7] Load Pproject Datasets
run_with_spinner "📊 [4/7] Converting JSON to CSV..." "python ./src/etl/populate_projects.py"

# [5/7] Run Cleaning
run_with_spinner "🔗 [5/7] Cleaning names and filling missing values..." "python ./src/etl/clean_projects.py"

# [6/7] Fix permissions and copy CSV
echo -e "\n🔑 [6/7] Adding permissions for ./neo4j-docker directory..."
if [ -d "./neo4j-docker" ]; then
    # Use sudo only if necessary, or ensure user is in the docker group
    sudo chmod -R 777 ./neo4j-docker
    echo "✅ Permissions Added."
else
    echo "🟡 Directory ./neo4j-docker not found, skipping permission fix."
fi

# [7/7] Generate project graph CSVs and Import into Neo4j
echo -e "\n🧩 [7/7] Generating project graph files and importing into Neo4j..."

# First, generate the graph CSVs --- FILENAME CORRECTED
run_with_spinner "  -> Generating graph CSVs..." "python ./src/etl/generate_project_graph_csv.py"

# Then, add the commodity groups --- Assuming this script exists from your previous requests
run_with_spinner "  -> Categorising commodities..." "python ./src/feature/categorise_commodity.py"

# Copy CSV to import folder (after all graph CSVs are generated/modified)
if [ -d "./neo4j-docker/import" ]; then
    cp ./data/graph/*.csv ./neo4j-docker/import/
    echo "✅ Graph CSV files copied to Neo4j import."
else
    echo "🟡 Directory ./neo4j-docker/import not found, skipping copy."
fi

# Finally, run the Cypher script to load data --- FILENAME CORRECTED
run_with_spinner "  -> Loading data via Cypher..." "python ./src/etl/load_cyper.py"

echo "✅ Graph import process complete."

BOLD="\033[1m"
GREEN="\033[32m"
BLUE="\033[34m"
UNDERLINE="\033[4m"
RESET="\033[0m"

echo -e "\n${GREEN}${BOLD} All steps completed successfully! Your Neo4j environment is ready.${RESET}"
echo -e "   You can access the Neo4j Browser at: ${BOLD}${UNDERLINE}${BLUE}http://localhost:7474${RESET}"