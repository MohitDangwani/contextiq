---
title: Revenue Dashboard Guide
asset_id: revenue_dashboard
doc_type: readme
source_url: https://wiki.brightcart.example/dashboards/revenue
---
# Revenue Dashboard

The Revenue Dashboard is the BI team's Looker dashboard for tracking
Brightcart's top-line revenue performance.

## What it shows

- Net revenue by month
- Order volume by month
- Refund rate (refunds / gross revenue)

## Where the numbers come from

Every tile reads from `monthly_revenue`, which is itself built from
`revenue_model` (see the Revenue Recognition Policy for how net revenue
is calculated). Because the dashboard has no data of its own, its
trustworthiness depends entirely on the freshness and quality of
`monthly_revenue` and everything upstream of it — check those datasets'
quality checks if a number on this dashboard looks wrong.

## Refresh schedule

Refreshed daily at 18:00 UTC, after the nightly `monthly_revenue` batch
completes.
