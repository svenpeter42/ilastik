import unittest

import numpy as np

from ilastik.applets.crossValidation.opCrossValidation \
    import OpCrossValidation

from lazyflow.graph import Graph

import vigra

class IntegrationTest(unittest.TestCase):
    def setUp(self):
        g = Graph()
        self.op = OpCrossValidation(graph=g)

    def testOperator(self):
        feats = np.arange(40).reshape(10, 4)
        labels = np.array([0, 0, 0, 0, 0, 1, 1, 1, 1, 1])

        n_folds = 2

        self.op.addLane(0)
        self.op.addLane(1)

        self.op.NFolds.setValue(n_folds)
        self.op.NLabels.setValue(2)

        self.op.PatchFeatures[0].setValue(feats)
        self.op.PatchLabels[0].setValue(labels)

        self.op.PatchFeatures[1].setValue(feats)
        self.op.PatchLabels[1].setValue(labels)


        classifiers = self.op.Classifiers[:].wait()
        predictions = list(self.op.Predictions[i][:].wait()
                           for i in range(len(self.op.Predictions)))

        self.assertEqual(len(classifiers), 2)
        for c in classifiers:
            self.assertIsInstance(c, vigra.learning.RandomForest)

        self.assertEqual(len(predictions), 2)
        for p in predictions:
            self.assertTrue(p.ndim == 2)
            self.assertTrue(np.all(np.argmax(p, axis=1) == labels))

        # ensure that nothing gets re-calculated
        new_classifiers = self.op.Classifiers[:].wait()
        self.assertIs(new_classifiers, classifiers)


if __name__ == '__main__':
    unittest.main()
