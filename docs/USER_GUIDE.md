# User guide

## Sign in and select a workspace

In SaaS mode, sign in with your verified account. Registration is available only when the deployment enables it; new accounts must verify their email before signing in. Use the sign-in page to request a verification email or password reset. Resetting your password revokes existing sessions. Your organization membership and role determine available actions. Use the organization selector to switch only between organizations you belong to. Owners and admins can review organization-scoped audit history through the API. Sessions use secure cookies and mutations are CSRF-protected.

The demo opens without an account and uses fictional Northstar data. It is read-only and clearly labeled.

## Executive overview

The overview shows recognized revenue, recorded operating costs, operating profit, and operating margin. Supporting metrics display budget achievement, on-time delivery, and customer activity. Choose start and end dates to refresh period totals and charts. The prior period is an equally long immediately preceding date range.

Use the KPI dictionary for calculation definitions. Report pages provide tenant-scoped CSV and PDF downloads.

## Workspace pages

- **Financial performance:** headline financial results, cost composition, and accounting limitations.
- **Revenue & sales:** recognized revenue by customer plus separate demo-only synthetic pipeline examples.
- **Projects & delivery:** project progress and budget variances.
- **Customers:** customer directory with a name filter and historical recognized revenue.
- **Departments** and **Budgets & goals:** reporting dimensions and monthly targets.
- **Business records:** paginated create/read/update/delete management for customers, departments, projects, budgets, revenue, and expenses. Editing follows your organization role; record deletion is restricted to owners/admins.
- **Data imports:** preview and validate revenue files; authorized analysts, admins, and owners may commit all-valid files. Demo data remains read-only.
- **Team & access:** owners/admins can add existing accounts, update member roles, and remove members.
- **Alerts:** organization-scoped exceptions and suggested actions.
- **Settings:** current organization, role, and implemented/remaining capabilities.

Only the synthetic demo is a fixed snapshot. Authenticated organization data reflects the records stored in that organization; calculation notes explain what the metrics do and do not represent.
