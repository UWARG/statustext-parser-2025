import argparse
import time
from pathlib import Path
from pymavlink import mavutil

from modules.common.data_encoding.message_encoding_decoding import decode_bytes_to_position_global
from modules.common.data_encoding.metadata_encoding_decoding import decode_metadata
from modules.common.data_encoding import worker_enum
from modules.common.kml.kml_conversion import positions_to_kml

CONNECTION_ADDRESS = "tcp:localhost:14550"

def main(save_directory, document_name_prefix):
    vehicle = mavutil.mavlink_connection(CONNECTION_ADDRESS, source_system=255, source_component=0)
    vehicle.wait_heartbeat()
    print("connected")

    while True:
        positions = []
        msg = vehicle.recv_match(type="STATUSTEXT", blocking=True)
        if not msg:
            print("no message")
        elif msg.get_type() == "BAD_DATA":
            if mavutil.all_printable(msg.data):
                print(msg.data)
        else:
            success, worker_id, expected_positions_count = decode_metadata(msg.data)
            if success and worker_id == worker_enum.WorkerEnum.COMMUNICATIONS_WORKER:
                received_positions_count = 0
                while received_positions_count < expected_positions_count:
                    gps_msg = vehicle.recv_match(type="STATUSTEXT", blocking=True)
                    if not gps_msg:
                        print("no message")
                    elif gps_msg.get_type() == "BAD_DATA":
                        if mavutil.all_printable(gps_msg.data):
                            print(gps_msg.data)
                    else:
                        success, worker_id, global_position = decode_bytes_to_position_global(gps_msg.data)
                        if success and worker_id == worker_enum.WorkerEnum.COMMUNICATIONS_WORKER:
                            print(f"Decoded GPS Data: {global_position.latitude}, {global_position.longitude}, {global_position.altitude}")
                            positions.append(global_position)
                            received_positions_count += 1
                        else:
                            print(f"Unsuccessful or Non-communications worker message (worker_id: {worker_id})")
                success, kml_path = positions_to_kml(positions, document_name_prefix, save_directory)
                if success:
                    print(f"KML file saved to {kml_path}")
                else:
                    print("Failed to save KML file")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Collect drone GPS positions and save as KML.")
    parser.add_argument("--save-directory", type=str, default="logs", help="Directory to save KML files.")
    parser.add_argument("--document-name-prefix", type=str, default="IR hotspot locations", help="Prefix for the KML document name.")
    
    args = parser.parse_args()
    save_directory = Path(args.save_directory)
    document_name_prefix = args.document_name_prefix
    
    main(save_directory, document_name_prefix)
