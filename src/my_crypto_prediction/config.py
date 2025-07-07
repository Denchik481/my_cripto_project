import os
import yaml

def load_params(path="params.yaml"):
    with open(path) as f:
        return yaml.safe_load(f)

def get_data_path(layer, filename="train.parquet"):
    base = os.getenv("DATA_BASE", "../data")
    return os.path.join(base, layer, filename)

def get_layer_params(params, layer):
    return params.get(layer, {})