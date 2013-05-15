from lazyflow.graph import Graph

from ilastik.workflow import Workflow
from ilastik.applets.tracking.manual.manualTrackingApplet import ManualTrackingApplet
from ilastik.applets.tracking.trainable.trainableTrackingApplet import TrainableTrackingApplet
from ilastik.applets.objectExtraction.objectExtractionApplet import ObjectExtractionApplet

class TrainableTrackingWorkflow( Workflow ):
    workflowName = "Tracking Workflow (trainable)"

    @property
    def applets(self):
        return self._applets
    
    @property
    def imageNameListSlot(self):
        return self.dataSelectionApplet.topLevelOperator.ImageName

    def __init__( self, *args, **kwargs ):
        graph = kwargs['graph'] if 'graph' in kwargs else Graph()
        if 'graph' in kwargs: del kwargs['graph']
        super(TrainableTrackingWorkflow, self).__init__(graph=graph, *args, **kwargs)
        
    def connectLane( self, laneIndex ):
        self._manual_wf.connectLane( laneIndex )
