# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# Copyright 2011-2014, the ilastik developers


# basic python modules
import functools
import logging
logger = logging.getLogger(__name__)
from threading import Lock as ThreadLock

# required numerical modules
import numpy as np
import vigra
import opengm

# basic lazyflow types
from lazyflow.operator import Operator
from lazyflow.slot import InputSlot, OutputSlot
from lazyflow.rtype import SubRegion
from lazyflow.stype import Opaque
from lazyflow.request import Request, RequestPool

# required lazyflow operators
from lazyflow.operators.opLabelVolume import OpLabelVolume
from lazyflow.operators.valueProviders import OpArrayCache
from lazyflow.operators.opCompressedCache import OpCompressedCache
from lazyflow.operators.opReorderAxes import OpReorderAxes

from _OpGraphCut import segmentGC_fast, OpGraphCut


## segment predictions with pre-thresholding
#
# This operator segments an image into foreground and background and makes use
# of a preceding thresholding step. The connected components in the label image
# are taken as single objects, and their bounding boxes are fed into the graph-
# cut segmentation algorithm (see _OpGraphCut.OpGraphCut).
#
# The operator inherits from OpGraphCut because they share some details:
#   * output meta
#   * dirtiness propagation
#   * input slots
#   * multithreading approach
#
class OpObjectsSegment(OpGraphCut):
    name = "OpObjectsSegment"

    # thresholded predictions, or otherwise obtained ROI indicators
    # (a value of 0 is assumed to be background and ignored)
    LabelImage = InputSlot()

    # margin around each object (always xyz!)
    Margin = InputSlot(value=np.asarray((20, 20, 20)))

    # bounding boxes of the labeled objects
    # this slot returns an array of dicts with shape (t, c)
    BoundingBoxes = OutputSlot()

    ### slots from OpGraphCut ###

    ## prediction maps
    #Prediction = InputSlot()

    ## graph cut parameter
    #Beta = InputSlot(value=.2)

    ## segmentation image -> graph cut segmentation
    #Output = OutputSlot()
    #CachedOutput = OutputSlot()

    ## for internal use
    #_FakeSlot = OutputSlot()

    def __init__(self, *args, **kwargs):
        super(OpObjectsSegment, self).__init__(*args, **kwargs)

    def setupOutputs(self):
        super(OpObjectsSegment, self).setupOutputs()
        # sanity checks
        shape = self.LabelImage.meta.shape
        assert all([i == j for i, j in zip(self.Prediction.meta.shape, shape)]),\
            "shape mismatch: {} vs. {}".format(self.Prediction.meta.shape, shape)
        if len(shape) < 5:
            raise ValueError("Prediction maps must be a full 5d volume (txyzc)")
        tags = self.LabelImage.meta.getAxisKeys()
        tags = "".join(tags)
        haveAxes =  tags == 'txyzc'
        if not haveAxes:
            raise ValueError("Label image has wrong axes order"
                             "(expected: txyzc, got: {})".format(tags))

        # bounding boxes are just one element arrays of type object
        shape = self.Prediction.meta.shape
        self.BoundingBoxes.meta.shape = (shape[0], shape[4])
        self.BoundingBoxes.meta.dtype = np.object
        self.BoundingBoxes.meta.axistags = vigra.defaultAxistags('tc')

    def execute(self, slot, subindex, roi, result):

        if slot == self.BoundingBoxes:
            self._execute_bbox(roi, result)
        elif slot == self.Output:
            self._execute_graphcut(roi, result)
        else:
            raise NotImplementedError(
                "execute() is not implemented for slot {}".format(str(slot)))

    def _execute_bbox(self, roi, result):
        logger.debug("computing bboxes...")

        def getBoundingBoxForSlice(t, c):
            cc = self.LabelImage[t, ..., c].wait()
            cc = vigra.taggedView(cc, axistags=self.LabelImage.meta.axistags)
            cc = cc.withAxes(*'xyz')

            feats = vigra.analysis.extractRegionFeatures(
                cc.astype(np.float32),
                cc.astype(np.uint32),
                features=["Count", "Coord<Minimum>", "Coord<Maximum>"])
            feats_dict = {}
            feats_dict["Coord<Minimum>"] = feats["Coord<Minimum>"]
            feats_dict["Coord<Maximum>"] = feats["Coord<Maximum>"]
            feats_dict["Count"] = feats["Count"]
            return feats_dict

        # we already do the objects in parallel, so sequential computation here
        print(roi)
        for ti, t in enumerate(range(roi.start[0], roi.stop[0])):
            for ci, c in enumerate(range(roi.start[1], roi.stop[1])):
                result[ti, ci] = getBoundingBoxForSlice(t, c)

    def _execute_graphcut(self, roi, result):
        # we already do the objects in parallel, so sequential computation here
        for t in range(roi.start[0], roi.stop[0]):
            for c in range(roi.start[4], roi.stop[4]):
                with self._lock[t, c]:
                    self._runGraphCutForSlice(t, c)
        req = self._cache.Output.get(roi)
        req.writeInto(result)
        req.block()

    ## run graph cut algorithm on a single c-t-slice
    # assumes that it has exclusive access (i.e. use with lock)
    def _runGraphCutForSlice(self, t, c):

        # check whether cache is filled or not
        if not self._need[t, c]:
            return

        margin = self.Margin.value
        beta = self.Beta.value
        MAXBOXSIZE = 10000000  # FIXME justification??

        ## request the bounding box coordinates ##
        # the trailing index brackets give us the dictionary (instead of an
        # array of size 1)
        feats = self.BoundingBoxes[t, c].wait()[0, 0]
        mins = feats["Coord<Minimum>"]
        maxs = feats["Coord<Maximum>"]
        nobj = mins.shape[0]
        # these are indices, so they should have an index datatype
        mins = mins.astype(np.uint32)
        maxs = maxs.astype(np.uint32)

        stop = np.asarray(self.Prediction.meta.shape, dtype=np.int)
        start = stop * 0
        start[0] = t
        start[4] = c
        stop[0] = t+1
        stop[4] = c+1
        start = tuple(start)
        stop = tuple(stop)
        ## request the prediction image ##
        predRoi = SubRegion(self.Prediction,
                            start=start, stop=stop)
        pred = self.Prediction.get(predRoi).wait()
        pred = vigra.taggedView(pred, axistags=self.Prediction.meta.axistags)
        pred = pred.withAxes(*'xyz')

        ## request the connected components image ##
        ccRoi = SubRegion(self.LabelImage,
                        start=start, stop=stop)
        cc = self.LabelImage.get(ccRoi).wait()
        cc = vigra.taggedView(cc, axistags=self.LabelImage.meta.axistags)
        cc = cc.withAxes(*'xyz')

        # provide xyz view for the output
        resultXYZ = vigra.taggedView(np.zeros(cc.shape, dtype=np.uint8),
                                     axistags='xyz')

        #FIXME what do we do if the objects' bboxes overlap?
        def processSingleObject(i):
            logger.debug("processing object {}".format(i))
            # maxs are inclusive, so we need to add 1
            xmin = max(mins[i][0]-margin[0], 0)
            ymin = max(mins[i][1]-margin[1], 0)
            zmin = max(mins[i][2]-margin[2], 0)
            xmax = min(maxs[i][0]+margin[0]+1, cc.shape[0])
            ymax = min(maxs[i][1]+margin[1]+1, cc.shape[1])
            zmax = min(maxs[i][2]+margin[2]+1, cc.shape[2])
            ccbox = cc[xmin:xmax, ymin:ymax, zmin:zmax]
            resbox = resultXYZ[xmin:xmax, ymin:ymax, zmin:zmax]

            nVoxels = ccbox.size
            if nVoxels > MAXBOXSIZE:
                #problem too large to run graph cut, assign to seed
                logger.warn("Object {} too large for graph cut.".format(i))
                resbox[ccbox == i] = 1
                return

            probbox = pred[xmin:xmax, ymin:ymax, zmin:zmax]
            gcsegm = segmentGC_fast(probbox, beta)
            gcsegm = vigra.taggedView(gcsegm, axistags='xyz')
            ccsegm = vigra.analysis.labelVolumeWithBackground(
                gcsegm.astype(np.uint8))

            #TODO @akreshuk document what this part is doing
            seed = ccbox == i
            filtered = seed*ccsegm
            passed = np.unique(filtered)
            assert len(passed.shape) == 1
            if passed.size > 2:
                logger.warn("ambiguous label assignment for region {}".format(
                    (xmin, xmax, ymin, ymax, zmin, zmax)))
                resbox[ccbox == i] = 1
            elif passed.size <= 1:
                logger.warn(
                    "box {} segmented out with beta {}".format(i, beta))
            else:
                # assign to the overlap region
                label = passed[1]  # 0 is background
                resbox[ccsegm == label] = 1

        pool = RequestPool()
        #FIXME make sure that the parallel computations fit into memory
        for i in range(1, nobj):
            req = Request(functools.partial(processSingleObject, i))
            pool.add(req)

        logger.info("Processing {} objects ...".format(nobj-1))

        pool.wait()
        pool.clean()

        logger.info("object loop done")

        # convert from label image to segmentation
        resultXYZ[resultXYZ > 0] = 1

        # write to cache
        cacheRoi = SubRegion(self._cache.Input,
                            start=start, stop=stop)
        self._cache.setInSlot(self._cache.Input, (), cacheRoi,
                            resultXYZ.withAxes(*'txyzc'))
        self._need[t, c] = False

    def propagateDirty(self, slot, subindex, roi):
        super(OpObjectsSegment, self).propagateDirty(slot, subindex, roi)

        if slot == self.LabelImage:
            # time-channel slices are pairwise independent

            # determine t, c from input volume
            t_ind = 0
            c_ind = 4
            t = (roi.start[t_ind], roi.stop[t_ind])
            c = (roi.start[c_ind], roi.stop[c_ind])

            # schedule slices for recomputation
            #FIXME do we need a lock here?
            self._need[t[0]:t[1], c[0]:c[1]] = True

            # set output dirty
            start = t[0:1] + (0,)*3 + c[0:1]
            stop = t[1:2] + self.Output.meta.shape[1:4] + c[1:2]
            roi = SubRegion(self.Output, start=start, stop=stop)
            self.Output.setDirty(roi)
        elif slot == self.Margin:
            # margin affects the whole volume
            self.Output.setDirty(slice(None))