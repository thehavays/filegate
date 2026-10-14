# Continuous Deployment (CD) Guidelines for FileGate

---

## ⚙️ Environment & CD Context

* **HOSTING_PLATFORM**: Canonical Snap Store & PyPI / GitHub Releases
* **GITHUB_USERNAME**: `thehavays`
* **REPOSITORY**: `filegate`
* **DEPLOYMENT_TYPE**: Python CLI Package & Snap Distribution
* **RUNTIME**: Linux (x86_64 / arm64), macOS, Windows

---

## 🌐 Delivery & Distribution Architecture

`filegate` is distributed as a Python CLI utility and packaged for the Canonical Snap Store:

### Distribution Channels:
1. **Canonical Snap Store**:
   - Package name: `filegate`
   - Installation:
     ```bash
     sudo snap install filegate
     sudo snap connect filegate:password-manager-service
     ```
   - Automated CD Workflow: [`.github/workflows/snapcraft-release.yml`](../.github/workflows/snapcraft-release.yml)
   - Trigger: Pushes of semantic version tags (`v*`).

2. **Pipx / Pip Installation**:
   ```bash
   pipx install filegate
   # or
   pip install filegate
   ```

3. **Source Build & Local Installation**:
   ```bash
   pip install .
   ```

---

## 🌿 Environment & Branch Mappings

| Branch / Tag | Stage | Purpose |
| :--- | :--- | :--- |
| **`main`** | **Production Release** | Stable release branch. |
| **`dev`** | **Integration / Staging** | Active development branch for validated feature PRs. |
| **`feat/*`** | **Feature Branches** | Feature development branches targeting `dev`. |
| **`v*` Tags** | **Snap Store Publish** | Automatically triggers the Snapcraft build & publish workflow to the `stable` channel. |

---

## 🚀 Production Release Workflow

1. **Verify Integration**: Ensure all features, tests, and checks pass on `dev`.
2. **Open Release PR**: Ask user confirmation, then create Release PR from `dev` to `main` via GitHub MCP `create_pull_request`.
3. **Merge Release PR**: Ask user confirmation, then merge via GitHub MCP `merge_pull_request` (auto-closes resolved issues).
4. **Publish Release & Tag**:
   - Tag the release commit on `main`:
     ```bash
     git tag -a v1.1.11 -m "Release v1.1.11"
     git push origin v1.1.11
     ```
   - GitHub Actions automatically executes `snapcraft-release.yml` to build the snap and publish to the Snap Store.
