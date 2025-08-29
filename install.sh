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
echo -e "\n🐳 [2/7] Pulling latest Neo4j Docker image..."
docker pull neo4j:latest
echo "✅ Image pull complete."

# [3/7] Start Neo4j container
echo -e "\n🚀 [3/7] Starting Neo4j container via Docker Compose..."
docker compose up -d
echo "✅ Docker services started."

# [4/7] Fix permissions and copy CSV
echo -e "\n🔑 [4/7] Adding permissions for ./neo4j-docker directory..."
if [ -d "./neo4j-docker" ]; then
    sudo chmod -R 777 ./neo4j-docker
    echo "✅ Permissions Added."
else
    echo "🟡 Directory ./neo4j-docker not found, skipping permission fix."
fi

# [5/7] Convert JSON to CSV
run_with_spinner "📊 [5/7] Converting JSON to CSV..." "python ./src/json2csv.py"

# [6/7] Run spatial join
run_with_spinner "🔗 [6/7] Running spatial join..." "python ./src/spatial_join.py"

# Copy CSV to import folder (after spatial join output exists)
if [ -d "./neo4j-docker" ]; then
    cp ./data/processed/Deposits_spatial.csv ./neo4j-docker/import
    echo "✅ Deposits_spatial.csv copied to Neo4j import."
fi

# Wait for Neo4j to initialize
echo ""
for i in {3..0}; do
    echo -ne "Allowing Neo4j to initialize... $i second(s) \r"
    sleep 1
done
echo " "

# [7/7] Import CSV into Neo4j
echo -e "\n🧩 [7/7] Importing CSV into Neo4j graph..."
python ./src/cypher_run.py
echo "✅ Graph import complete."

BOLD="\033[1m"
GREEN="\033[32m"
BLUE="\033[34m"
UNDERLINE="\033[4m"
RESET="\033[0m"

echo -e "\n${GREEN}${BOLD} All steps completed successfully! Your Neo4j environment is ready.${RESET}"
echo -e "   You can access the Neo4j Browser at: ${BOLD}${UNDERLINE}${BLUE}http://localhost:7474${RESET}"
