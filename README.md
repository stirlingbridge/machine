# machine
CLI utility to create and manage VMs

Initially supports only DigitalOcean using the [python-digitalocean](https://github.com/koalalorenzo/python-digitalocean) module.

## Usage

Access token and other settings configured in the file `~/.machine/config.yml` :
```
digital-ocean:
    access-token: dop_v1_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
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
