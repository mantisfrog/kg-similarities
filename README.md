# 🚀 Neo4j Environment Setup Guide

This guide will help you set up and run the Neo4j environment for this project.
You **do not need prior Git or Linux experience** — just follow the steps carefully.

---

## 1. 📦 Install Required Software

Before running the setup script, make sure the following tools are installed on your computer:

### Windows (Recommended: WSL2 + Ubuntu)

1. Install **Docker Desktop for Windows**
   👉 [https://docs.docker.com/desktop/install/windows/](https://docs.docker.com/desktop/install/windows/)

2. Install **Windows Subsystem for Linux (WSL2)** and Ubuntu:
   👉 [https://learn.microsoft.com/en-us/windows/wsl/install](https://learn.microsoft.com/en-us/windows/wsl/install)

3. Install **Git** (to download the project):

   ```bash
   sudo apt install -y git
   ```

---

### macOS

1. Install **Homebrew** (package manager):
   👉 [https://brew.sh/](https://brew.sh/)

2. Install required software:

   ```bash
   brew install python git docker
   ```

3. Install **Docker Desktop for Mac**:
   👉 [https://docs.docker.com/desktop/install/mac/](https://docs.docker.com/desktop/install/mac/)

---

## 2. 📥 Download the Project

Open a **terminal** (on macOS) or **Ubuntu (WSL2)** (on Windows), then run:

```bash
git clone -b develop https://github.com/mantisfrog/kg-similarities.git
cd kg-similarities
```

---

## 3. ▶️ Run the Installation Script

Inside the project folder, run:

```bash
bash install.sh
```

The script will automatically:

1. Create a Python virtual environment
2. Install dependencies
3. Convert JSON to CSV
4. Run spatial join preprocessing
5. Pull the Neo4j Docker image
6. Start Neo4j with Docker Compose
7. Import CSV into Neo4j graph

You will see a spinner (`| / - \`) showing progress for each step.

---

## 4. 🌐 Access Neo4j Browser

After the script finishes, open your browser and go to:

👉 [http://localhost:7474](http://localhost:7474)

Default login:

* **Username:** `neo4j`
* **Password:** `neo4jroot`

---

## 5. 📊 Sample Queries

Here are some example Cypher queries you can run inside the **Neo4j Browser**:

### 1. Show deposits in Western Australia (WA)

```cypher
MATCH (d:Deposit)
WHERE d.STATE = 'WA'
RETURN d
LIMIT 20;
```

### 2. Show deposits where the primary commodity is **Gold (Au)**

```cypher
MATCH (d:Deposit)-[r:HAS_COMMODITY {role:'PRIMARY'}]->(c:Commodity)
WHERE toUpper(c.name) = 'AU'
RETURN d, r, c
LIMIT 20;
```

### 3. Show deposits in WA where the primary commodity is **Gold (Au)**

```cypher
MATCH (d:Deposit)-[r:HAS_COMMODITY {role:'PRIMARY'}]->(c:Commodity)
WHERE toUpper(c.name) = 'AU'
  AND d.STATE = 'WA'
RETURN d
LIMIT 20;
```

---

## 6. ✅ Troubleshooting

* If you see **permission errors** on Linux/macOS:
  Try running the script with `sudo`:

  ```bash
  sudo bash install.sh
  ```

* If Neo4j does not start, make sure **Docker Desktop** is running.

* To stop Neo4j:

  ```bash
  docker compose down
  ```

* To restart Neo4j:

  ```bash
  docker compose up -d
  ```

---

## 🎉 Done!

If everything works, you should see the Neo4j Browser at:
👉 [http://localhost:7474](http://localhost:7474)

Now you are ready to explore your graph database with your own queries! 🚀
