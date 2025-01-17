"""
This module connects to a drone via MAVLink, collects GPS position data from a communications worker, 
and generates a KML file after receiving the expected number of positions. The process repeats indefinitely.
"""

import argparse
from pathlib import Path


from pymavlink import mavutil
from modules.common.modules.data_encoding import message_encoding_decoding
from modules.common.modules.data_encoding import metadata_encoding_decoding
from modules.common.modules.data_encoding import worker_enum
import modules.common.modules.kml.kml_conversion


CONNECTION_ADDRESS = "tcp:localhost:14550"


def main(save_directory: str, document_name_prefix: str) -> int:
    """
    Connects to a drone, collects GPS position data, and generates a KML file.

    The function listens for GPS data messages, decodes them into positions,
    and saves them as a KML file in the specified directory once the expected
    number of positions is received.

    Args:
        save_directory (Path): Directory to save the KML file.
        document_name_prefix (str): Prefix for the KML file name.

    Returns:
        int: 0 on success, -1 on error (connection failure, invalid data, or failure to save KML).
    """
    save_directory = Path(args.save_directory)
    document_name_prefix = args.document_name_prefix
    
    vehicle = mavutil.mavlink_connection(CONNECTION_ADDRESS, source_system=255, source_component=0)
    # Catch library and other unexpected errors
    # pylint: disable=broad-exception-caught
    try:
        vehicle.wait_heartbeat()
        print("connected")
    except Exception as e:
        print(f"Error connecting to vehicle: {e}")
        return -1
    while True:
        positions = []
        msg = vehicle.recv_match(type="STATUSTEXT", blocking=True)
        if not msg:
            print("no message")
        elif msg.get_type() == "BAD_DATA":
            if mavutil.all_printable(msg.data):
                print(msg.data)
            return -1
        else:
            success, worker_id, expected_positions_count = (
                metadata_encoding_decoding.decode_metadata(msg.data)
            )
            if not success or worker_id != worker_enum.WorkerEnum.COMMUNICATIONS_WORKER:
                return
            received_positions_count = 0
            while received_positions_count < expected_positions_count:
                gps_msg = vehicle.recv_match(type="STATUSTEXT", blocking=True)
                if not gps_msg:
                    print("no message")
                    continue 
                if gps_msg.get_type() == "BAD_DATA":
                    if mavutil.all_printable(gps_msg.data):
                        print(gps_msg.data)
                    return -1 
                success, worker_id, global_position = (
                    message_encoding_decoding.decode_bytes_to_position_global(gps_msg.data)
                ) 
                if not success or worker_id != worker_enum.WorkerEnum.COMMUNICATIONS_WORKER:
                    print(f"Unsuccessful or Non-communications worker message (worker_id: {worker_id})")
                    return -1 
                print(
                    f"Decoded GPS Data: {global_position.latitude}, {global_position.longitude}, {global_position.altitude}"
                ) 
                positions.append(global_position)
                received_positions_count += 1 
            success, kml_path = kml_conversion.positions_to_kml(
                positions, document_name_prefix, save_directory
            ) 
            if not success:
                print("Failed to save KML file")
                return -1
            print(f"KML file saved to {kml_path}")
    return 0 
DEFAULT_SAVE_DIRECTORY = "logs"
DEFAULT_DOCUMENT_NAME_PREFIX = "IR hotspot locations"
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Collect drone GPS positions and save as KML.")
    parser.add_argument(
        "--save-directory",
        type=str,
        default=DEFAULT_SAVE_DIRECTORY,
        help="Directory to save KML files.",
    )
    parser.add_argument(
        "--document-name-prefix",
        type=str,
        default=DEFAULT_DOCUMENT_NAME_PREFIX,
        help="Prefix for the KML document name.",
    )
    args = parser.parse_args()
    main(save_directory, document_name_prefix)
