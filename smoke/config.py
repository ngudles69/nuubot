from pathlib import Path

from nuubot.config import Config


path = Path("workspace/config/config.toml")
config = Config(path).load()
print()
print(f"Current Mode: {config.general.mode}")
print("Config:")
print()
print(config.model_dump_json(indent=2))
