import json
import os


def load_analysis_methods(registry_path: str) -> dict:
    if not os.path.exists(registry_path):
        raise RuntimeError(
            f"No analysis registry file found at: {registry_path}. "
            "Please make sure it exists and restart the server."
        )
    with open(registry_path, encoding="utf-8") as f:
        try:
            registry = json.load(f)
        except json.JSONDecodeError as e:
            raise RuntimeError(
                f"The file found at {registry_path} is not valid JSON: {e}."
            )
    return registry
