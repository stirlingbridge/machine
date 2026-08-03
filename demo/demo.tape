# VHS tape for the README demo animation.
#
# Renders docs/images/demo.gif — a real, unfaked run of the machine CLI against
# a live DigitalOcean account: validate the config, create a droplet with DNS
# and cloud-init provisioning, inspect it, ssh into it, then destroy it and show
# that both the machine and its DNS record are gone.
#
# Run it via ./demo/record-demo.sh, which builds the scratch HOME (config file
# and ssh key) that this tape assumes, and cleans up afterwards. Nothing here is
# staged: every command talks to the real DigitalOcean API.
#
# Requires: vhs, ttyd, ffmpeg, dig, and the `machine` CLI on PATH.

Output docs/images/demo.gif

Set Shell bash
Set FontSize 14
Set Width 1100
Set Height 480
Set Padding 18
Set Framerate 20
Set TypingSpeed 20ms
Set Theme "Catppuccin Mocha"

# --- off-camera setup ------------------------------------------------------
# HOME points at a scratch home holding only the demo config file and the demo
# ssh key, so the recording never touches (or shows) the real ~/.config/machine.
# The API token, ssh key name, DNS zone and project name come from the
# environment via ${...} substitution in the config file, so no secret is ever
# on screen.
Hide
Type "cd /tmp/machine-demo && export HOME=/tmp/machine-demo/home"
Enter
Type `PS1='\[\e[38;5;114m\]▸\[\e[0m\] '`
Enter
Type "clear"
Enter
Show

# --- the config ------------------------------------------------------------
# Show what the tool is configured with before using it: which provider, which
# region and image, and the "demo" machine type whose provisioning scripts run
# on first boot. The token is a ${...} reference, not a literal.
Type "cat ~/.config/machine/config.yml"
Enter
Wait+Line@60s /^▸$/
Sleep 4s

# `check` answers "is this config actually going to work?" without creating
# anything: each line is a live read-only API call.
Type "machine check"
Enter
Wait+Line@60s /^▸$/
Sleep 3s

Type "clear"
Enter

# --- create ----------------------------------------------------------------
# ~40s of real work: create the droplet, wait for its IP, add the DNS A record,
# and hand cloud-init a user-data payload that creates the `demo` user, installs
# the ssh key and runs the provisioning scripts from the machine type.
Type "machine create --name demo1 --type demo --wait-for-ip"
Enter
Wait+Line@300s /^▸$/
Sleep 2s

Type "machine list"
Enter
Wait+Line@60s /^▸$/
Sleep 2s

# The A record was created by `create`; dig proves it is really in public DNS
# and not just something the tool printed.
Type "machine list-domain"
Enter
Wait+Line@60s /^▸$/
Sleep 1500ms

Type "dig +short demo1.machine.servesthe.world"
Enter
Wait+Line@60s /^▸$/
Sleep 2s

Type "ping -c 3 demo1.machine.servesthe.world"
Enter
Wait+Line@60s /^▸$/
Sleep 2500ms

Type "clear"
Enter

# --- wait for provisioning to finish (off camera) --------------------------
# `status` reports UNKNOWN until the health endpoint the machine type installs
# is serving, which is a plain "not up yet", not a result worth filming. Poll
# off camera so the status shown next is the real, settled one.
Hide
Type "until machine status | grep -q 'cloud-init-status=UP'; do sleep 5; done"
Enter
Wait+Line@600s /^▸$/
Type "clear"
Enter
Show

# --- inspect ---------------------------------------------------------------
# machine-status comes from the provider API; cloud-init-status comes from the
# machine itself, so UP means provisioning actually completed on the box.
Type "machine status"
Enter
Wait+Line@60s /^▸$/
Sleep 3s

# And it is a working machine: the key named in the config was installed for
# the `demo` user cloud-init created, and the provisioning script wrote the
# machine's FQDN to /etc/machine/fqdn.
Type `ssh -i ~/.ssh/machine-demo -o StrictHostKeyChecking=accept-new \`
Enter
Type `  demo@demo1.machine.servesthe.world 'id -un; hostname -f; cat /etc/machine/fqdn'`
Enter
Wait+Line@120s /^▸$/
Sleep 4s

# --- destroy ---------------------------------------------------------------
# `list -q` prints ids only, so the ids of this session's machines can be piped
# straight into destroy. Confirmation deliberately requires exactly YES.
Type "machine destroy $(machine list -q)"
Enter
# The confirmation prompt leaves the cursor on an empty input line, so match
# the screen rather than the last line.
Wait+Screen@60s /Type YES/
Sleep 2s
Type "YES"
Enter
Wait+Line@300s /^▸$/
Sleep 2s

# Both the droplet and its DNS record are gone — destroy removes the A record
# it created along with the machine.
Type "machine list"
Enter
Wait+Line@60s /^▸$/
Sleep 1s

Type "machine list-domain"
Enter
Wait+Line@60s /^▸$/
Sleep 4s
