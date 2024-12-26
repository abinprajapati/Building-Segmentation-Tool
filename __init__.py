

# -*- coding: utf-8 -*-
"""
/***************************************************************************
 BuildingFootprintTool
                                 A QGIS plugin
 This plugin helps in handling building footprint tools.
                              -------------------
        begin                : 2024-12-22
        copyright            : (C) 2024 by Your Name
        email                : your.email@example.com
 ***************************************************************************/
"""
from qgis.PyQt.QtCore import QCoreApplication
from qgis.core import QgsProject, QgsApplication
from .building_footprint_tool import BuildingFootprintToolPlugin

def classFactory(iface):
    """Load the BuildingFootprintTool class from file BuildingFootprintTool."""
    return BuildingFootprintToolPlugin(iface)