"""
This module takes two generated KML files and merges shared positions based on a threshold.
"""

import argparse
import pathlib
import time

from lxml import etree
from lxml import objectify
from pykml import parser as kml_parser
from pykml.factory import KML_ElementMaker as KML

from modules.common.modules import position_global
from modules.common.modules import position_local
from modules.common.modules.mavlink import local_global_conversion
from modules.common.modules.logger import logger as log


def validate_placemark(logger: log.Logger, place: objectify.ObjectifiedElement) -> bool:
    """
    Uses common's Logger to log errors and validate a KML Placemark
    """
    if place.name is None:
        logger.error(
            f"Invalid Placemark. All placemarks should have names.\n{etree.tostring(place, pretty_print=True).decode()}"
        )
        return False
    if place.name.text == "":
        logger.error(
            f"Invalid Placemark. All placemarks should have valid names (e.g. Source / Hotspot 1).\n{etree.tostring(place, pretty_print=True).decode()}"
        )
        return False
    if place.Point is None:
        logger.error(
            f"Invalid Placemark. All placemarks should have Points.\n{etree.tostring(place, pretty_print=True).decode()}"
        )
        return False
    if place.Point.coordinates is None:
        logger.error(
            f"Invalid Placemark. All placemarks should have coordinates.\n{etree.tostring(place, pretty_print=True).decode()}"
        )
        return False
    if len(place.Point.coordinates.text) == "":
        logger.error(
            f"Invalid Placemark. All placemarks should have valid coordinates (e.g. Lat, Lng, Alt).\n{etree.tostring(place, pretty_print=True).decode()}"
        )
        return False
    return True


def main(
    threshold: float, file_1: str, file_2: str, save_directory: str, document_name_prefix: str
) -> int:
    """
    Parses two KML files for every LatLng point in both file_1 & file_2.

    Validates Placemarks, Averages Sources, & Converts Hotspot LatLngs (global_pos) to NEDs (local_pos).

    Creates clusters of points then converts them to LatLng for KML generation.

    Args:
        threshold: Threshold (in meters) specifying the distance between points before merging them.
        file_1: Directory to first KML file.
        file_2: Directory to second KML file.
        save_directory (Path): Directory to save the KML file.
        document_name_prefix (str): Prefix for the KML file name.

    Returns:
        int: 0 on success, -1 on error (invalid threshold, couldn't open files, couldn't create new file, invalid KML placemarks).
    """
    # Initialize logger
    result, logger = log.Logger.create(__name__, False)
    if not result:
        print("ERROR: Failed to create Logger")
        return -1

    # Verify threshold input
    logger.info(f"Threshold: {threshold} m")
    if not threshold > 0:
        logger.error("Invalid threshold value. Should be a positive integer (meters).")
        return -1
    if threshold > 10:
        logger.warning(
            "Your threshold is greater than 10m, expect largely imprecise clusters of points."
        )

    # Opening KML files
    try:
        with open(file_1, "r", encoding="utf-8") as f1:
            doc_1 = kml_parser.parse(f1).getroot().Document
    except IOError as e:
        logger.error(f"Failed to open file_1 {file_1}.\n{e}")
        return -1

    try:
        with open(file_2, "r", encoding="utf-8") as f2:
            doc_2 = kml_parser.parse(f2).getroot().Document
    except IOError as e:
        logger.error(f"Failed to open file_2 {file_2}.\n{e}")
        return -1

    hotspots = []
    source = []  # There should only be 1 source per KML
    home = []
    home_pos = None

    for place in doc_2.iterchildren():  # Append file_2 points to file_1
        doc_1.append(place)

    # Preprocess all placemarks
    for i, place in enumerate(doc_1.iterchildren()):
        result = validate_placemark(logger, place)

        if not result:
            return -1

        coordinates = place.Point.coordinates.text.split(",")
        lat = float(coordinates[0])
        long = float(coordinates[1])
        alt = float(coordinates[2])

        if i == 0:
            home = [lat, long, alt]  # The first valid placemark will be our home

            # home (Global Position) used as Home Location
            result, home_pos = position_global.PositionGlobal.create(
                latitude=home[0], longitude=home[1], altitude=home[2]
            )

            if not result:
                logger.error(
                    "Failed to create Global Position (home_pos) from Placemark ({place.name.text}).\n{etree.tostring(place, pretty_print=True).decode()}"
                )
                return -1

        if "Source" in place.name.text:  # Average all source points
            if len(source) == 0:
                source = [lat, long, alt]
            else:
                source[0] = (source[0] + lat) / 2
                source[1] = (source[1] + long) / 2
                source[2] = (source[2] + alt) / 2

        elif "Hotspot" in place.name.text:
            # Hotspot (Global Position)
            result, hotspot = position_global.PositionGlobal.create(
                latitude=lat, longitude=long, altitude=alt
            )
            if not result:
                logger.error(
                    "Failed to create Global Position (hotspot) for Hotspot ({place.name.text}).\n{etree.tostring(place, pretty_print=True).decode()}"
                )
                return -1

            # Convert Global Pos to Local Pos (Hotspot) using Home Location (home)
            result, local_pos = local_global_conversion.position_local_from_position_global(
                home_pos, hotspot
            )

            if not result:
                logger.error(
                    "Failed to convert Global Position (hotspot) to Local Position (local_pos) for Hotspot ({place.name.text}).\n{etree.tostring(place, pretty_print=True).decode()}"
                )
                return -1

            hotspots.append([local_pos.north, local_pos.east, local_pos.down])

        else:
            logger.error(
                f"Invalid Placemark name in KML ({place.name.text}).\n{etree.tostring(place, pretty_print=True).decode()}"
            )
            return -1

    # Clustering Hotspots
    clusters = []
    merged_indices = []

    for i, hotspot_i in enumerate(hotspots):
        if i not in merged_indices:
            cluster = [hotspot_i]
            for j, hotspot_j in enumerate(hotspots):
                if i != j and j not in merged_indices:
                    dist_squared = (hotspot_j[0] - hotspot_i[0]) ** 2 + (
                        hotspot_j[1] - hotspot_i[1]
                    ) ** 2

                    if threshold**2 > dist_squared:
                        cluster.append([hotspot_j[0], hotspot_j[1], hotspot_j[2]])
                        merged_indices.append(j)

            cluster_lat = sum(point[0] for point in cluster) / len(cluster)
            cluster_long = sum(point[1] for point in cluster) / len(cluster)
            cluster_alt = sum(point[2] for point in cluster) / len(cluster)

            # Append the average of the cluster's points
            clusters.append([cluster_lat, cluster_long, cluster_alt])

    # Convert local position clusters to Global Pos for KML
    global_clusters = []

    for cluster in clusters:
        result, hotspot = position_local.PositionLocal.create(
            north=cluster[0], east=cluster[1], down=cluster[2]
        )

        if not result:
            logger.error("Failed to create Local Position (hotspot)")
            return -1

        result, global_pos = local_global_conversion.position_global_from_position_local(
            home_pos, hotspot
        )

        if not result:
            logger.error(
                "Failed to convert Local Position (hotspot) to Global Position (global_pos)"
            )
            return -1

        global_clusters.append(global_pos)

    # Generate merged KML file
    kml = KML.kml()
    doc = KML.Document()
    kml.append(doc)

    doc.append(
        KML.Placemark(
            KML.name("Source"),
            KML.Point(KML.coordinates(f"{source[0]},{source[1]},{source[2]}")),
        )
    )

    for i, point in enumerate(global_clusters):
        doc.append(
            KML.Placemark(
                KML.name(f"Hotspot {i+1}"),  # Start counting Hotspots at 1
                KML.Point(KML.coordinates(f"{point.latitude},{point.longitude},{point.altitude}")),
            )
        )

    current_time = time.time()
    pathlib.Path(save_directory).mkdir(exist_ok=True, parents=True)
    kml_file_path = pathlib.Path(save_directory, f"{document_name_prefix}_{int(current_time)}.kml")

    # Write to KML file
    try:
        with open(kml_file_path, "w", encoding="utf-8") as f:
            f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
            f.write(etree.tostring(etree.ElementTree(kml), pretty_print=True).decode("utf-8"))
    except IOError as e:
        logger.error(f"Failed to write to merged file.\n{e}")
        return -1

    return 0


DEFAULT_SAVE_DIRECTORY = "logs"
DEFAULT_DOCUMENT_NAME_PREFIX = "Merged_KML"

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Merge two KML files and merge overlapping/close points."
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=1,
        help="Threshold for merging points (meters)",
    )
    parser.add_argument("--file-1", type=str, help="KML file to be merged")
    parser.add_argument("--file-2", type=str, help="KML file to be merged")
    parser.add_argument(
        "--save-directory",
        type=str,
        default=DEFAULT_SAVE_DIRECTORY,
        help="Directory to save merged KML file",
    )
    parser.add_argument(
        "--document-name-prefix",
        type=str,
        default=DEFAULT_DOCUMENT_NAME_PREFIX,
        help="Prefix for the KML document name.",
    )

    args = parser.parse_args()

    if (
        main(
            args.threshold, args.file_1, args.file_2, args.save_directory, args.document_name_prefix
        )
        == 0
    ):
        print("Process completed successfully.")
    else:
        print("Process failed. Check logs for more detail.")
