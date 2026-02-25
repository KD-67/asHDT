# When data is requested, read_timeseries() finds the requested data files and returns their contents as a clean, sorted list.
# It acts as the bridge between raw data and the rest of the backend, it's the only thing that ever touches the raw_data folders.
# It uses the index.json files to quickly filter the files and only open the ones it actually needs.

# The specific steps of the function are:
#   0. logger: sets up logging channel for this specific file ("__name__" automatically becomes the path ("backend.core.storage.data_reader") so that any errors that 
#       come from here can be quickly identified).
#   1. marker_folder: builds the file path pointing to the folder containing the correct biomarkers by taking all of the folder names as arguments.
#   2. index_path: builds the file path pointing to the correct index.json file by taking marker_folder and 'index.json' as arguments. If there it can't find it, ERROR MESSAGE
#   3. index: opens the index.json that it found and converts it into a python dict, just like in load_modules().
#   4. entries: the entries variable from the index.json is the list of datapoints, each with a value and a timestamp. This function extracts them into a variable.
#   5. filtered_entries: loops through all entries in index, converting all of the timestape strings into datetime objects that it can use. The "replace("Z", "+00:00")" part is 
#       because old python versions don't understand that the Z means UTC, so that it's always understood. After this it checks if the timedate falls within the user-requested 
#       window, and if yes it gets added to filtered_entries.
#   6. datapoints: for every filtered entry: the function builds the file path and opens the original raw JSON for each one. If any files are missing or corrupt, it just skips
#       them instead of crashing. "datapoints" is a newly created dict that will have the relevant info added to it soon.
#   7. parsed_timestamp: converts the timestamp to a datetime object so that the computer can do math on it.
#   8. datapoints.append(datapoint): populates the datapoints dict with the updated entries that were filtered and have datetime objects as timestamps.
#   9. sort: sorts the final list chronologically to make sure that they're in order.
#   10. return: returns the final sorted list of filtered datapoints with the right datetime format

import json
import os
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

def read_timeseries(
    archive_root: str,
    subject_id: str,
    module_id: str,
    marker_id: str,
    from_time: datetime,
    to_time: datetime,
) -> list[dict]:
    
    marker_folder = os.path.join(archive_root, subject_id, module_id, marker_id)
    index_path = os.path.join(marker_folder, "index.json")

    if not os.path.exists(index_path):
        raise FileNotFoundError(
            f"No index.json found at {index_path}. "
            f"Check that subject_id='{subject_id}', module_id='{module_id}', "
            f"and marker_id='{marker_id}' are correct and that data exists in the archive."
        )

    with open(index_path, encoding="utf-8") as f:
        index = json.load(f)

    entries = index["entries"]

    filtered_entries = []
    for entry in entries:

        entry_time = datetime.fromisoformat(
            entry["timestamp"].replace("Z", "+00:00")
        )

        if from_time <= entry_time <= to_time:
            filtered_entries.append(entry)

    datapoints = []
    for entry in filtered_entries:
        file_path = os.path.join(marker_folder, entry["file"])

        try:
            with open(file_path, encoding="utf-8") as f:
                datapoint = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.warning(
                "Skipping data point file '%s': %s", file_path, e
            )
            continue

        datapoint["parsed_timestamp"] = datetime.fromisoformat(
            datapoint["timestamp"].replace("Z", "+00:00")
        )

        datapoints.append(datapoint)

    datapoints.sort(key=lambda dp: dp["parsed_timestamp"])

    return datapoints