"""
This module connects to a drone via MAVLink, collects GPS position data from a communications worker, 
and generates a KML file after receiving the expected number of positions. The process repeats indefinitely.
"""

import argparse
import pathlib

from pymavlink import mavutil

from modules.common.modules import position_global
from modules.common.modules import position_global_relative_altitude
from modules.common.modules.data_encoding import message_encoding_decoding
from modules.common.modules.data_encoding import metadata_encoding_decoding
from modules.common.modules.data_encoding import worker_enum
from modules.common.modules.kml import kml_conversion


CONNECTION_ADDRESS = "tcp:localhost:14550"


def position_global_to_named_relative_altitude(
    name: str,
    original: position_global.PositionGlobal,
) -> (
    tuple[True, position_global_relative_altitude.NamedPositionGlobalRelativeAltitude]
    | tuple[False, None]
):
    """
    Convert a PositionGlobal to a PositionGlobalRelativeAltitude.
    """
    return position_global_relative_altitude.NamedPositionGlobalRelativeAltitude.create(
        name, original.latitude, original.longitude, original.altitude
    )


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
            continue
        if msg.get_type() == "BAD_DATA":
            if mavutil.all_printable(msg):
                print(f"Bad data received: {msg}")
            print("Error: Bad data")
            return -1

        # Receive first metadata message from communications worker to determine number of hotspots
        try:  # Filter out system messages (they will fail)
            success, worker_id, expected_positions_count = (
                metadata_encoding_decoding.decode_metadata(bytes(msg.text, "utf-8"))
            )
        # except binascii.Error (failed to base64 decode) -- skip processing system messages
        # pylint: disable=bare-except
        except:
            continue
        if not success:
            print(
                f"Error: Failed to decode metadata, message recieved was {msg.text}. Skipping it for now"
            )
            continue
        if worker_id != worker_enum.WorkerEnum.COMMUNICATIONS_WORKER:
            print("Warning: skipping over non-communication worker message")
            continue
        received_positions_count = 0

        # Collecting all hotspot locations
        while received_positions_count < expected_positions_count:
            gps_msg = vehicle.recv_match(type="STATUSTEXT", blocking=True)
            if not gps_msg:
                print("No GPS message received.")
                continue
            if gps_msg.get_type() == "BAD_DATA":
                if mavutil.all_printable(gps_msg):
                    print(f"Bad GPS data received: {gps_msg}")
                print("Error: Bad GPS data")
                return -1
            try:  # Filter out system messages (they will fail)
                success, worker_id, global_position = (
                    message_encoding_decoding.decode_bytes_to_position_global(
                        bytes(gps_msg.text, "utf-8")
                    )
                )
            # except binascii.Error (failed to base64 decode) -- skip processing system messages
            # pylint: disable=bare-except
            except:
                continue
            if not success:
                print(
                    f"Error: Failed to decode GPS data, message received was {gps_msg.text}. Skipping it for now"
                )
                continue
            if worker_id != worker_enum.WorkerEnum.COMMUNICATIONS_WORKER:
                print("Warning: skipping over non-communication worker message")
                continue
            print(
                f"Decoded GPS Data: {global_position.latitude}, {global_position.longitude}, {global_position.altitude}"
            )
            result, named_global_position_relative_altitude = (
                position_global_to_named_relative_altitude(
                    f"Hotspot {received_positions_count+1}",
                    global_position,
                )
            )
            if result:
                positions.append(named_global_position_relative_altitude)
                received_positions_count += 1
            else:
                print("Failed to convert to relative altitude")

        # Generating KML file
        pathlib.Path(save_directory).mkdir(exist_ok=True, parents=True)
        success, kml_path = kml_conversion.named_positions_to_kml(
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

    if main(args.save_directory, args.document_name_prefix) == 0:
        print("Process completed successfully.")
    else:
        print("Process failed.")
