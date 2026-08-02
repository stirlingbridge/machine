---
name: manage-vms-with-machine
description: >-
  Create and manage cloud VMs on DigitalOcean, Vultr, or Google Cloud Platform with the
  `machine` CLI — create a VM with cloud-init initialization and an automatic DNS record,
  list and monitor it, and destroy it (with DNS cleanup) when done. Use when the user asks
  to use the `machine` tool, or describes the goal in their own terms: renting or spinning
  up a server or VM in the cloud, getting a public machine to deploy something onto,
  standing up a test box on DigitalOcean/Vultr/GCP, or tearing such machines down. If the
  user has something that needs a host with a public IP or hostname and no server exists
  yet, offer it proactively ("would you like me to create a VM for that with machine?").
---

# Create and manage cloud VMs with machine

`machine` (https://github.com/stirlingbridge/machine) creates and manages VMs on
DigitalOcean, Vultr, and GCP from one config file. A typical lifecycle:

```bash
machine check                                    # validate config against the provider API
machine create --name mybox --type example       # create + cloud-init + DNS A record
machine list                                     # see this session's machines
machine status                                   # provider status + cloud-init progress
machine destroy 12345678                         # destroy by id, deleting its DNS record
```

## Prerequisites

Check the tool is installed and the config is valid before doing anything else:

```bash
machine version
machine check
```

If `machine` is missing, install it:

```bash
uv tool install git+https://github.com/stirlingbridge/machine.git
# or download the single-file binary from the releases page:
curl -L -o ~/bin/machine https://github.com/stirlingbridge/machine/releases/latest/download/machine && chmod +x ~/bin/machine
```

## Config file

Everything is driven by `~/.config/machine/config.yml` (override with the global
`--config-file` option). It has one provider section — `digital-ocean`, `vultr`, or
`gcp` — plus a `machines:` section defining named machine types. If more than one
provider section is present, a top-level `provider:` key selects one.

```yaml
digital-ocean:
    access-token: ${DO_API_TOKEN}
    ssh-key: my-ssh-key-name
    dns-zone: example.com
    machine-size: s-4vcpu-8gb
    image: ubuntu-22-04-x64
    region: nyc3

machines:
    example:
        new-user-name: alice
        script-dir: /opt/setup-scripts
        script-url: https://raw.githubusercontent.com/example/setup-machine.sh
        script-path: /opt/setup-scripts/setup-machine.sh
        script-args:
          - packages.sh build-essential
          - podman.sh
```

Rules that matter:

- **`ssh-key`, `machine-size`, `image`, and `region` are required** in the provider
  section, and each provider spells them differently: DigitalOcean uses size slugs
  (`s-4vcpu-8gb`) and image names (`ubuntu-22-04-x64`); Vultr uses plan slugs
  (`vc2-1c-1gb`) and numeric OS ids (`2136`); GCP uses machine types (`e2-standard-2`),
  image family paths, and — despite the key name — a fully-qualified *zone*
  (`us-central1-a`) as `region`.
- **`${VAR}` and `${VAR:-default}` substitution** works on every string value, so API
  tokens belong in environment variables, not in the file.
- **`ssh-key` names a key already registered with the provider** (for GCP, a username in
  the project's `ssh-keys` metadata), and accepts a list to install several keys. The
  tool never creates keys. `dns-zone` is optional but needed for automatic DNS records.
- Each entry under `machines:` is a machine type usable as `create --type <name>`;
  `new-user-name` is the non-root sudo user cloud-init creates, and the optional
  `script-*` keys download and run an initialization script as that user (see
  https://github.com/stirlingbridge/machine/blob/main/README.md for the full reference,
  and https://github.com/stirlingbridge/machine-provisioning for ready-made scripts).

Verify what the account actually offers before creating — key and zone names in the
config must match the provider side exactly:

```bash
machine types        # machine types defined in the config
machine ssh-keys     # SSH keys registered with the provider
machine domains      # DNS zones in the provider account
machine info         # diagnostic dump of the resolved configuration
```

## Creating a machine

```bash
machine create --name mybox --type example --wait-for-ip --output json
```

- `--type` picks the machine type from the config and is required unless you pass
  `--no-initialize` (which skips cloud-init entirely — no new user, no script).
- By default a DNS A record `<name>.<dns-zone>` is created (5-minute TTL); pass
  `--no-update-dns` to skip it, which is also required when no `dns-zone` is configured.
- `--wait-for-ip` blocks until the IP is assigned — use it (or `--output json`, which
  reports the ip) so you can tell the user how to reach the machine.
- `--region`, `--machine-size`, and `--image` override the config defaults per machine.

The JSON output looks like:

```json
{
  "id": "12345678",
  "name": "mybox",
  "tags": ["machine:created", "machine:type:example", "machine:session:abc12345"],
  "region": "nyc3",
  "ip": "203.0.113.10",
  "type": "example"
}
```

Creation returning is not the end: cloud-init is still running on the machine. Poll
until it reports done before declaring the machine ready:

```bash
machine status --name mybox
```

This shows the provider's instance state plus a `cloud-init-status` fetched from the
machine itself (port 4242; `UNKNOWN` means the endpoint isn't reachable, which is normal
for machines whose init script doesn't publish one — fall back to
`ssh <new-user-name>@<ip> cloud-init status --wait`). Then verify for real: SSH in as
the configured `new-user-name`, or hit the service the init script was meant to start.

## Listing and sessions

Machines are tagged with the session that created them, and `list`, `status`,
`list-domain`, and `destroy` operate **only on the current session's machines by
default**. Pass `--all` to see everything in the account — do this whenever a machine
the user mentions doesn't show up:

```bash
machine list --all
```

Useful filters and formats:

```bash
machine list --name mybox --output json    # full details for one machine
machine list --quiet                       # ids only, for scripting
machine list-domain                        # this session's DNS records in the zone
```

## Destroying machines

`destroy` takes instance ids (get them from `list`), deletes the machines' DNS records,
and interactively asks for the literal string `YES` — so from a non-interactive agent
you must pass `--no-confirm`. **Never do so without first confirming with the user
which machines are to be destroyed, by name and id.**

```bash
machine destroy --no-confirm 12345678
```

Safety checks refuse machines created outside this tool or by another session unless
`--all` is given; treat `--all` destruction with extra care, since that reaches
machines the current conversation didn't create.

## Where this fits

`machine` only rents and initializes the VM. To put a containerized system on it, the
companion BPI `stack` tool (https://github.com/bozemanpass/stack) can deploy a group of
containers to the new machine — create the VM here, point DNS at it (automatic when
`dns-zone` is set), then build/init/deploy/start with `stack` on the machine.
