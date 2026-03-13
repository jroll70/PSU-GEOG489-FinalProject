import os
import pandas as pd
import arcpy
import csv
from arcgis.gis import GIS
from arcgis.geocoding import geocode

class GeocodeStrDatabase:
    def __init__(self, inputCsv, filteredFolder, geocodedFolder, aprxPath):
        self.inputCsv = inputCsv
        self.filteredFolder = filteredFolder
        self.geocodedFolder = geocodedFolder
        self.aprxPath = aprxPath

        self.aprx = arcpy.mp.ArcGISProject(self.aprxPath)
        self.map = self.aprx.listMaps()[0]
        arcpy.env.overwriteOutput = True

    def filterDatabase(self):
        df = pd.read_csv(self.inputCsv)

        vr = df[df['Vacation Rental or Homestay'] == "Vacation Rental"] \
                .drop_duplicates(subset=['Address'])
        hs = df[df['Vacation Rental or Homestay'] == "Homestay"] \
                .drop_duplicates(subset=['Address'])

        vrPath = os.path.join(self.filteredFolder, "ShortTermRental.csv")
        hsPath = os.path.join(self.filteredFolder, "Homestays.csv")

        vr.to_csv(vrPath, index=False)
        hs.to_csv(hsPath, index=False)

        return [vrPath, hsPath]

    def geocodeCsv(self, csvPath):
        fileName = os.path.splitext(os.path.basename(csvPath))[0]
        outputFc = os.path.join(self.aprx.defaultGeodatabase, fileName)

        arcpy.geocoding.GeocodeAddresses(
            in_table=csvPath,
            address_locator="https://geocode.arcgis.com/arcgis/rest/services/World/GeocodeServer"
        )

        self.map.addDataFromPath(outputFc)
        return outputFc

    def run(self):
        csvList = self.filterDatabase()
        outputs = []

        for csvPath in csvList:
            outputFc = self.geocodeCsv(csvPath)
            outputs.append(outputFc)

        self.aprx.save()
        return outputs
    

class BufferGenerator:
    def __init__(self, agendaCsv, outputFolder, aprxPath):
        self.agendaCsv = agendaCsv
        self.outputFolder = outputFolder
        self.aprx = arcpy.mp.ArcGISProject(aprxPath)
        self.map = self.aprx.listMaps()[0]

        self.gis = GIS("home")
        self.projectedSr = arcpy.SpatialReference(2284)

    def geocodeAddress(self, address):
        result = geocode(address)
        if not result:
            return None

        loc = result[0]['location']
        pointGeom = arcpy.PointGeometry(
            arcpy.Point(loc['x'], loc['y']),
            arcpy.SpatialReference(4326)
        )
        return pointGeom.projectAs(self.projectedSr)

    def createBuffer(self, geom, distance, label):
        safeLabel = label.replace(',', '').replace(' ', '_')
        outputPath = f"{self.outputFolder}/{safeLabel}_Buffer"
        bufferFc = arcpy.analysis.Buffer(geom, outputPath, distance)
        self.map.addDataFromPath(bufferFc)
        return bufferFc

    def run(self):
        createdBuffers = []

        with open(self.agendaCsv, 'r') as csvFile:
            reader = csv.DictReader(csvFile)

            for row in reader:
                address = row['Address']
                projectedPoint = self.geocodeAddress(address)

                if not projectedPoint:
                    continue

                buffer500 = self.createBuffer(projectedPoint, "500 Feet", f"{address} 500 Feet")
                buffer1mile = self.createBuffer(projectedPoint, "1 Miles", f"{address} 1 Miles")

                createdBuffers.extend([buffer500, buffer1mile])

        self.aprx.save()
        return createdBuffers
    
class ReportGenerator:
    def __init__(self, bufferFolder, templateCsv, aprxPath):
        self.bufferFolder = bufferFolder
        self.templateCsv = templateCsv
        self.aprxPath = aprxPath

        self.aprx = arcpy.mp.ArcGISProject(self.aprxPath)
        self.map = self.aprx.listMaps()[0]

        self.featureLayers = ["ShortTermRental", "Homestays", "Parcels"]
        arcpy.env.workspace = self.bufferFolder

    def run(self):
        bufferFiles = arcpy.ListFeatureClasses("*.shp")

        with open(self.templateCsv, 'a', newline='') as csvOut:
            writer = csv.writer(csvOut)

            for shpPath in bufferFiles:
                tempLayer = arcpy.management.MakeFeatureLayer(shpPath, "tempBuffer")

                rowValues = [shpPath]

                for layerName in self.featureLayers:
                    selection = arcpy.management.SelectLayerByLocation(
                        layerName, "INTERSECT", tempLayer
                    )
                    matchCount = int(arcpy.management.GetCount(selection)[0])
                    rowValues.append(matchCount)

                writer.writerow(rowValues)
                arcpy.management.Delete(tempLayer)

        return True