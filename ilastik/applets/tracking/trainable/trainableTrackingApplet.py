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
