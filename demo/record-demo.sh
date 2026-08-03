#!/usr/bin/env bash
#
# Record docs/images/demo.gif from demo/demo.tape.
#
# The recording is a real run against a live DigitalOcean account — nothing is
# staged or faked. This script only builds the environment the tape assumes and
# cleans up after it:
#
#   * A scratch HOME at /tmp/machine-demo/home containing just the demo config
#     file and the demo ssh key, so the recording neither reads nor displays
#     your real ~/.config/machine, and so each run starts with a fresh session
#     id (session-scoped `list`/`destroy` then only ever see the demo machine).
#   * The config file references the API token, ssh key name, DNS zone and
#     project by ${...} environment variable, so no secret appears on screen.
#   * A best-effort sweep for a leftover demo1 droplet from an aborted run.
#   * A `machine` shim on PATH that runs this working tree, so the recording
#     always shows the current source rather than an installed release.
#
# Costs money: it creates and destroys a real droplet each time it runs.
#
# Required environment:
#   MACHINE_DO_TOKEN    DigitalOcean API token
#   MACHINE_SSH_KEY     Name of an ssh key in the DO account; the matching
#                       private key must be at ~/.ssh/<name>
#   MACHINE_DNS_ZONE    DNS zone hosted at DigitalOcean
#   MACHINE_DO_PROJECT  DO project to assign the droplet to
#
# Requires: vhs, ttyd, ffmpeg, dig and uv on PATH.

set -euo pipefail

cd "$(dirname "$0")/.."
REPO_ROOT="$PWD"
SCRATCH="/tmp/machine-demo"
DEMO_HOME="$SCRATCH/home"
DEMO_NAME="demo1"
# The tape types this zone literally (in the dig, ping and ssh commands), so a
# different zone would need the tape updated to match.
EXPECTED_ZONE="machine.servesthe.world"

missing=()
for tool in vhs ttyd ffmpeg dig uv; do
    command -v "$tool" >/dev/null || missing+=("$tool")
done
if [ ${#missing[@]} -gt 0 ]; then
    echo "error: not on PATH: ${missing[*]}" >&2
    echo "  ffmpeg, ttyd, dig: sudo apt-get install -y ffmpeg ttyd dnsutils" >&2
    echo "  vhs:               https://github.com/charmbracelet/vhs/releases" >&2
    echo "  uv:                curl -LsSf https://astral.sh/uv/install.sh | sh" >&2
    exit 1
fi

missing=()
for var in MACHINE_DO_TOKEN MACHINE_SSH_KEY MACHINE_DNS_ZONE MACHINE_DO_PROJECT; do
    [ -n "${!var:-}" ] || missing+=("$var")
done
if [ ${#missing[@]} -gt 0 ]; then
    echo "error: environment variables not set: ${missing[*]}" >&2
    exit 1
fi

if [ "$MACHINE_DNS_ZONE" != "$EXPECTED_ZONE" ]; then
    echo "error: MACHINE_DNS_ZONE is '$MACHINE_DNS_ZONE' but demo/demo.tape types" >&2
    echo "       '$EXPECTED_ZONE' literally. Update the tape (and EXPECTED_ZONE here)" >&2
    echo "       to record against a different zone." >&2
    exit 1
fi

PRIVATE_KEY="$HOME/.ssh/$MACHINE_SSH_KEY"
if [ ! -f "$PRIVATE_KEY" ]; then
    echo "error: no private key at $PRIVATE_KEY (needed for the recorded ssh)" >&2
    exit 1
fi

echo "==> Building the scratch home"
rm -rf "$SCRATCH"
mkdir -p "$DEMO_HOME/.config/machine" "$DEMO_HOME/.ssh" "$SCRATCH/bin"
install -m 600 "$PRIVATE_KEY" "$DEMO_HOME/.ssh/$MACHINE_SSH_KEY"

# The recorded commands must exercise this working tree, not whatever version of
# `machine` happens to be installed on the recorder's PATH — otherwise a gif
# recorded after a CLI change would silently show the old behaviour (or fail on
# a flag that is not released yet). A shim named `machine` runs the working tree
# and shadows any installed copy, so the recording stays honest without needing
# `uv tool install` to be re-run first.
cat > "$SCRATCH/bin/machine" <<EOF
#!/usr/bin/env bash
exec uv run --quiet --project "$REPO_ROOT" machine "\$@"
EOF
chmod +x "$SCRATCH/bin/machine"
export PATH="$SCRATCH/bin:$PATH"

echo "==> Syncing the working tree"
uv sync --quiet

cat > "$DEMO_HOME/.config/machine/config.yml" <<'EOF'
digital-ocean:
    access-token: ${MACHINE_DO_TOKEN}
    ssh-key: ${MACHINE_SSH_KEY}
    dns-zone: ${MACHINE_DNS_ZONE}
    project: ${MACHINE_DO_PROJECT}
    machine-size: s-1vcpu-1gb
    image: ubuntu-24-04-x64
    region: nyc3

machines:
    demo:
        new-user-name: demo
        script-dir: /opt/machine
        script-url: https://raw.githubusercontent.com/stirlingbridge/machine-provisioning/refs/heads/main/scripts/combine.sh
        script-path: /opt/machine/combine.sh
        script-args:
          - fqdn.sh
          - health.sh
EOF

# Sweep any droplet left behind by an aborted run. --all is needed because a
# previous run had its own session id, which this run's scratch home does not
# share.
sweep_leftovers() {
    local ids
    ids=$(HOME="$DEMO_HOME" machine list --all --name "$DEMO_NAME" -q 2>/dev/null || true)
    if [ -n "$ids" ]; then
        echo "==> Removing leftover $DEMO_NAME droplet(s): $ids"
        # shellcheck disable=SC2086
        HOME="$DEMO_HOME" machine destroy --all --no-confirm $ids || true
    fi
}

sweep_leftovers

# ssh resolves ~/.ssh from the passwd entry, not $HOME, so the recorded ssh
# adds the throwaway host key (and its IP) to the real known_hosts. Put it back
# as it was rather than trying to pick the new entries out afterwards.
KNOWN_HOSTS="$HOME/.ssh/known_hosts"
KNOWN_HOSTS_BACKUP="$SCRATCH/known_hosts.backup"
if [ -f "$KNOWN_HOSTS" ]; then
    cp -p "$KNOWN_HOSTS" "$KNOWN_HOSTS_BACKUP"
fi
restore_known_hosts() {
    if [ -f "$KNOWN_HOSTS_BACKUP" ]; then
        cp -p "$KNOWN_HOSTS_BACKUP" "$KNOWN_HOSTS"
    fi
}
trap restore_known_hosts EXIT

mkdir -p "$REPO_ROOT/docs/images"

echo "==> Recording (creates and destroys a real droplet, ~3 minutes)"
vhs demo/demo.tape

echo "==> Cleaning up"
sweep_leftovers
restore_known_hosts
rm -rf "$SCRATCH"

echo
echo "Wrote $REPO_ROOT/docs/images/demo.gif"
ls -lh "$REPO_ROOT/docs/images/demo.gif"
