# GitHub MCP Server

This project is a complete [Model Context Protocol (MCP)](https://github.com/mcprotocol) server that exposes GitHub functionality for LLMs like Claude.

It allows natural language control over GitHub via Claude using 30+ tools, including pull requests, branches, issues, actions, commits, analytics, and more.

---

## 🚀 Features

All GitHub operations are accessible through natural language:

### 🔁 Pull Requests

* Create, list, view, and merge PRs

### 📦 Repository Management

* Create repositories
* List and fetch repo metadata

### 🌿 Branch Operations

* List, create, delete branches

### 🐞 Issues

* Create, list, and update issues
* Add labels or close issues

### 🏷️ Releases & Tags

* Create and list GitHub releases

### ⚙️ GitHub Actions

* List workflows
* Trigger workflows
* View recent workflow runs

### 📝 Commits

* List recent commits
* Get commit details

### 📊 Analytics

* Get repository statistics
* View contributor activity
* Analyze commit trends

### 👥 Collaboration

* Add collaborators to repos
* List existing collaborators

### 📁 File Operations

* Read files from repos
* Create or update files with commits

### 🔍 Search

* Search repositories
* Search for code in a repo or globally

---

## 🛠️ Installation

#### Option A: Clone via Git

```bash
git clone https://github.com/your-username/github-mcp-server.git
cd github-mcp-server
```

#### Option B: Manual Download

Save these files to a new folder:

* `github_server.py`
* `install.sh` (Linux/macOS)
* `install.bat` (Windows)
* `.gitignore`
* `README.md` (optional)

---

### 🧪 Step 2 – Run the Installer

#### ▶️ On Linux/macOS

```
bash
```

CopyEdit

`chmod +x install.sh ./install.sh`

#### ▶️ On Windows

Double-click `install.bat` or run it in terminal:

```
bat
```

CopyEdit

`install.bat`

These scripts:

* Create a Python virtual environment in `./venv`
* Activate the environment
* Install required packages: `httpx`, `pydantic`, `mcp`

---

### 🔐 Step 3 – Set GitHub Token

The server requires a GitHub token for API access.

#### Create a Token:

* Go to: [https://github.com/settings/tokens](https://github.com/settings/tokens)
* Generate a Personal Access Token (Classic) with scopes:

  * `repo`
  * `workflow`
  * *(optional)* `admin:repo_hook` if planning to extend

#### Set the token in your environment:

**On Linux/macOS**

```
bash
```

CopyEdit

`export GITHUB_TOKEN=ghp_your_token_here`

**On Windows (CMD)**

```
bat
```

CopyEdit

`set GITHUB_TOKEN=ghp_your_token_here`

💡 *You can also store it permanently in a **`.env`** file and load it via **`python-dotenv`**.*

---

### ▶️ Step 4 – Start the MCP Server

Run the following from the root of the project:

```
bash
```

CopyEdit

`python github_server.py`

The server will listen over **stdio** and respond to MCP-compliant model requests.

---

### 🤖 Step 5 – Connect via Claude (or another LLM)

Once the server is running, Claude can use the defined tools to operate GitHub entirely through natural language.

#### ✅ Example Prompts:

* “Create a new repo named `alpha-project`”
* “List open PRs in `weezboo/frontend`”
* “Trigger workflow `ci.yml` on branch `main`”
* “Read the file `server/settings.yml` from `main`”

The MCP protocol routes these requests to the correct tool via schema-matched JSON.
