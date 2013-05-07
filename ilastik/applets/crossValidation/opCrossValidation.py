from crossValidation import make_folds, train_and_predict
from lazyflow.graph import Operator, InputSlot, OutputSlot
from ilastik.utility import OperatorSubView, MultiLaneOperatorABC
from lazyflow.request import RequestLock

import logging
logger = logging.getLogger(__name__)

class OpCrossValidation(Operator, MultiLaneOperatorABC):
    name = "OpCrossValidation"
    category = "Top-level"

    PatchFeatures = InputSlot(level=1)
    PatchLabels = InputSlot(level=1)
    NFolds = InputSlot(stype='int')
    NLabels = InputSlot(stype='int')

    Classifiers = OutputSlot()
    Predictions = OutputSlot(level=1)

    def __init__(self, *args, **kwargs):
        super(OpCrossValidation, self).__init__(*args, **kwargs)
        self.resetCaches()
        self.lock = RequestLock()


    def setupOutputs(self):
        super(OpCrossValidation, self).setupOutputs()

        self.Classifiers.meta.shape = (self.NFolds.value,)

        n = len(self.PatchFeatures)
        n_labels = self.NLabels.value

        self.Predictions.resize(n)
        for i in range(len(self.Predictions)):
            self.Predictions[i].meta.shape = (self.PatchLabels[i].meta.shape[0],
                                              n_labels)


    def execute(self, slot, subindex, roi, result):
        self.lock.acquire()
        if not self.computed:
            samples = []
            labels = []

            for i in range(len(self.PatchFeatures)):
                samples.append(self.PatchFeatures[i][:].wait())
                labels.append(self.PatchLabels[i][:].wait())

            # FIXME: defect and non-defect images
            folds = list(make_folds([0] * len(samples), self.NFolds.value))

            self.classifiers, self.predictions = train_and_predict(samples, labels, folds)
            self.computed = True

        self.lock.release()

        if slot is self.Classifiers:
            return self.classifiers

        if slot is self.Predictions:
            return self.predictions[subindex[0]]


    def resetCaches(self):
        self.computed = False
        self.classifiers = None
        self.predictions = None


    def propagateDirty(self, slot, subindex, roi):
        self.resetCaches()
        for i in range(len(self.Classifiers)):
            self.Classifiers[i].setDirty(slice(None))
        for i in range(len(self.Predictions)):
            self.Predictions.setDirty(slice(None))


    def addLane(self, laneIndex):
        numLanes = len(self.PatchFeatures)
        assert numLanes == laneIndex, "Image lanes must be appended."
        for slot in self.inputs.values():
            if slot.level > 0 and len(slot) == laneIndex:
                slot.resize(numLanes + 1)


    def removeLane(self, laneIndex, finalLength):
        for slot in self.inputs.values():
            if slot.level > 0 and len(slot) == finalLength + 1:
                slot.removeSlot(laneIndex, finalLength)


    def getLane(self, laneIndex):
        return OperatorSubView(self, laneIndex)
