from .geopackage_replacer import GeopackageReplacerPlugin


def classFactory(iface):
    """QGIS calls this to instantiate the plugin."""
    return GeopackageReplacerPlugin(iface)
