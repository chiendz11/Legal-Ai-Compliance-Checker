# Mock fixtures

Generated, Git-ignored `<ca_id>.json` files (`Output_ReportRecord` shape) from the local DB:

```bash
python -m scripts.ui_fixtures            # 5 diverse DEV cases
python -m scripts.ui_fixtures --case CA360_001 --case CA360_051
```

They are QA `EXPECTED` C13 references used only to lay out the UI. They are not output of a dev
run and must never be shown as a reviewed or published report.
