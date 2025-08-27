#!/usr/bin/env bash

# Exit immediately if a command exits with a non-zero status.
set -e

# --- Helper function for showing a spinner during a command ---
# Usage: run_with_spinner "Your descriptive message" "command_to_run"
run_with_spinner() {
    local message="$1"
    local command_to_run="$2"
    local spin='|/-\'
    
    echo -n "$message "
    
    # Run the command in the background and redirect its output
    # The output is saved to a temp file to be displayed on error
    local tmp_output
    tmp_output=$(mktemp)
    eval "$command_to_run" > "$tmp_output" 2>&1 &
    local pid=$!

    # Show spinner while the command is running
    while kill -0 $pid 2>/dev/null; do
        for i in $(seq 0 3); do
            echo -ne "\r$message ${spin:$i:1}"
            sleep 0.1
        done
    done
    
    # Check the command's exit code
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
        exit 1 # Exit the script due to the error
    fi
}

# --- Main Script Logic ---

echo -e "\n🚀 Starting the Neo4j Environment Setup..."

# [0/7] 只创建，不激活（激活必须在当前 shell 执行，不能放 spinner 里）
run_with_spinner "🆕 [0/7] Creating Python virtual environment..." "python3 -m venv .venv"
# 立刻在当前脚本的 shell 激活
# shellcheck source=/dev/null
source .venv/bin/activate

run_with_spinner "🐍 [1/7] Installing Python dependencies..." "pip install -r requirements.txt"
run_with_spinner "📊 [2/7] Converting JSON to CSV..." "python ./src/json2csv.py"
run_with_spinner "🔗 [3/7] Running spatial join..." "python ./src/spatial_join.py"

# For Docker commands, we want to see the output, so we run them directly
echo -e "\n🐳 [4/7] Pulling latest Neo4j Docker image..."
docker pull neo4j:latest
echo "✅ Image pull complete."

echo -e "\n🚀 [5/7] Starting Neo4j container via Docker Compose..."
docker compose up -d
echo "✅ Docker services started."

echo -e "\n🔑 [6/7] Adding permissions for ./neo4j-docker directory..."
if [ -d "./neo4j-docker" ]; then
    # This command requires sudo and will likely prompt for your password
    sudo chmod -R 777 ./neo4j-docker
    # Copy csv file to Neo4j import folder
    cp ./src/data/Deposits_spatial.csv ./neo4j-docker/import
    echo "✅ Permissions Added."
else
    echo "🟡 Directory ./neo4j-docker not found, skipping permission fix."
fi

# --- Countdown to allow Docker container to initialize ---
echo ""
for i in {19..0}; do
    echo -ne "Allowing Neo4j to initialize... $i second(s) \r"
    sleep 1
done
echo " " # Clear the line

# --- NEW: Import CSV into the graph with cypher_run.py ---
echo -e "\n🧩 [7/7] Importing CSV into Neo4j graph..."
python ./src/cypher_run.py
echo "✅ Graph import complete."
# --- Final success message with highlighted URL ---

# ANSI escape codes for formatting
BOLD="\033[1m"
GREEN="\033[32m"
BLUE="\033[34m"
UNDERLINE="\033[4m"
RESET="\033[0m"

echo -e "\n${GREEN}${BOLD} All steps completed successfully! Your Neo4j environment is ready.${RESET}"
echo -e "   You can access the Neo4j Browser at: ${BOLD}${UNDERLINE}${BLUE}http://localhost:7474${RESET}"
