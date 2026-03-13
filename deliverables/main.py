from analysis_functions import GeocodeStrDatabase, BufferGenerator, ReportGenerator
from PyQt6.QtWidgets import QApplication, QWidget, QLineEdit, QPushButton
from PyQt6.QtCore import Qt

class MainWindow(QMainWindow):
    def __init__(self, aprxPath, filteredFolder, geocodedFolder, bufferFolder):
        super().__init__()

        # Store important paths
        self.aprxPath = aprxPath
        self.filteredFolder = filteredFolder
        self.geocodedFolder = geocodedFolder
        self.bufferFolder = bufferFolder

        # Set up UI
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        # Connect tool buttons to file browsers
        self.ui.shortTermRentalDBTB.clicked.connect(self.browseStrCsv)
        self.ui.agendaItemsTB.clicked.connect(self.browseAgendaCsv)
        self.ui.reportTemplateTB.clicked.connect(self.browseReportCsv)

        # Connect Run button
        self.ui.RunPB.clicked.connect(self.runAll)

    def browseStrCsv(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select STR Database CSV", "", "CSV Files (*.csv)"
        )
        if path:
            self.ui.shortTermRentalDBLE.setText(path)

    def browseAgendaCsv(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Agenda Items CSV", "", "CSV Files (*.csv)"
        )
        if path:
            self.ui.agendaItemsLE.setText(path)

    def browseReportCsv(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Report Template CSV", "", "CSV Files (*.csv)"
        )
        if path:
            self.ui.reportTemplateLE.setText(path)

    # -----------------------------
    # Getter methods
    # -----------------------------
    def strCsv(self):
        return self.ui.shortTermRentalDBLE.text()

    def agendaCsv(self):
        return self.ui.agendaItemsLE.text()

    def reportCsv(self):
        return self.ui.reportTemplateLE.text()

    # -----------------------------
    # Run all processing steps
    # -----------------------------
    def runAll(self):
        # 1. STR Database geocode
        geoTool = GeocodeStrDatabase(
            self.strCsv(),
            self.filteredFolder,
            self.geocodedFolder,
            self.aprxPath
        )
        geoTool.run()

        # 2. Buffers for agenda items
        bufferTool = BufferGenerator(
            self.agendaCsv(),
            self.bufferFolder,
            self.aprxPath
        )
        bufferTool.run()

        # 3. Select + report
        reportTool = ReportGenerator(
            self.bufferFolder,
            self.reportCsv(),
            self.aprxPath
        )
        reportTool.run()


def main():
    app = QApplication([])

    # You can hardcode or later move to config
    aprxPath = r"C:\Path\To\YourProject.aprx"
    filteredFolder = r"C:\Path\To\str_database_filtered"
    geocodedFolder = r"C:\Path\To\str_database_Maplayers"
    bufferFolder = r"C:\Path\To\buffer_folder"

    window = MainWindow(aprxPath, filteredFolder, geocodedFolder, bufferFolder)
    window.show()

    app.exec()


if __name__ == "__main__":
    main()