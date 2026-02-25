# When the FastAPI server starts up, it needs to know what modules and markers are already
# defined so that it can validate incoming requests and populate the menus on the frontend.
# This registry isn't hardcoded, but rather stored separately in an editable version that
# can be updated as things change. 

# Runs just once at start-up.

# The load_registry() function opens module_registry.json, reads it, and returns the 
# contents as a dict. It's called by main.py and does the following:
#       1. Check that the file actually exists before trying to open it. If not, ERROR
#       2. Open and parse the JSON file. Turns it into a dict "registry"
#       3. Return the parsed dict as a plain Python dict mirroring the JSON format

import json
import os

def load_modules(registry_path: str) -> dict:
    if not os.path.exists(registry_path):                                         
        raise RuntimeError(
            f"No module registry file found at: {registry_path}. Please make sure it exists and restart the server."
        )
    with open(registry_path, encoding="utf-8") as f:                              
        try:
            registry = json.load(f)
        except json.JSONDecodeError as e:
            raise RuntimeError(
                f"The file found at {registry_path} is not a valid JSON: {e}."
            )
    return registry