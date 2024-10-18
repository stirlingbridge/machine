# machine
CLI utility to create and manage VMs

Initially supports only DigitalOcean using the [python-digitalocean](https://github.com/koalalorenzo/python-digitalocean) module.

## Usage

### Config File
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
### Command Line Options
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
  -h, --help            Show this message and exit.

Commands:
  create       Create a machine
  destroy      Destroy a machine
  domains      List dns domains
  list         List machines
  list-domain  List domain records
  projects     List projects
  ssh-keys     List ssh keys
```
#### Create Command
```
$ machine create --help
Usage: machine create [OPTIONS]

  Create a machine

Options:
  -n, --name <MACHINE-NAME>       Name for new machine  [required]
  -t, --tag <TAG-TEXT>            tag to be applied to new machine
  -m, --type <MACHINE-TYPE>       create a machine of this type
  -r, --region <REGION-CODE>      create a machine in this region (overrides default from config)
  -s, --machine-size <MACHINE-SLUG>
                                  create a machine of this size (overrides
                                  default from config)
  -s, --image <IMAGE-NAME>        create a machine from this image (overrides default from config)
  --wait-for-ip / --no-wait-for-up
  --update-dns / --no-update-dns
  --initialize / --no-initialize
  -h, --help                      Show this message and exit.
```
