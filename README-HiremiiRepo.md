
# Hiremii-Shortlist

This repository contains models and resources for knowledge graph improvements. One important large file is stored using **Git LFS (Large File Storage)**:

```

models/KnowledgeGraphs/company\_graph.txt

````

If you only download the ZIP from GitHub, this file will not be included properly. To get the repository **and** the large file, follow the steps below.

---

## 🔧 Step 1. Install Git and Git LFS

### 🖥️ Windows
1. Install **Git for Windows**: [https://git-scm.com/download/win](https://git-scm.com/download/win) (During installation, keep default options. You’ll also get **Git Bash**.)  
2. Install **Git LFS**: [https://git-lfs.github.com/](https://git-lfs.github.com/)  
3. Open **Git Bash** and run:  
   ```bash
   git lfs install

### 🍎 macOS

1. Open **Terminal**. If you don’t have **Homebrew**, install it:

   ```bash
   /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
   ```
2. Install Git and Git LFS:

   ```bash
   brew install git
   brew install git-lfs
   git lfs install
   ```

---

## 📥 Step 2. Clone the Repository

Run the following in Git Bash (Windows) or Terminal (macOS):

```bash
git clone https://github.com/Veloceo/Hiremii-Shortlist.git
cd Hiremii-Shortlist
```

---

## 📂 Step 3. Download the LFS File

Run:

```bash
git lfs pull
```

This will fetch `company_graph.txt` and any other LFS-tracked files.

---

## ✅ Step 4. Verify the File

Check that the file is large (MBs, not KBs):

* On macOS/Linux:

  ```bash
  ls -lh models/KnowledgeGraphs/company_graph.txt
  ```
* On Windows (PowerShell):

  ```powershell
  dir models\KnowledgeGraphs\company_graph.txt
  ```

---

🎉 Done! You now have the full repository and the large file `company_graph.txt` on your local machine.