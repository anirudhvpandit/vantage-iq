# Data import guide

The MVP supports recognized-revenue CSV and XLSX files. Use either in-product template download or `GET /api/v1/imports/revenue/template.csv` / `GET /api/v1/imports/revenue/template.xlsx`.

## Workflow

1. Choose a `.csv` or `.xlsx` file no larger than the configured upload limit (default 5 MiB), with at most 10,000 data rows and 50 columns.
2. Select **Preview & validate**. The API checks file type, UTF-8 CSV parsing or XLSX structure, required headers, row values, customer/department names in the active organization, and duplicate IDs.
3. Review the sample rows and validation messages. No data is committed during preview.
4. Fix every invalid row and preview again. All rows must validate before the commit button is enabled.
5. An analyst, admin, or owner can select **Confirm and import records**. The API revalidates the uploaded bytes and commits the rows transactionally. The synthetic demo is read-only and cannot commit imports.

## Required columns

| Column | Rule |
|---|---|
| `external_id` | Non-empty stable ID, unique within the organization |
| `date` | `YYYY-MM-DD`; demo dates must be within November 1, 2024–October 31, 2026 |
| `customer` | Exact name of an existing customer in the active organization |
| `department` | Exact name of an existing department in the active organization |
| `amount` | Decimal; negative values represent refunds |
| `currency` | Three-letter alphabetic code matching the workspace currency (no FX conversion is applied) |
| `description` | Required short text |

Imports do not create or silently overwrite customers, departments, or transactions. A repeated ID blocks the import. XLSX files are loaded as values (`data_only`); macros are not executed. The API does not retain uploaded source files or create a persistent import-job history in this MVP.
