import os
import pandas as pd
import arcpy
import csv
from arcgis.gis import GIS
from arcgis.geocoding import geocode

# Custom locator
# Update this path
locatorPath = r"C:\PSU\geog489\analysis_tool\analysis_project\NorfolkCityAddresses.loc"

# Creates a scratch gdb to prevent schema locks
# Update this path
scratchGdb = r"C:\PSU\geog489\analysis_tool\scratch\analysis_scratch.gdb"

class GeocodeStrDatabase:
    """
    This class is used for Geocoding the Short Term rental database
    """
    def __init__(self, inputCsv, filteredFolder, geocodedFolder, mapObject, aprxPath):
        self.inputCsv = inputCsv
        self.filteredFolder = filteredFolder
        self.geocodedFolder = geocodedFolder
        self.map = mapObject
        self.locatorPath = locatorPath
        self.aprxPath = aprxPath


        arcpy.env.overwriteOutput = True

        # Creates a Scratch Workspace to prevent schema locks
        self.aprxFolder = os.path.dirname(self.aprxPath)
        self.scratchFolder = os.path.join(self.aprxFolder, "scratch")
        self.scratchGdb = os.path.join(self.scratchFolder, "analysis_scratch.gdb")

        if not os.path.exists(self.scratchFolder):
            os.makedirs(self.scratchFolder)

        if not arcpy.Exists(self.scratchGdb):
            arcpy.management.CreateFileGDB(self.scratchFolder, "analysis_scratch.gdb")


    # This function filters the database into two CSVs based on field values
    def filterDatabase(self):
        print("Filtering")
        df = pd.read_csv(self.inputCsv)

        vr = df[df['Vacation Rental or Homestay'] == "Vacation Rental"].drop_duplicates("Address")
        hs = df[df['Vacation Rental or Homestay'] == "Homestay"].drop_duplicates("Address")

        vrPath = os.path.join(self.filteredFolder, "ShortTermRental.csv")
        hsPath = os.path.join(self.filteredFolder, "Homestays.csv")

        vr.to_csv(vrPath, index=False)
        hs.to_csv(hsPath, index=False)

        print("DB Filtered")
        return [vrPath, hsPath]

    # This Function geocodes the STR csvs and deletes previously created layers
    def geocodeCsv(self, csvPath):

        fileName = os.path.splitext(os.path.basename(csvPath))[0]
        fileName = fileName.replace(" ", "_").replace("-", "_")
        fileName = ''.join(c for c in fileName if c.isalnum() or c == "_")

        outputFc = os.path.join(self.scratchGdb, fileName)

        # Deletes the old layers to allow for updated data
        if arcpy.Exists(outputFc):
            try:
                arcpy.management.Delete(outputFc)
            except:
                raise Exception(f"Failed: {outputFc} is locked")

        fieldMappings = "Address Address VISIBLE NONE"

        result = arcpy.geocoding.GeocodeAddresses(
            in_table=csvPath,
            address_locator=self.locatorPath,
            in_address_fields=fieldMappings,
            out_feature_class=outputFc
        )

        print("Geocoded:", result)
        self.map.addDataFromPath(outputFc)
        return outputFc

    # This function runs the above functions
    def run(self):
        csvList = self.filterDatabase()
        outputs = []

        for csvPath in csvList:
            outputs.append(self.geocodeCsv(csvPath))

        return outputs

class BufferGenerator:
    """
    This class creates the buffers used for selection around the tiems that will be reported on
    """
    def __init__(self, agendaCsv, outputFolder, mapObject, aprxPath):
        self.agendaCsv = agendaCsv
        self.outputFolder = outputFolder
        self.map = mapObject
        self.aprxPath = aprxPath

        self.gis = GIS("home")
        self.projectedSr = arcpy.SpatialReference(2284)

        os.makedirs(self.outputFolder, exist_ok=True)

    # This function geocodes the addresses to points that will be used as the center of the buffers
    def geocodeAddress(self, address):
        result = geocode(address)
        if not result:
            return None

        loc = result[0]["location"]
        pt = arcpy.PointGeometry(arcpy.Point(loc["x"], loc["y"]), arcpy.SpatialReference(4326))
        return pt.projectAs(self.projectedSr)

    # This Function creates the one mile and 500 foot buffers around the address points
    def createBuffer(self, geom, distanceValue, distanceLabel, address):
        # Standardize file naming
        safeAddress = address.replace(",", "").replace(" ", "_")

        # Build output FC name with no duplicates
        outputName = f"{safeAddress}_{distanceLabel}"

        outputFc = os.path.join(self.outputFolder, outputName)

        # If exists, delete it
        if arcpy.Exists(outputFc):
            arcpy.Delete_management(outputFc)

        # Perform buffer
        bufferFc = arcpy.analysis.Buffer(
            in_features=geom,
            out_feature_class=outputFc,
            buffer_distance_or_field=distanceValue
        )

        self.map.addDataFromPath(bufferFc)
        return bufferFc

    # This Function runs the above functions
    def run(self):
        for f in os.listdir(self.outputFolder):
            if f.endswith(".shp") or f.endswith(".dbf") or f.endswith(".shx") or f.endswith(".prj"):
                os.remove(os.path.join(self.outputFolder, f))
        
        createdBuffers = []

        with open(self.agendaCsv, "r") as csvFile:
            reader = csv.DictReader(csvFile)

            for row in reader:
                address = row["Address"]
                projectedPoint = self.geocodeAddress(address)

                if projectedPoint:

                    # 500 ft buffer
                    createdBuffers.append(
                        self.createBuffer(
                            geom=projectedPoint,
                            distanceValue="500 Feet",
                            distanceLabel="500ft",
                            address=address
                        )
                    )

                    # 1-mile buffer
                    createdBuffers.append(
                        self.createBuffer(
                            geom=projectedPoint,
                            distanceValue="1 Miles",
                            distanceLabel="1mile",
                            address=address
                        )
                    )

        return createdBuffers

class ReportGenerator:
    """
    This  class is used to generate the report for each address that will reported on
    """
    def __init__(self, bufferFolder, templateCsv, mapObject, aprxPath):
        self.bufferFolder = bufferFolder
        self.templateCsv = templateCsv
        self.map = mapObject
        self.aprxPath = aprxPath

        # Scratch GDB (same folder geocode tool uses)
        self.scratchGdb = os.path.join(
            os.path.dirname(self.aprxPath),
            "scratch",
            "analysis_scratch.gdb"
        )

        if not arcpy.Exists(self.scratchGdb):
            raise Exception(f"Scratch GDB not found: {self.scratchGdb}")

        aprxObj = arcpy.mp.ArcGISProject(self.aprxPath)
        projectGdb = aprxObj.defaultGeodatabase

        # STR + Homestays in scratch GDB
        # Parcels in project GDB
        self.fcPaths = {
            "ShortTermRental": os.path.join(self.scratchGdb, "ShortTermRental"),
            "Homestays": os.path.join(self.scratchGdb, "Homestays"),
            "Parcels": os.path.join(projectGdb, "Parcels")
        }

        for name, path in self.fcPaths.items():
            if not arcpy.Exists(path):
                raise Exception(f"Feature class '{name}' not found: {path}")

        arcpy.env.workspace = self.bufferFolder

    # This function runs the above class
    def run(self):

        bufferFiles = list(set(arcpy.ListFeatureClasses("*.shp")))
        bufferFiles.sort()

        with open(self.templateCsv, 'a', newline='') as csvOut:
            writer = csv.writer(csvOut)

            for shpPath in bufferFiles:

                tempBuffer = arcpy.MakeFeatureLayer_management(shpPath, "tempBuffer")

                rowValues = [os.path.basename(shpPath)]

                # Loop through STR, Homestays, Parcels once per buffer
                for name, fcPath in self.fcPaths.items():
                    targetLayer = arcpy.MakeFeatureLayer_management(fcPath, f"{name}_lyr")
                    sel = arcpy.management.SelectLayerByLocation(targetLayer, "INTERSECT", tempBuffer)
                    count = int(arcpy.management.GetCount(sel)[0])
                    rowValues.append(count)
                    arcpy.management.Delete(targetLayer)

                # Add totals and percentages
                str_count = rowValues[1]
                homestay_count = rowValues[2]
                parcel_count = rowValues[3]

                total_count = str_count + homestay_count
                percent_of_parcels = (total_count / parcel_count * 100) if parcel_count != 0 else 0

                rowValues.append(total_count)
                rowValues.append(percent_of_parcels)

                writer.writerow(rowValues)
                arcpy.management.Delete(tempBuffer)

        return True