import sys
import arcpy
from PyQt6.QtWidgets import QApplication, QMainWindow, QFileDialog
from PyQt6.QtCore import QObject, pyqtSignal, QThread
from gui_main import Ui_MainWindow
from analysis_functions import GeocodeStrDatabase, BufferGenerator, ReportGenerator

class EmittingStream(QObject):
    """
    This allows print statements and exceptions raised during
    ArcPy execution to be displayed in the GUI log window
    in real time.
    """

    textWritten = pyqtSignal(str)

    def write(self, text):
        """
        Emits written text as a Qt signal.
        """
        if text.strip():
            self.textWritten.emit(str(text))

    def flush(self):
        """
        Required for compatibility with sys.stdout and sys.stderr.
        """
        pass

class Worker(QObject):
    """
    Executes the geocoding, buffering, and reporting workflow
    in a background thread.
    """

    finished = pyqtSignal()
    progress = pyqtSignal(str)

    def __init__(self, strCsv, agendaCsv, reportCsv, aprxPath, folders, mapObj):
        """
        Initializes the worker with all required inputs.
        """
        super().__init__()
        self.strCsv = strCsv
        self.agendaCsv = agendaCsv
        self.reportCsv = reportCsv
        self.aprxPath = aprxPath
        self.filteredFolder = folders["filtered"]
        self.geocodedFolder = folders["geocoded"]
        self.bufferFolder = folders["buffer"]
        self.mapObj = mapObj

    def run(self):
        """
        Executes the full analysis workflow.
        """
        try:
            self.progress.emit("Starting geocode...")
            geoTool = GeocodeStrDatabase(
                self.strCsv,
                self.filteredFolder,
                self.geocodedFolder,
                self.mapObj,
                self.aprxPath
            )
            geoTool.run()
            self.progress.emit("Geocoding complete.")

            self.progress.emit("Creating buffers...")
            bufferTool = BufferGenerator(
                self.agendaCsv,
                self.bufferFolder,
                self.mapObj,
                self.aprxPath
            )
            bufferTool.run()
            self.progress.emit("Buffers created.")

            self.progress.emit("Generating report...")
            reportTool = ReportGenerator(
                self.bufferFolder,
                self.reportCsv,
                self.mapObj,
                self.aprxPath
            )
            reportTool.run()
            self.progress.emit("Report written.")
            self.progress.emit("STR analysis complete.")
        except Exception as e:
            self.progress.emit(f"Error: {str(e)}")

        self.finished.emit()

class MainWindow(QMainWindow):
    """
    Primary GUI window for the Short-Term Rental Analysis Tool.
    """

    def __init__(self):
        """
        Initializes the GUI, connects signals, and sets defaults.
        """
        super().__init__()

        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        self._connectSignals()
        self._configurePaths()
        self._redirectOutput()

    def _connectSignals(self):
        """
        Connects UI buttons to their respective handlers.
        """
        self.ui.shortTermRentalDBTB.clicked.connect(self.browseStrCsv)
        self.ui.agendaItemsTB.clicked.connect(self.browseAgendaCsv)
        self.ui.reportTemplateTB.clicked.connect(self.browseReportCsv)
        self.ui.RunPB.clicked.connect(self.runAll)

    def _configurePaths(self):
        """
        Configures hard-coded project and output paths.
        """
        self.aprxPath = r"C:\PSU\geog489\analysis_tool\analysis_project\analysis_project.aprx"
        self.filteredFolder = r"C:\PSU\geog489\analysis_tool\str_database_filteredcsvs"
        self.geocodedFolder = r"C:\PSU\geog489\analysis_tool\str_database_Maplayers"
        self.bufferFolder = r"C:\PSU\geog489\analysis_tool\buffer_folder"

    def _redirectOutput(self):
        """
        Redirects stdout and stderr to the GUI log window.
        """
        self.stdout_stream = EmittingStream()
        self.stdout_stream.textWritten.connect(self.appendLog)
        sys.stdout = self.stdout_stream
        sys.stderr = self.stdout_stream

    def browseStrCsv(self):
        """
        Opens a file dialog for selecting the STR database CSV.
        """
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select STR CSV",
            r"C:\PSU\geog489\analysis_tool\str_database",
            "CSV (*.csv)"
        )
        if path:
            self.ui.shortTermRentalDBLE.setText(path)

    def browseAgendaCsv(self):
        """
        Opens a file dialog for selecting the agenda items CSV.
        """
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Agenda CSV",
            r"C:\PSU\geog489\analysis_tool\agenda_items",
            "CSV (*.csv)"
        )
        if path:
            self.ui.agendaItemsLE.setText(path)

    def browseReportCsv(self):
        """
        Opens a file dialog for selecting the report CSV.
        """
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Report CSV",
            r"C:\PSU\geog489\analysis_tool\reports",
            "CSV (*.csv)"
        )
        if path:
            self.ui.reportTemplateLE.setText(path)

    def runAll(self):
        """
        Starts the threaded analysis workflow.
        """
        aprx = arcpy.mp.ArcGISProject(self.aprxPath)
        theMap = aprx.listMaps()[0]

        folders = {
            "filtered": self.filteredFolder,
            "geocoded": self.geocodedFolder,
            "buffer": self.bufferFolder
        }

        self.thread = QThread()
        self.worker = Worker(
            self.ui.shortTermRentalDBLE.text(),
            self.ui.agendaItemsLE.text(),
            self.ui.reportTemplateLE.text(),
            self.aprxPath,
            folders,
            theMap
        )

        self.worker.moveToThread(self.thread)

        self.thread.started.connect(self.worker.run)
        self.worker.progress.connect(self.appendLog)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)

        self.ui.RunPB.setEnabled(False)
        self.worker.finished.connect(lambda: self.ui.RunPB.setEnabled(True))

        self.thread.start()

    def appendLog(self, text):
        """
        Appends text to the GUI log window.
        """
        self.ui.logTE.append(text)
        self.ui.logTE.verticalScrollBar().setValue(
            self.ui.logTE.verticalScrollBar().maximum()
        )

def main():
    """
    Launches the PyQt application.
    """
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
