from crossValidation import make_folds, train_and_predict
from lazyflow.graph import Operator, InputSlot, OutputSlot
from ilastik.utility import OperatorSubView, MultiLaneOperatorABC

import logging
logger = logging.getLogger(__name__)

class OpCrossValidation(Operator, MultiLaneOperatorABC):
    name = "OpCrossValidation"
    category = "Top-level"

    PatchFeatures = InputSlot(level=1)
    PatchLabels = InputSlot(level=1)
    NFolds = InputSlot(stype='int')

    Classifiers = OutputSlot()
    Predictions = OutputSlot(level=1)

    def __init__(self, *args, **kwargs):
        super(OpCrossValidation, self).__init__(*args, **kwargs)


    def setupOutputs(self):
        super(OpCrossValidation, self).setupOutputs()

        self.Classifiers.meta.shape = (self.NFolds.value,)

        n = len(self.PatchFeatures)
        self.Predictions.resize(n)

        for i in range(len(self.Predictions)):
            self.Predictions[i].meta.shape = (self.PatchLabels[i].meta.shape[0], 2)


    def execute(self, slot, subindex, roi, result):
        samples = []
        labels = []

        for i in range(len(self.PatchFeatures)):
            samples.append(self.PatchFeatures[i][:].wait())
            labels.append(self.PatchLabels[i][:].wait())

        n_folds = self.NFolds.value

        # FIXME: defect and non-defect images
        folds = list(make_folds([0] * len(samples), n_folds))

        # FIXME: cache output
        classifiers, predictions = train_and_predict(samples, labels, folds)

        # FIXME: predict lazily

        if slot is self.Classifiers:
            return classifiers

        if slot is self.Predictions:
            return predictions[subindex[0]]


    def propagateDirty(self, slot, subindex, roi):
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
