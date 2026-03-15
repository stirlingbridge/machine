from machine.log import fatal_error
from machine.provider import CloudProvider

KNOWN_PROVIDERS = ["digital-ocean"]


def create_provider(provider_name, provider_config) -> CloudProvider:
    if provider_name == "digital-ocean":
        from machine.providers.digitalocean import DigitalOceanProvider

        return DigitalOceanProvider(provider_config)
    else:
        fatal_error(f"Unknown provider: '{provider_name}'. Known providers: {', '.join(KNOWN_PROVIDERS)}")
