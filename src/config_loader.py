import yaml
import os

class ConfigLoader:
    def __init__(self, config_path="config.yml"):
        self.config_path = config_path
        self.config = {}

    def load_config(self):
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"Config file not found: {self.config_path}")
        
        with open(self.config_path, "r") as f:
            self.config = yaml.safe_load(f)
        
        self._validate_config()
        return self.config

    def _validate_config(self):
        required_keys = ["max_attempts", "allowed_paths"]
        for key in required_keys:
            if key not in self.config:
                raise ValueError(f"Missing required config key: {key}")

if __name__ == "__main__":
    loader = ConfigLoader()
    print(loader.load_config())
