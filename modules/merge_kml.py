"""
This module takes two generated KML files and merges shared positions based on a threshold.
"""

import argparse
import pathlib
import time

from lxml import etree
from pykml import parser as kml_parser
from pykml.factory import KML_ElementMaker as KML
import pygeohash as pgh


def main(
    precision: int, file_1: str, file_2: str, save_directory: str, document_name_prefix: str
) -> int:
    """
    Parses two KML files for every LatLng point in both file_1 & file_2.

    Converts LatLng points to geohash strings.

    Any points that have the same geohash string, generate an average of their Lat & Lng positions.

    Generate a KML for final average LatLng points.

    Args:
        file_1: Directory to first KML file.
        file_2: Directory to second KML file.
        save_directory (Path): Directory to save the KML file.
        document_name_prefix (str): Prefix for the KML file name.

    Returns:
        int: 0 on success, -1 on error (invalid threshold, couldn't open files, couldn't create new file).
    """

    # Verify precision input
    print("Precision: ", precision)
    if precision < 1 or precision > 12:
        print("Invalid precision level. Should range from 1-12")
        return -1
    if precision < 8:
        print(
            "WARNING: Your precision is now less than 8 characters, meaning the estimations may be largely inaccurate."
        )

    with open(file_1, "r", encoding="utf-8") as f1:
        doc_1 = kml_parser.parse(f1).getroot().Document

    with open(file_2, "r", encoding="utf-8") as f2:
        doc_2 = kml_parser.parse(f2).getroot().Document

    points = {}

    for place in doc_2.iterchildren():  # Append all points from both files
        doc_1.append(place)

    for place in doc_1.iterchildren():
        # Geohash Points
        coordinates = place.Point.coordinates.text.split(",")
        lat = float(coordinates[0])
        long = float(coordinates[1])
        alt = float(coordinates[2])
        geohash = pgh.encode(latitude=lat, longitude=long, precision=precision)

        if geohash not in points:
            points[geohash] = [lat, long, alt]
        else:
            point = points[geohash]
            points[geohash] = [(point[0] + lat) / 2, (point[1] + long) / 2, (point[2] + alt) / 2]

    # print(etree.tostring(doc_1, pretty_print=True).decode())
    print(points)

    # Generate merged KML file
    kml = KML.kml()
    doc = KML.Document()
    kml.append(doc)

    for i, point in enumerate(points.values()):
        doc.append(
            KML.Placemark(
                KML.name(f"Point {i}"),
                KML.Point(KML.coordinates(f"{point[0]},{point[1]},{point[2]}")),
            )
        )

    current_time = time.time()
    pathlib.Path(save_directory).mkdir(exist_ok=True, parents=True)
    kml_file_path = pathlib.Path(save_directory, f"{document_name_prefix}_{int(current_time)}.kml")

    with open(kml_file_path, "wb") as f:
        f.write(etree.tostring(etree.ElementTree(kml), pretty_print=True))

    return 0


DEFAULT_SAVE_DIRECTORY = "logs"
DEFAULT_DOCUMENT_NAME_PREFIX = "Merged_KML"

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Merge two KML files and merge shared positions.")
    parser.add_argument(
        "--precision",
        type=int,
        default=10,
        help="Precision level for geohashing",
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
            args.precision, args.file_1, args.file_2, args.save_directory, args.document_name_prefix
        )
        == 0
    ):
        print("Process completed successfully.")
    else:
        print("Process failed.")
