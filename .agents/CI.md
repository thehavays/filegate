# Continuous Integration (CI) Guidelines for FileGate

---

## ⚙️ Environment & CI Context

* **GITHUB_USERNAME**: `thehavays`
* **REPOSITORY**: `filegate`
* **STACK**: Python (3.8+ / 3.10), `setuptools`, `paramiko`, `cryptography`, `smbprotocol`, `keyring`, `rich`
* **CI_STRATEGY**: Mandatory local verification gates and automated GitHub Actions PR checks

---

## 🎯 CI Philosophy & Purpose

Continuous Integration guarantees that all code integrated into `dev` and `main`:
1. **Passes Syntax & Lint Checks**: Code conforms to Python 3 syntax and PEP 8 guidelines.
2. **Passes Automated Tests**: Unittest discovery suite (`python -m unittest discover -v -s tests`) runs cleanly with mock verification.
3. **Validates Packaging**: `setup.py` builds without packaging errors or missing dependencies.
4. **Ensures Zero Leaks**: Strict zero-secret policy via `.env.example`, `.gitignore`, and secure credential keyrings.

---

## 🚦 Mandatory Local Verification Gates

Before opening a Pull Request or pushing changes to remote, run these gates in order:

### 1. Test Suite Verification
```bash
python -m unittest discover -v -s tests
```
* **Acceptance Criteria**: Exit code 0, all unit test cases pass.

### 2. Package Build Check
```bash
python setup.py check
```
* **Acceptance Criteria**: Exit code 0, package metadata and syntax valid.

### 3. Diff Hygiene & Cleanliness
```bash
git status
git diff
```
* **Acceptance Criteria**:
  - No leftover debug print statements (`print(...)` dumps).
  - No untracked cache files (`__pycache__`, `.pytest_cache`), secrets (`.env`), or snap build artifacts (`parts/`, `stage/`, `prime/`).
  - Working tree is clean and scoped.

---

## 🤖 Automated CI Strategy: GitHub Actions

Configured workflow: [`.github/workflows/ci.yml`](../.github/workflows/ci.yml)
- **Triggers**: On `push` and `pull_request` targeting `dev` and `main`, plus `workflow_call`.
- **Environment**: Ubuntu Latest with Python `3.10`.
- **System Dependencies**: Installs `libsecret-1-dev` and `pkg-config` for system keyring integration.
- **Steps**: Checkout code, Setup Python, install dependencies (`requirements.txt`, `pip install .`), and run `python -m unittest discover -v -s tests`.
