# End-to-End Tests

These tests verify that `machine` can create and manage real VMs on DigitalOcean, including DNS record lifecycle. They are **not** run as part of the normal test suite due to cost and runtime.

## Prerequisites

You need a DigitalOcean account with:

- An API token
- An SSH key registered in the account
- A DNS zone managed by DigitalOcean (e.g. `test.example.com`)

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `E2E_DO_TOKEN` | Yes | DigitalOcean API token |
| `E2E_SSH_KEY` | Yes | Name of an SSH key in your DO account |
| `E2E_DNS_ZONE` | Yes | DO-managed DNS zone for test records |
| `E2E_REGION` | No | Region slug (default: `nyc1`) |
| `E2E_IMAGE` | No | Image slug (default: `ubuntu-24-04-x64`) |
| `E2E_SIZE` | No | Droplet size (default: `s-1vcpu-512mb-10gb`) |
| `E2E_PROJECT` | No | DO project to assign droplets to |

## Running

```bash
# Set credentials
export E2E_DO_TOKEN="dop_v1_..."
export E2E_SSH_KEY="my-ssh-key"
export E2E_DNS_ZONE="test.example.com"

# Run e2e tests
make test-e2e

# Or directly
uv run pytest tests/test_e2e.py -v -m e2e
```

The normal `make test` (and CI) will **skip** these tests automatically.

## What's Tested

- **Droplet lifecycle** — create, list, destroy, verify removal
- **DNS lifecycle** — create with `--update-dns`, verify A record, destroy with `--delete-dns`, verify record removal
- **Cloud-init initialization** — create with `--type`, verify type tag
- **Custom tags** — create with `--tag`, verify tag filtering

## Cleanup

Each test cleans up after itself. A safety fixture also destroys any leftover droplets if a test fails mid-run. All test droplets use unique names prefixed with `e2etest-` so they are easy to identify.

## Cost

Tests use the smallest available droplet size (`s-1vcpu-512mb-10gb`) and destroy VMs immediately after verification, so cost is minimal.
