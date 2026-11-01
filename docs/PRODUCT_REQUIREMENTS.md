# Product requirements and delivery scope

## Product

Vantage IQ is an executive business intelligence workspace for small and medium-sized, project-driven organizations. Its intended value is a consolidated, decision-ready view of financial, sales, project, and customer signals.

## User journeys implemented

1. Open a clearly marked synthetic workspace or authenticate to an organization.
2. Select an authorized organization and review its period-filtered headline performance.
3. Drill into financial costs, customer revenue, project status, and alerts.
4. Manage organization-scoped customer, project, department, budget, revenue, and expense records, subject to role.
5. Upload an authorized organization's CSV/XLSX revenue file, review row-level validation, and explicitly commit an all-valid file.
6. Export a period-filtered executive KPI CSV or PDF.

## MVP requirements

- The demo works without third-party paid services.
- Synthetic data is deterministic and coherent across views.
- Financial amounts use decimal database columns.
- Revenue and pipeline remain separate concepts.
- Empty and zero-baseline calculations are explicit.
- Import validation is a separate step from transactional commit.
- The UI provides responsive navigation, loading/error states, keyboard focus styling, reduced-motion support, and a light/dark option.

## Remaining requirements

Live email delivery/deliverability, invitations, production MySQL/TLS validation, monitoring, import history/reversal, advanced forecasting, KPI target editing, billing entitlements, and verified backup/restore and security-review processes.

The synthetic demo remains unauthenticated and read-only. Tenant permissions are enforced server-side for authenticated organizations; frontend role-aware controls are not the authorization boundary.
