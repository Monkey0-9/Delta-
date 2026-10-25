# GitHub Branch Protection & Repository Rulesets Specification

**Repository**: `Monkey0-9/Delta-`  
**Target Branch**: `main`  
**Governance Tier**: Institutional Quantitative Trading Standard

---

## 1. Objective

To prevent unauthorized, unverified, or untested code from landing on `main`, the following branch protection policy and GitHub Ruleset must be enforced on `Monkey0-9/Delta-`.

---

## 2. Ruleset Configuration (main)

```yaml
ruleset:
  name: "Institutional Main Protection"
  target: "branch"
  enforcement: "active"
  conditions:
    ref_name:
      include:
        - "refs/heads/main"
      exclude: []

  rules:
    # 1. Prevent direct pushes; require pull requests
    - type: "pull_request"
      parameters:
        required_approving_review_count: 1
        dismiss_stale_reviews_on_push: true
        require_code_owner_review: true
        require_last_push_approval: true
        required_review_thread_resolution: true

    # 2. Required Status Checks (All must pass before merge)
    - type: "required_status_checks"
      parameters:
        strict_required_status_checks_policy: true
        required_status_checks:
          # delta-ci (.github/workflows/ci.yml)
          - context: "math-invariants"
          - context: "test"
          - context: "rust"
          - context: "wheels"
          # delta-security-gates (.github/workflows/security.yml)
          - context: "semgrep"
          - context: "bandit"
          - context: "secret-scan"
          - context: "cargo-audit"
          - context: "pip-audit"

    # 3. Block Force Pushes & Deletions
    - type: "non_fast_forward"
    - type: "deletion"

    # 4. Require Signed Commits (Optional but recommended)
    - type: "required_signatures"
```

---

## 3. Code Owner Boundaries (`.github/CODEOWNERS`)

The following directory paths require review by institutional code owners:
- `/core/oms/`: Execution and Order Management leads.
- `/risk/`: Risk Officer and Governance leads.
- `/governance/`: Compliance and Audit leads.
- `/docs/CAPABILITY_REGISTER.yaml`: Chief Technology Officer / Release Architect.
- `/SYSTEM_STATUS.yaml`: Chief Technology Officer / Release Architect.
- `/.github/workflows/`: DevOps / Platform Security lead.
