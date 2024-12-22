import time
from pymavlink import mavutil
from modules.common.data_encoding.message_encoding_decoding import decode_bytes_to_position_global
from modules.common.data_encoding.metadata_encoding_decoding import decode_metadata
from modules.common.data_encoding.worker_enum import WorkerEnum
from modules.common.kml.kml_conversion import positions_to_kml
from pathlib import Path

CONNECTION_ADDRESS = "tcp:localhost:14550"
DELAY = 1
vehicle = mavutil.mavlink_connection(CONNECTION_ADDRESS, source_system=255, source_component=0)
vehicle.wait_heartbeat()
print("connected")

positions = [] 

# There should be 2 loops, one outer infinite loop, and one inner loop that runs expected_position_count number of times
while True:
    msg = vehicle.recv_match(type="STATUSTEXT", blocking=True)
    if not msg:
        print("no message")
    elif msg.get_type() == "BAD_DATA":
        if mavutil.all_printable(msg.data):
            print(msg.data)
    else: 
        # use the decode_metadata to to decode message and get worker_id, then if it matchces proceed to loop expected_positions_count number of times
        success, worker_id, expected_positions_count = decode_metadata(msg.data)  
        if success and worker_id == WorkerEnum.COMMUNICATIONS_WORKER:
            received_positions_count = 0 
            # Use a while loop to receive the expected number of positions
            while received_positions_count < expected_positions_count: 
                #  need to actually receive another message in your for loop, and again check if it's from the right worker. It might be better to make your own counter and change it to a while loop.
                gps_msg = vehicle.recv_match(type="STATUSTEXT", blocking=True) 
                if not gps_msg:
                    print("no message")
                elif gps_msg.get_type() == "BAD_DATA":
                    if mavutil.all_printable(gps_msg.data):
                        print(gps_msg.data) 
                else:
                    success, worker_id, global_position = decode_bytes_to_position_global(gps_msg.data) 
                    if success and worker_id == WorkerEnum.COMMUNICATIONS_WORKER:  
                        print(f"Decoded GPS Data: {global_position.latitude}, {global_position.longitude}, {global_position.altitude}")
                        positions.append(global_position) 
                        received_positions_count += 1
                    else:
                        print(f"Unsuccessful or Non-communications worker message (worker_id: {worker_id})")
            # After collecting all positions, generate KML
            save_directory = Path("path/to/save/kml/files")
            document_name_prefix = "drone_gps_data"
            success, kml_path = positions_to_kml(positions, document_name_prefix, save_directory) 
            if success:
                positions = [] 
            else:
                print("Failed to save KML file.")
        else:
            print(f"Unsuccessful or Non-communications worker message (worker_id: {worker_id})")
    time.sleep(DELAY)