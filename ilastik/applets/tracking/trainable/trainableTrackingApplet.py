from ilastik.applets.base.standardApplet import StandardApplet
from ilastik.applets.tracking.trainable.opTrainableTracking import OpTrainableTracking
from ilastik.applets.tracking.trainable.trainableTrackingGui import TrainableTrackingGui
from ilastik.applets.tracking.base.trackingSerializer import TrackingSerializer

class TrainableTrackingApplet( StandardApplet ):
    def __init__( self, name="Tracking", workflow=None, projectFileGroupName="TrainableTracking" ):
        super(TrainableTrackingApplet, self).__init__( name=name, workflow=workflow )
        self._serializableItems = [ TrackingSerializer(self.topLevelOperator, projectFileGroupName) ]

    @property
    def singleLaneOperatorClass( self ):
        return OpTrainableTracking

    @property
    def broadcastingSlots( self ):
        return []

    @property
    def singleLaneGuiClass( self ):
        return TrainableTrackingGui

    @property
    def dataSerializers(self):
        return self._serializableItems

if __name__ == "__main__":
    from PyQt4.QtGui import QApplication

    #make the program quit on Ctrl+C
    import signal
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    from ilastik.workflow import Workflow
    from ilastik.shell.projectManager import ProjectManager
    from lazyflow.operator import Operator
    from lazyflow.slot import OutputSlot, InputSlot
    from lazyflow.graph import Graph

    class ImageNameOperator( Operator ):
        Output = OutputSlot( level=1 )

        def setupOutputs( self ):
            self.Output.setValue("Dummy Name")

        def execute( self, *args, **kwargs ):
            pass

    class DummyWorkflow( Workflow ):
        @property
        def applets( self ):
            return self._applets

        @property
        def imageNameListSlot( self ):
            return self._opImageName.Output


        def __init__(self, headless=False, workflow_cmdline_args=(), parent=None, graph=None):
            super(DummyWorkflow, self).__init__(headless, workflow_cmdline_args, parent, graph)
            self._applets = [ TrainableTrackingApplet( workflow=self ) ]
            self._opImageName = ImageNameOperator( parent = self )

        def connectLane( self, laneIndex ):
            pass

        def onProjectLoaded( self, projectManager ):
            self._opImageName.Output.resize(1)

if __name__=="__main__":            
    def createNewProject(shell):
        shell.createAndLoadNewProject("tmp.ilp", DummyWorkflow, h5_file_kwargs={'driver': 'core', 'backing_store': False})
    init_funcs = [createNewProject]

    from ilastik.shell.gui.startShellGui import startShellGui
    import sys
    sys.exit(startShellGui({}, False, *init_funcs))
    
