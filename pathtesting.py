import os
config_path = "/Users/pascal-maker/agentscomparison/sam2/sam2/sam2_hiera_l.yaml"
print(f"Config exists: {os.path.exists(config_path)}")

import yaml
with open(config_path, 'r') as f:
    config = yaml.safe_load(f)
print("Config loaded successfully!")
print(f"Config keys: {list(config.keys())}")