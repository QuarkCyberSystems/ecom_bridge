# Ecom Bridge

Custom ecommerce bridge for Shopify & Amazon integrations with ERPNext. Syncs orders, inventory, fulfillments, and products between your online stores and ERPNext.

## Features

- **Order Sync**: Shopify/Amazon orders automatically create Sales Orders, Sales Invoices, and Delivery Notes in ERPNext
- **Fulfillment Sync**: Submitting a Delivery Note in ERPNext marks the Shopify order as Fulfilled
- **Inventory Sync**: Stock levels from ERPNext are pushed to Shopify on a configurable schedule (out-of-stock items become unavailable)
- **Product Sync**: Push new ERPNext items to Shopify, or map existing Shopify products to ERPNext items
- **Customer Sync**: Shopify customers are automatically created in ERPNext
- **ZATCA Compliance**: Optional VAT validation for Saudi Arabia

## Installation

```bash
cd $PATH_TO_YOUR_BENCH
bench get-app https://github.com/QuarkCyberSystems/ecom_bridge.git --branch main
bench --site your-site.com install-app ecom_bridge
```

### Dependencies

- ERPNext (v14+)
- Python packages: `ShopifyAPI`, `boto3` (installed automatically)

## Quick Start

### Shopify Integration

Setting up the Shopify integration involves two parts: creating a custom app in Shopify and configuring ERPNext.

#### 1. Create a Shopify Custom App

1. Go to **Shopify Admin** > **Settings** > **Apps and sales channels** > **Develop apps**
2. Click **Create an app**, name it (e.g., `ERPNext Bridge`)
3. Under **Configuration** > **Admin API access scopes**, add:

```
read_customers,write_customers,read_fulfillments,write_fulfillments,read_merchant_managed_fulfillment_orders,write_merchant_managed_fulfillment_orders,read_inventory,write_inventory,read_locations,read_orders,write_orders,read_products,write_products,read_shipping
```

4. Click **Save**, then go to **API credentials** > **Install app**
5. Copy the **Access Token** (`shpat_...`), **API key**, and **API secret**

#### 2. Configure ERPNext

1. Go to **Shopify Setting** in ERPNext
2. Check **Enable Shopify**
3. Enter your Shop URL, Access Token, and API Secret
4. Configure company, warehouse, cost center, tax mappings, and naming series
5. Click **Save** (webhooks are registered automatically)

Then go to **Ecom Bridge Settings**:
1. Check **Enabled** and **Enable Shopify Overrides**
2. Enable **Sync Fulfillment to Shopify** (to push fulfillments from ERPNext)
3. Enable **Sync Inventory to Shopify** (to push stock levels)
4. Click **Save**

> For the full step-by-step guide with screenshots, see [docs/shopify-setup-guide.md](docs/shopify-setup-guide.md)

### How Sync Works

```
Shopify Order Placed
  --> Sales Order created in ERPNext
  --> Sales Invoice created (if paid)
  --> Delivery Note created (if fulfilled in Shopify)

Delivery Note submitted in ERPNext
  --> Shopify order marked as Fulfilled

Stock Entry in ERPNext
  --> Stock levels pushed to Shopify (on schedule)
  --> Out-of-stock items become unavailable in Shopify
```

## Configuration Reference

### Shopify Setting

| Field | Description |
|-------|-------------|
| Shop URL | `your-store.myshopify.com` (no https://) |
| Password / Access Token | Shopify Admin API access token |
| Shared Secret | Shopify API secret for webhook verification |
| Company | ERPNext company for Shopify transactions |
| Warehouse | Default warehouse for stock operations |
| Customer Group | Group for Shopify customers |
| Tax Mapping | Map Shopify taxes to ERPNext accounts |
| Inventory Sync Frequency | Push stock every 5/10/15/30/60 minutes |

### Ecom Bridge Settings

| Field | Description |
|-------|-------------|
| Sync Fulfillment to Shopify | Auto-fulfill Shopify orders when DN is submitted |
| Sync Inventory to Shopify | Push ERPNext stock levels to Shopify |
| Enable ZATCA Validation | Validate VAT on Shopify orders (Saudi Arabia) |

## API Endpoints

| Method | Description |
|--------|-------------|
| `ecom_bridge.api.dashboard.get_sync_dashboard` | Sync status overview |
| `ecom_bridge.api.dashboard.force_inventory_sync` | Manually trigger inventory sync |
| `ecom_bridge.api.dashboard.force_fulfillment_sync` | Manually trigger fulfillment for a DN |
| `ecom_bridge.api.dashboard.force_sync` | Manually trigger order sync |

## Troubleshooting

| Issue | Check |
|-------|-------|
| Orders not syncing | Webhooks registered? Check Ecommerce Integration Log |
| Fulfillment 403 error | Add `read/write_merchant_managed_fulfillment_orders` scopes in Shopify app |
| Inventory "tracking not enabled" | Enable "Track quantity" on Shopify products |
| Inventory not updating | Warehouse mapping configured? Ecommerce Item records exist? |

See [docs/shopify-setup-guide.md](docs/shopify-setup-guide.md) for the complete troubleshooting guide.

## Contributing

This app uses `pre-commit` for code formatting and linting:

```bash
cd apps/ecom_bridge
pre-commit install
```

Tools: ruff, eslint, prettier, pyupgrade

## License

MIT
