from lazyflow.graph import Operator, InputSlot, OutputSlot
from lazyflow.rtype import List
from lazyflow.stype import Opaque
from ilastik.applets.tracking.base.opTrackingBase import OpTrackingBase

class OpTrainableTracking(OpTrackingBase): 
    Tracks = InputSlot( stype=Opaque, rtype=List )
    Divisions = InputSlot( stype=Opaque, rtype=List )
    
    def setupOutputs(self):
        pass

    def execute(self, slot, subindex, roi, result):
        pass

    def propagateDirty(self, slot, subindex, roi):
        pass
