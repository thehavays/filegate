# Git & GitHub Workflow Guidelines for FileGate

This document defines the version control, branching, and GitHub MCP conventions used in `filegate`.

---

## ⚙️ Environment & MCP Context

* **GITHUB_USERNAME**: `thehavays`
* **REPOSITORY**: `filegate`
* **REMOTE_URL**: `https://github.com/thehavays/filegate.git`
* **MCP_SERVER**: `github`

---

## 🌿 Branching Strategy

We use a standard two-tier branching structure with `dev` as the primary integration branch. Both `main` and `dev` are **protected branches**:

1. **`dev` (Integration Branch)**:
   * The default branch for active development.
   * All feature branches, bug fixes, and chores branch from `dev` and merge back into `dev`.
2. **`main` (Production Branch)**:
   * Holds the stable production release code.
   * Periodically, `dev` is merged into `main` via a Release Pull Request.

### 🛡️ Branch Protection Rules

* **Direct Pushes**: Direct pushes to `main` and `dev` are strictly forbidden. All changes must be delivered via Pull Requests.
* **Review / Admin Merge**: PRs require review approval or an administrator merge override.

### 🛑 User Confirmation Gates (MANDATORY)

To prevent unwanted changes, maintain strict quality control, and ensure implementation matches user expectations:
1. **Gate 1 — Before Opening a Pull Request**:
   - The agent **MUST explicitly ask the user for confirmation** before calling `create_pull_request`.
   - **Rationale**: The user may request additional modifications, want to review the diff/files first, or adjust scope before a PR is opened.
2. **Gate 2 — Before Merging a Pull Request**:
   - Even when CI checks succeed with `conclusion: "success"`, the agent **MUST explicitly ask the user for confirmation** before calling `merge_pull_request`.
   - **Rationale**: The user must review the build/preview behavior and give explicit approval before integrating changes into `dev` or releasing to `main`.

### 📋 Issue Pre-requisite & Closure Policy (MANDATORY)

Before committing changes or starting work:
* **Verify Existing Issues**: Check if an open GitHub Issue exists for the work using GitHub MCP `search_issues`.
* **Create Issue First**: If an issue does NOT exist, you **MUST create one first** using GitHub MCP `issue_write`:
  ```json
  {
    "ServerName": "github",
    "ToolName": "issue_write",
    "Arguments": {
      "method": "create",
      "owner": "thehavays",
      "repo": "filegate",
      "title": "<summary>",
      "body": "<description>",
      "assignees": ["thehavays"]
    }
  }
  ```
* **Link in Commits & PRs (`dev` Integration)**: Reference the issue using non-closing keywords like `ref #35` or `relates to #35` in commit messages and PR descriptions targeting `dev`.
* **Issue Closure Policy (CRITICAL)**: **DO NOT CLOSE ANY ISSUE UNTIL MERGED TO `main`!**
  - Feature and bugfix PRs merge into `dev`, which is our staging/integration branch. The issue represents work that is NOT yet live in production.
  - Therefore, issues must **NEVER be closed when merged into `dev`**, neither automatically nor manually via `issue_write`.
  - Closing keywords (`closes #...`, `resolves #...`, `fixes #...`) must ONLY be placed in the **Release PR description from `dev` to `main`**.
  - Merging `dev` into `main` is the only event that resolves and closes GitHub issues.

---

## 🏷️ Branch Naming Conventions

`<type>/<description-in-kebab-case>`

* **Allowed types**:
  * `feat/` — New feature or protocol driver
  * `fix/` — Bug fix or error handling correction
  * `chore/` — Dependency update, packaging, or cleanup
  * `docs/` — Documentation updates
  * `refactor/` — Code refactoring without behavior change
  * `perf/` — Performance optimization

---

## 📝 Commit Standards (Conventional Commits)

`<type>(<scope>): <imperative summary>` or `<type>: <imperative summary>`

* **Examples**:
  * `feat(sftp): add key-based authentication fallback`
  * `fix(config): resolve master password decryption on headless hosts`
  * `chore(deps): update paramiko to 3.4.0`
* **Disallowed**: Vague messages like `"fix"`, `"wip"`, `"update"`, `"changes"`.

---

## 🤖 GitHub MCP Tool Actions

Agents interact with GitHub through MCP tool calls (`call_mcp_tool` with `ServerName: "github"`):

### 1. Issues Management
* **Search Existing Issues**:
  ```json
  {
    "ServerName": "github",
    "ToolName": "search_issues",
    "Arguments": {
      "query": "repo:thehavays/filegate is:open <keywords>"
    }
  }
  ```
* **Create an Issue**:
  ```json
  {
    "ServerName": "github",
    "ToolName": "issue_write",
    "Arguments": {
      "method": "create",
      "owner": "thehavays",
      "repo": "filegate",
      "title": "<summary>",
      "body": "<description>",
      "assignees": ["thehavays"]
    }
  }
  ```

### 2. Pull Request Management
* **Create Pull Request to `dev`**:
  ```json
  {
    "ServerName": "github",
    "ToolName": "create_pull_request",
    "Arguments": {
      "owner": "thehavays",
      "repo": "filegate",
      "title": "<type>: <title>",
      "body": "<description referencing issue with ref #<issue_number> (DO NOT use closes #... on dev PRs)>",
      "head": "feat/<branch-name>",
      "base": "dev"
    }
  }
  ```
* **Create Release PR to `main`**:
  ```json
  {
    "ServerName": "github",
    "ToolName": "create_pull_request",
    "Arguments": {
      "owner": "thehavays",
      "repo": "filegate",
      "title": "release: merge dev to main",
      "body": "<release notes, changelog, and list of closed issues with closes #<issue_number>>",
      "head": "dev",
      "base": "main"
    }
  }
  ```
* **Merge Pull Request**:
  ```json
  {
    "ServerName": "github",
    "ToolName": "merge_pull_request",
    "Arguments": {
      "owner": "thehavays",
      "repo": "filegate",
      "pullNumber": 1,
      "merge_method": "merge"
    }
  }
  ```

---

## 🚀 Development & PR Step-by-Step Flow

### 1. Starting a Feature or Fix
1. Switch to `dev` and pull latest changes:
   ```bash
   git checkout dev
   git pull origin dev
   ```
2. Verify or create the tracking issue via GitHub MCP (`search_issues` or `issue_write`).
3. Create your task branch:
   ```bash
   git checkout -b feat/your-feature-name dev
   ```

### 2. Developing & Verifying
1. Make focused changes adhering to PEP 8.
2. Run project verification gates (`python -m unittest discover -v -s tests`).
3. Check status and staged diff (`git status`, `git diff`).

### 3. Rebasing & Opening a Pull Request
1. Rebase onto latest `dev`:
   ```bash
   git fetch origin
   git rebase origin/dev
   git push origin feat/your-feature-name
   ```
2. **Ask for User Confirmation (Mandatory)**: Present staged changes to the user and obtain explicit permission before opening the PR.
3. Create Pull Request targeting `dev` via `create_pull_request`.

### 4. Merging & Release to Production (`main`)
1. Wait for CI checks to pass.
2. **Ask for User Confirmation (Mandatory)**: Present check results to user and obtain permission before merge.
3. Merge PR into `dev` via `merge_pull_request`.
4. When releasing:
   - Ask for user approval before opening release PR from `dev` to `main`.
   - Open Release PR via `create_pull_request` (listing `closes #...`).
   - Ask for user approval before merging.
   - Merge into `main` via `merge_pull_request`.
   - Tag release with semantic version (`git tag -a vX.Y.Z -m "Release vX.Y.Z"`) to trigger Snapcraft release.
