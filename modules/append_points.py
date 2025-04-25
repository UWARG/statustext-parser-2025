"""
This module appends points to a KML file.
The points are charactorized to be a hotspot or a source of fire.
"""

from lxml import etree
from pykml import parser
from pykml.factory import KML_ElementMaker as KML


def append_hotspot(
    kml_file: str,
    latitude: float,
    longitude: float,
) -> bool:
    """
    Append a hotspot to the KML file.

    Args:
        kml_file (str): Path to the KML file.
        latitude (float): Latitude of the hotspot.
        longitude (float): Longitude of the hotspot.
    """

    with open(kml_file, "r", encoding="utf-8") as file:
        kml = parser.parse(file).getroot()

    if kml is None:
        print("Error: KML file could not be opened.")
        return False

    # Counts number of existing hotspots for proper indexing of the new hotspot
    new_hotspot_index = 1
    for point in kml.Document.Placemark:
        if "Hotspot" in str(point.name):
            new_hotspot_index += 1

    # Create a new Placemark and append it to the KML
    new_placemark = KML.Placemark(
        KML.name("Hotspot " + str(new_hotspot_index)),
        KML.Point(KML.coordinates(f"{longitude},{latitude},0")),
    )
    kml.Document.append(new_placemark)

    with open(kml_file, "w", encoding="utf-8") as output:
        etree.cleanup_namespaces(kml)
        output.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        output.write(etree.tostring(kml, pretty_print=True).decode("utf-8"))

    return True


def append_source(
    kml_file: str,
    latitude: float,
    longitude: float,
    description: str,
) -> bool:
    """
    Append a source to the KML file.

    Args:
        kml_file (str): Path to the KML file.
        latitude (float): Latitude of the source.
        longitude (float): Longitude of the source.
        description (str): Description of the source.
    """

    with open(kml_file, "r", encoding="utf-8") as file:
        kml = parser.parse(file).getroot()

    if kml is None:
        print("Error: KML file could not be opened.")
        return False

    # Create a new Placemark and append it to the KML
    new_placemark = KML.Placemark(
        KML.name("Source"),
        KML.description(description),
        KML.Point(KML.coordinates(f"{longitude},{latitude},0")),
    )
    kml.Document.append(new_placemark)

    with open(kml_file, "w", encoding="utf-8") as output:
        etree.cleanup_namespaces(kml)
        output.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        output.write(etree.tostring(kml, pretty_print=True).decode("utf-8"))

    return True
