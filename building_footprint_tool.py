from qgis.core import Qgis, QgsProject, QgsVectorLayer
from qgis.PyQt.QtWidgets import QAction, QMessageBox, QDialog, QVBoxLayout, QPushButton, QLabel, QLineEdit, QFileDialog, QHBoxLayout
from qgis.PyQt.QtGui import QIcon
from qgis.gui import QgisInterface
import os
from shapely.geometry import Polygon
import cv2
import numpy as np
from PIL import Image
from osgeo import ogr, osr
from ultralytics import YOLO


class BuildingFootprintToolPlugin:
    def __init__(self, iface: QgisInterface):
        self.iface = iface
        self.tool = None

    def initGui(self):
        """Initialize GUI components and connect actions."""
        self.tool = BuildingFootprintTool(self.iface)  # Initialize the tool
        self.tool.initGui()

    def unload(self):
        """Remove the tool from the interface."""
        if self.tool:
            self.tool.unload()

    def run(self):
        """Activate the tool."""
        self.tool.run()


class BuildingFootprintTool:
    def __init__(self, iface: QgisInterface):
        self.iface = iface
        self.action = None
        self.model = None
        self.input_image_path = ""
        self.output_shapefile_path = ""

    def initGui(self):
        """Initialize GUI components and connect actions."""
        icon_path = os.path.join(os.path.dirname(__file__), "icon.png")  # Adjust icon path as needed
        self.action = QAction(QIcon(icon_path), "Building Footprint Tool", self.iface.mainWindow())
        self.action.triggered.connect(self.show_popup)

        # Add the action to the QGIS toolbar
        self.iface.addToolBarIcon(self.action)

        plugin_dir = os.path.dirname(__file__)  # Get the directory of the plugin
        model_path = os.path.join(plugin_dir, "best.pt")
        if os.path.exists(model_path):
            self.model = YOLO(model_path)
        else:
            QMessageBox.critical(self.iface.mainWindow(), "Error", "YOLO model file not found!")

    def show_popup(self):
        """Show a popup dialog with input and output options."""
        dialog = QDialog()
        dialog.setWindowTitle("Building Footprint Tool")
        layout = QVBoxLayout()

        # Input image label and button
        input_label = QLabel("Select an image for segmentation:")
        layout.addWidget(input_label)
        input_browse_button = QPushButton("Browse Image")
        layout.addWidget(input_browse_button)
        self.input_field = QLineEdit()
        self.input_field.setReadOnly(True)
        layout.addWidget(self.input_field)

        # Output shapefile label and button
        output_label = QLabel("Select the save location for shapefile:")
        layout.addWidget(output_label)
        output_browse_button = QPushButton("Output Location")
        layout.addWidget(output_browse_button)
        self.output_field = QLineEdit()
        self.output_field.setReadOnly(True)
        layout.addWidget(self.output_field)

        # Submit button and Close button in horizontal layout
        button_layout = QHBoxLayout()  # Create a horizontal layout for buttons
        submit_button = QPushButton("Run")
        button_layout.addWidget(submit_button)
        
        close_button = QPushButton("Close")
        button_layout.addWidget(close_button)

        layout.addLayout(button_layout)  # Add the horizontal button layout to the main layout


        # Connect buttons
        input_browse_button.clicked.connect(self.browse_image)
        output_browse_button.clicked.connect(self.browse_save_location)
        submit_button.clicked.connect(lambda: self.submit(dialog))
        close_button.clicked.connect(dialog.reject)  # Close the dialog when clicked

        dialog.setLayout(layout)
        dialog.exec_()

    def browse_image(self):
        """Browse to select the input image."""
        file_dialog = QFileDialog()
        file_dialog.setNameFilters(["Image Files (*.png *.jpg *.jpeg)", "All Files (*)"])
        file_dialog.setWindowTitle("Select an Image")
        if file_dialog.exec_():
            selected_files = file_dialog.selectedFiles()
            if selected_files:
                self.input_image_path = selected_files[0]
                self.input_field.setText(self.input_image_path)

    def browse_save_location(self):
        """Browse to select the output shapefile save location."""
        file_dialog = QFileDialog()
        file_dialog.setFileMode(QFileDialog.AnyFile)
        file_dialog.setDefaultSuffix("shp")
        file_dialog.setNameFilter("Shapefile (*.shp)")
        file_dialog.setWindowTitle("Save Shapefile")
        if file_dialog.exec_():
            selected_file = file_dialog.selectedFiles()[0]
            self.output_shapefile_path = selected_file
            self.output_field.setText(self.output_shapefile_path)

    def submit(self, dialog):
        """Handle the submit button."""
        if not self.input_image_path:
            QMessageBox.warning(None, "Warning", "Please select an image!")
        elif not self.output_shapefile_path:
            QMessageBox.warning(None, "Warning", "Please select a save location for the shapefile!")
        else:
            dialog.accept()
            self.process_building_footprints()

    def process_building_footprints(self):
        """Process the building footprints and save them as a shapefile."""
        try:
            image = Image.open(self.input_image_path)
            results = self.model.predict(image)

            masks = results[0].masks if results and results[0].masks else None
            if masks:
                self.save_masks_as_shapefile(masks, self.output_shapefile_path)
                footprints_layer = QgsVectorLayer(self.output_shapefile_path, "Building Footprints", "ogr")
                if footprints_layer.isValid():
                    QgsProject.instance().addMapLayer(footprints_layer)
                    self.iface.messageBar().pushMessage("Success", "Building footprints loaded into QGIS.", level=Qgis.Info)
                else:
                    self.iface.messageBar().pushMessage("Error", "Failed to load shapefile.", level=Qgis.Critical)
            else:
                self.iface.messageBar().pushMessage("No Footprints", "No building footprints detected.", level=Qgis.Warning)
        except Exception as e:
            self.iface.messageBar().pushMessage("Error", f"An error occurred: {str(e)}", level=Qgis.Critical)

    def save_masks_as_shapefile(self, masks, output_shapefile):
        """Save YOLO masks as a shapefile."""
        driver = ogr.GetDriverByName("ESRI Shapefile")
        if os.path.exists(output_shapefile):
            driver.DeleteDataSource(output_shapefile)
        data_source = driver.CreateDataSource(output_shapefile)
        spatial_ref = osr.SpatialReference()
        spatial_ref.ImportFromEPSG(4326)
        layer = data_source.CreateLayer("footprints", srs=spatial_ref, geom_type=ogr.wkbPolygon)
        layer.CreateField(ogr.FieldDefn("ID", ogr.OFTInteger))

        for i, mask in enumerate(masks.data):
            mask_array = mask.numpy()
            flipped_mask = np.flipud(mask_array)  # Flip both vertically and horizontally

            contours, _ = cv2.findContours((flipped_mask * 255).astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            for contour in contours:
                polygon = Polygon(contour[:, 0, :])
                if polygon.is_valid and not polygon.is_empty:
                    ogr_polygon = ogr.CreateGeometryFromWkt(polygon.wkt)
                    feature = ogr.Feature(layer.GetLayerDefn())
                    feature.SetField("ID", i + 1)
                    feature.SetGeometry(ogr_polygon)
                    layer.CreateFeature(feature)

        data_source = None  # Save and close

    def unload(self):
        """Unload the tool."""
        if self.action:
            self.iface.removeToolBarIcon(self.action)
