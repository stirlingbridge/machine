# machine
CLI utility to create and manage VMs

Initially supports only DigitalOcean using the [python-digitalocean](https://github.com/koalalorenzo/python-digitalocean) module.

## Prerequisites

This project uses [uv](https://docs.astral.sh/uv/) for dependency management and builds.

Install uv:
```
curl -LsSf https://astral.sh/uv/install.sh | sh
```

## Development Setup

```
uv sync
```

This creates a `.venv` virtual environment and installs all dependencies (including dev tools like flake8 and black).

Run the CLI during development:
```
uv run machine --help
```

Run the linter:
```
uv run flake8
```

## Build

Build a self-contained executable using [shiv](https://github.com/linkedin/shiv):
```
./sh/build-package.sh
```

This produces `build/machine`, a single-file Python zipapp.

## Install

Install directly from the GitHub repository using uv:
```
uv tool install git+https://github.com/stirlingbridge/machine.git
```

Alternatively, download the `machine` binary from the [releases page](https://github.com/stirlingbridge/machine/releases), make it executable, and place it on your PATH:
```
chmod +x machine
sudo mv machine /usr/local/bin/
```

## Usage

### Config File
Access token and other settings configured in the file `~/.machine/config.yml` :
```yaml
digital-ocean:
    access-token: dop_v1_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
    ssh-key: my-ssh-key-name
    dns-zone: example.com
    machine-size: s-4vcpu-8gb
    image: ubuntu-22-04-x64
    region: nyc3
    project: Infrastructure

machines:
    example:
        new-user-name: alice
        script-dir: /opt/setup-scripts
        script-url: https://raw.githubusercontent.com/example/setup-machine.sh
        script-path: /opt/setup-scripts/setup-machine.sh
        script-args: "-y"
```

#### Config Reference

**digital-ocean section:**

| Key | Required | Description |
|-----|----------|-------------|
| `access-token` | Yes | DigitalOcean API access token |
| `ssh-key` | Yes | Name of the SSH key in your DigitalOcean account to use for new machines |
| `dns-zone` | No | DNS zone for automatic DNS record creation/deletion |
| `machine-size` | Yes | Default machine size slug (e.g. `s-4vcpu-8gb`) |
| `image` | Yes | Default image name (e.g. `ubuntu-22-04-x64`) |
| `region` | Yes | Default region code (e.g. `nyc3`) |
| `project` | No | DigitalOcean project name to assign new machines to |

**machines section:**

Each entry under `machines:` defines a machine type that can be referenced with `create --type`:

| Key | Required | Description |
|-----|----------|-------------|
| `new-user-name` | Yes | Username for the non-root user created on the machine |
| `script-url` | No | URL to download an initialization script from |
| `script-dir` | No | Directory to store the initialization script |
| `script-path` | No | Full path for the initialization script |
| `script-args` | No | Arguments passed to the initialization script (supports variable expansion) |

If `script-url`, `script-dir`, and `script-path` are all provided, the script is downloaded and executed as the new user during cloud-init. The following variables are available for expansion in `script-args`:

- `$MACHINE_SCRIPT_URL` — URL of the initialization script
- `$MACHINE_SCRIPT_DIR` — directory path for the script
- `$MACHINE_FQDN` — fully qualified domain name of the machine (if DNS is configured)

#### Advanced Machine Setup

Examples of advanced machine setup scripts can be found in [the machine-provisioning repository](https://github.com/bozemanpass/machine-provisioning).

### Session Management

Each invocation of `machine` uses a session ID (auto-generated and stored in `~/.machine/session-id.yml`). Machines are tagged with their session ID on creation. By default, `list`, `status`, `list-domain`, and `destroy` only operate on machines from the current session. Use the `--all` flag to include machines from other sessions or machines not created by this tool.

The session ID can be overridden with the global `--session-id` option.

### Automatic Tagging

Machines created by this tool are automatically tagged with:

- `machine:created` — identifies the machine as created by this tool
- `machine:type:<type-name>` — the machine type from the config
- `machine:session:<session-id>` — the session that created the machine

### Global Options
```
$ machine --help
Usage: machine [OPTIONS] COMMAND [ARGS]...

Options:
  --debug               Enable debug output
  --quiet               Suppress all non-essential output
  --verbose             Enable verbose output
  --dry-run             Run but do not do anything
  --config-file <PATH>  Specify the config file (default
                        ~/.machine/config.yml)
  --session-id <ID>     Override the default session ID
  -h, --help            Show this message and exit.

Commands:
  create       Create a machine
  destroy      Destroy one or more machines
  domains      List dns domains
  list         List machines
  list-domain  List domain records
  projects     List projects
  ssh-keys     List ssh keys
  status       Machine status
  types        List configured machine types
  version      Display version
```

### Commands

#### create

Create a new machine on DigitalOcean. By default, the machine is initialized with cloud-init (using the specified `--type` from config) and a DNS A record is created.

```
$ machine create --help
Usage: machine create [OPTIONS]

  Create a machine

Options:
  -n, --name <MACHINE-NAME>         Name for new machine  [required]
  -t, --tag <TAG-TEXT>              Tag to be applied to new machine
  -m, --type <MACHINE-TYPE>        Machine type from config (required if --initialize)
  -r, --region <REGION-CODE>       Region (overrides config default)
  -s, --machine-size <MACHINE-SLUG>
                                    Machine size (overrides config default)
  -s, --image <IMAGE-NAME>         Image (overrides config default)
  --wait-for-ip / --no-wait-for-ip Wait for IP address assignment (default: off)
  --update-dns / --no-update-dns   Create DNS A record (default: on)
  --initialize / --no-initialize   Initialize with cloud-init (default: on)
  -h, --help                       Show this message and exit.
```

Supported regions: `NYC1`, `NYC3`, `AMS3`, `SFO2`, `SFO3`, `SGP1`, `LON1`, `FRA1`, `TOR1`, `BLR1`, `SYD1`

When `--update-dns` is enabled (the default), the command waits for the droplet's IP address and creates an A record in the configured `dns-zone` with a 5-minute TTL.

When `--initialize` is enabled (the default), a cloud-config user-data payload is generated that creates a non-root user with sudo access, installs the SSH key, and optionally downloads and runs an initialization script.

If a `project` is configured, the machine is automatically assigned to that DigitalOcean project.

#### destroy

Destroy one or more machines by droplet ID. By default, requires confirmation and deletes associated DNS records.

```
$ machine destroy --help
Usage: machine destroy [OPTIONS] [DROPLET-IDS]...

  Destroy one or more machines

Options:
  --confirm / --no-confirm       Require confirmation (default: on)
  --delete-dns / --no-delete-dns Delete associated DNS records (default: on)
  --all                          Include machines not created by this tool
                                 or by other sessions
  -h, --help                     Show this message and exit.
```

Confirmation requires typing exactly `YES` (not "y", "yes", or "Yes"). Use `--no-confirm` to skip.

Safety checks prevent destroying machines that were not created by this tool or that belong to a different session, unless `--all` is specified.

#### list

List machines with optional filtering.

```
$ machine list --help
Usage: machine list [OPTIONS]

  List machines

Options:
  --id <MACHINE-ID>       Filter by id
  -n, --name <MACHINE-NAME>  Filter by name
  -t, --tag <TAG-TEXT>    Filter by tag
  -m, --type <MACHINE-TYPE>  Filter by type
  -r, --region <REGION>   Filter by region
  -o, --output <FORMAT>   Output format (json)
  -q, --quiet             Only display machine IDs
  --unique                Return an error if more than one match
  --all                   Include all machines from all sessions
  -h, --help              Show this message and exit.
```

Output formats:
- Default: `name (id, region, type): ip_address`
- `--quiet`: droplet IDs only
- `--output json`: JSON array with id, name, tags, region, ip, type

#### status

Check the status of machines, including querying a custom status endpoint.

```
$ machine status --help
Usage: machine status [OPTIONS]

  Machine status

Options:
  --id <MACHINE-ID>          Filter by id
  -n, --name <MACHINE-NAME>  Filter by name
  -t, --tag <TAG-TEXT>       Filter by tag
  -m, --type <MACHINE-TYPE>  Filter by type
  -r, --region <REGION>      Filter by region
  -o, --output <FORMAT>      Output format (json)
  --status-check <CHECK>     Status check to perform (default: cloud-init-status)
  -q, --quiet                Only display machine IDs
  --all                      Include all machines from all sessions
  -h, --help                 Show this message and exit.
```

In addition to the DigitalOcean droplet status, this command queries each machine at `http://<ip>:4242/cgi-bin/<status-check>` (default: `cloud-init-status`) for custom status information. If the endpoint is unreachable, the status is reported as `UNKNOWN`.

#### list-domain

List DNS records within a domain zone.

```
$ machine list-domain --help
Usage: machine list-domain [OPTIONS] [ZONE]

  List domain records

Options:
  -n, --name <RECORD-NAME>  Filter by record name
  -m, --type <RECORD-TYPE>  Filter by record type (default: A and AAAA, use * for all)
  -o, --output <FORMAT>     Output format (json)
  -q, --quiet               Only display record names
  --all                     Include all records from all sessions
  -h, --help                Show this message and exit.
```

If `ZONE` is omitted, uses the `dns-zone` from config. By default, only shows A and AAAA records associated with machines from the current session.

Output formats:
- Default: `name\ttype\tdata`
- `--quiet`: record names only
- `--output json`: JSON array with id, droplet info, name, fqdn, zone, data, ttl, type

#### domains

List all DNS domains in your DigitalOcean account. Takes no options.

#### ssh-keys

List SSH keys in your DigitalOcean account. Output format: `id: name (fingerprint)`

#### projects

List DigitalOcean project names. Takes no options.

#### types

List all machine types defined in the config file (from the `machines` section). Takes no options.
