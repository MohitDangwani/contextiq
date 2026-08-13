---
title: Marketing Campaigns Overview
asset_id: marketing_campaigns
doc_type: readme
source_url: https://wiki.brightcart.example/data/marketing-campaigns
---
# Marketing Campaigns

One row per marketing campaign Brightcart has run. Used primarily for
acquisition attribution: `customers.acquisition_campaign_id` points back
to the campaign that brought that customer in, when known.

## Who owns it

Marketing Ops maintains this table manually — campaigns are entered when
planned, not auto-ingested from an ad platform. This is a deliberate
simplification for this environment and the reason the freshness check
on this dataset is only a `warn`, not a hard failure: manual entry is
expected to lag.

## Not connected to revenue lineage

Unlike `customers` → `orders` → `order_items`, this table does not feed
into `revenue_model`. It answers "who brought this customer in," not
"how much revenue did we make."
