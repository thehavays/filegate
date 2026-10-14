# FileGate — Agent & Developer Guide

This document is the primary onboarding and operational guide for AI agents and developers working in the `filegate` repository.

---

## 📖 Project Overview

FileGate (`filegate`) is a CLI utility for connecting, browsing, pulling, and pushing files across remote file servers (SFTP, FTP, SMB) with secure credential management and interactive shell capabilities.

### 🛠️ Core Technology Stack
- **Language / Runtime**: Python 3.8+ (Package: `filegate`)
- **Remote Protocols**:
  - SFTP: `paramiko`
  - SMB: `smbprotocol`
  - Cryptography: `cryptography` (Fernet symmetric encryption / PBKDF2HMAC)
- **Credential Storage**: `keyring` (system keyring via `libsecret` on Linux, Keychain on macOS, Credential Manager on Windows)
- **Terminal UI / Output**: `rich`
- **Packaging & Distribution**: `setuptools`, Canonical Snapcraft (`snap/snapcraft.yaml`), pip / pipx

---

## 📁 Repository Structure

```
filegate/
├── .agents/                 # Agent rules, workflows, and standards
│   ├── GIT_WORKFLOW.md      # Detailed Git branching & GitHub MCP rules
│   ├── CI.md                # Continuous Integration standards & quality gates
│   ├── CD.md                # Continuous Deployment & Snapcraft architecture
│   └── skills/              # Agent skills (filegate-assistant)
│       └── filegate/
│           └── SKILL.md
├── .github/
│   ├── workflows/
│   │   ├── ci.yml           # Automated Python CI test workflow
│   │   └── snapcraft-release.yml # Snapcraft build & publish workflow
│   ├── ISSUE_TEMPLATE/      # GitHub issue forms (bug_report.yml, feature_request.yml)
│   └── pull_request_template.md
├── completions/             # Shell completion scripts (bash, zsh)
├── filegate/                # Core application package
│   ├── __init__.py
│   ├── completer.py         # Tab auto-completion logic
│   ├── config.py            # Secure configuration and encryption management
│   ├── main.py              # CLI entry point and subcommands
│   └── protocols/           # Protocol drivers (SFTP, FTP, SMB)
├── snap/                    # Canonical Snapcraft packaging configuration and metadata
├── tests/                   # Automated unit test suite
├── .editorconfig            # Standard editor formatting rules (PEP 8 4-space indentation)
├── .env.example             # Documented environment configuration (FILEGATE_MASTER_PASSWORD)
├── .gitignore               # Ignored caches, environments, secrets, and build artifacts
├── LICENSE                  # MIT License
├── README.md                # User & contributor documentation
├── requirements.txt         # Production runtime dependencies
└── setup.py                 # Setuptools package configuration
```

---

## ⚡ Canonical Commands

Always use the following commands for development and verification:

| Action | Command | Purpose |
| :--- | :--- | :--- |
| **Run Unit Tests** | `python -m unittest discover -v -s tests` | Executes unit test suite |
| **Check Package** | `python setup.py check` | Verifies package metadata and syntax |
| **Install in Editable Mode** | `pip install -e .` | Installs local copy for CLI testing |
| **Run CLI Directly** | `python -m filegate.main --help` | Invokes CLI without global installation |
| **Check Dependencies** | `pip check` | Verifies installed package compatibility |

---

## 🌿 Git & Version Control Workflow

For complete version control guidelines, see [.agents/GIT_WORKFLOW.md](./.agents/GIT_WORKFLOW.md).

### Summary Rules:
1. **Protected Branches**: Direct pushes to `main` and `dev` are strictly forbidden.
2. **Branch Roles**:
   - `dev`: Primary integration branch. All feature and fix branches must originate from and target `dev`.
   - `main`: Production release branch. Updated only by merging `dev` via Release Pull Request.
3. **Branch Naming**: `<type>/<kebab-case-description>` (e.g. `feat/sftp-key-auth`, `fix/config-permissions`).
4. **Commit Format**: Conventional Commits (`feat: ...`, `fix: ...`, `chore: ...`).
5. **Pre-flight Verification**: Always run `python -m unittest discover -v -s tests` before opening PRs.
6. **User Confirmation Gates (MANDATORY)**:
   - **Before Opening PR**: ALWAYS ask user approval before calling `create_pull_request`.
   - **Before Merging PR**: ALWAYS ask user approval before calling `merge_pull_request`.
7. **Issue Closure Policy**: Issues are created first with `issue_write`, referenced in dev PRs (`ref #...`), and closed ONLY when merged to `main` via Release PR (`closes #...`).

---

## 🔄 CI/CD Guidelines
- **CI**: See [.agents/CI.md](./.agents/CI.md) for quality gates.
- **CD**: See [.agents/CD.md](./.agents/CD.md) for Snapcraft packaging and release flow.
