import numpy as np
import math
import vigra

from lazyflow.graph import Operator, InputSlot, OutputSlot
from lazyflow.stype import Opaque
from lazyflow.rtype import SubRegion, List
from lazyflow.operators import OpArrayCache
from lazyflow.roi import roiToSlice
from ilastik.applets.objectExtraction.opObjectExtraction import OpObjectExtraction    ,\
    default_features_key, OpAdaptTimeListRoi
from ilastik.applets.trackingFeatureExtraction import config
from ilastik.applets.trackingFeatureExtraction.trackingFeatures import FeatureManager

import logging
import collections
from ilastik.applets.base.applet import DatasetConstraintError
logger = logging.getLogger(__name__)




class OpDivisionFeatures(Operator):
    """Computes division features on a 5D volume."""    
    LabelVolume = InputSlot()
    DivisionFeatureNames = InputSlot(rtype=List, stype=Opaque)
    RegionFeaturesVigra = InputSlot()
    
    BlockwiseDivisionFeatures = OutputSlot()
        
    def __init__(self, *args, **kwargs):
        super(OpDivisionFeatures, self).__init__(*args, **kwargs)
                
    def setupOutputs(self):
        taggedShape = self.LabelVolume.meta.getTaggedShape()        

        if set(taggedShape.keys()) != set('txyzc'):
            raise Exception("Input volumes must have txyzc axes.")

        self.BlockwiseDivisionFeatures.meta.shape = tuple([taggedShape['t']])
        self.BlockwiseDivisionFeatures.meta.axistags = vigra.defaultAxistags("t")
        self.BlockwiseDivisionFeatures.meta.dtype = object        
        
        ndim = 3
        if np.any(list(taggedShape.get(k, 0) == 1 for k in "xyz")):
            ndim = 2
            
        self.featureManager = FeatureManager(scales=config.image_scale, n_best=config.n_best_successors, com_name_cur=config.com_name_cur,
                    com_name_next=config.com_name_next, size_name=config.size_name, delim=config.delim, template_size=config.template_size, 
                    ndim=ndim, size_filter=config.size_filter,squared_distance_default=config.squared_distance_default)


    def execute(self, slot, subindex, roi, result):
        assert len(roi.start) == len(roi.stop) == len(self.BlockwiseDivisionFeatures.meta.shape)
        assert slot == self.BlockwiseDivisionFeatures
        taggedShape = self.LabelVolume.meta.getTaggedShape()
        timeIndex = taggedShape.keys().index('t')
        
        import time
        start = time.time()
        
        vroi_start = len(self.LabelVolume.meta.shape) * [0,]
        vroi_stop = list(self.LabelVolume.meta.shape)
        
        assert len(roi.start) == 1
        froi_start = roi.start[0]
        froi_stop = roi.stop[0]
        vroi_stop[timeIndex] = roi.stop[0]
        
        assert timeIndex == 0
        vroi_start[timeIndex] = roi.start[0]
        if roi.stop[0] + 1 < self.LabelVolume.meta.shape[timeIndex]:
            vroi_stop[timeIndex] = roi.stop[0]+1
            froi_stop = roi.stop[0]+1
        vroi = [slice(vroi_start[i],vroi_stop[i]) for i in range(len(vroi_start))]
        
        feats = self.RegionFeaturesVigra[slice(froi_start, froi_stop)].wait()
        labelVolume = self.LabelVolume[vroi].wait()
        divisionFeatNames = self.DivisionFeatureNames[()].wait()[config.features_division_name] 
        
        for t in range(roi.stop[0]-roi.start[0]):
            result[t] = {}
            feats_cur = feats[t][config.features_vigra_name]
            if t+1 < froi_stop-froi_start:                
                feats_next = feats[t+1][config.features_vigra_name]
                                
                img_next = labelVolume[t+1,...]
            else:
                feats_next = None
                img_next = None
            res = self.featureManager.computeFeatures_at(feats_cur, feats_next, img_next, divisionFeatNames)
            result[t][config.features_division_name] = res 
        
        stop = time.time()
        logger.info("TIMING: computing division features took {:.3f}s".format(stop-start))
        return result
    
    
    def propagateDirty(self, slot, subindex, roi):
        if slot is self.DivisionFeatureNames:
            self.BlockwiseDivisionFeatures.setDirty(slice(None))
        elif slot is self.RegionFeaturesVigra:
            self.BlockwiseDivisionFeatures.setDirty(roi)
        else:
            axes = self.LabelVolume.meta.getTaggedShape().keys()
            dirtyStart = collections.OrderedDict(zip(axes, roi.start))
            dirtyStop = collections.OrderedDict(zip(axes, roi.stop))

            # Remove the spatial and channel dims (keep t, if present)
            del dirtyStart['x']
            del dirtyStart['y']
            del dirtyStart['z']
            del dirtyStart['c']

            del dirtyStop['x']
            del dirtyStop['y']
            del dirtyStop['z']
            del dirtyStop['c']

            self.BlockwiseDivisionFeatures.setDirty(dirtyStart.values(), dirtyStop.values())
    
    
class OpTrackingFeatureExtraction(Operator):
    name = "Tracking Feature Extraction"

    TranslationVectors = InputSlot(optional=True)
    RawImage = InputSlot()
    BinaryImage = InputSlot()

    # which features to compute.
    # nested dictionary with format:
    # dict[plugin_name][feature_name][parameter_name] = parameter_value
    # for example {"Standard Object Features": {"Mean in neighborhood":{"margin": (5, 5, 2)}}}
    FeatureNamesVigra = InputSlot(rtype=List, stype=Opaque, value={})
    
    FeatureNamesDivision = InputSlot(rtype=List, stype=Opaque, value={})
        

    LabelImage = OutputSlot()
    ObjectCenterImage = OutputSlot()
 
    # the computed features.
    # nested dictionary with format:
    # dict[plugin_name][feature_name] = feature_value
    RegionFeaturesVigra = OutputSlot(stype=Opaque, rtype=List)    
    RegionFeaturesDivision = OutputSlot(stype=Opaque, rtype=List)
    RegionFeaturesAll = OutputSlot(stype=Opaque, rtype=List)
    
    ComputedFeatureNamesAll = OutputSlot(rtype=List, stype=Opaque)
    ComputedFeatureNamesNoDivisions = OutputSlot(rtype=List, stype=Opaque)

    BlockwiseRegionFeaturesVigra = OutputSlot() # For compatibility with tracking workflow, the RegionFeatures output
                                                # has rtype=List, indexed by t.
                                                # For other workflows, output has rtype=ArrayLike, indexed by (t)
    BlockwiseRegionFeaturesDivision = OutputSlot() 
    
    LabelInputHdf5 = InputSlot(optional=True)
    LabelOutputHdf5 = OutputSlot()
    CleanLabelBlocks = OutputSlot()

    RegionFeaturesCacheInputVigra = InputSlot(optional=True)
    RegionFeaturesCleanBlocksVigra = OutputSlot()
    
    RegionFeaturesCacheInputDivision = InputSlot(optional=True)
    RegionFeaturesCleanBlocksDivision = OutputSlot()
    
        
    def __init__(self, parent):
        super(OpTrackingFeatureExtraction, self).__init__(parent)
        
        # internal operators
        self._objectExtraction = OpObjectExtraction(parent=self)
                
        self._opDivFeats = OpCachedDivisionFeatures(parent=self)
        self._opDivFeatsAdaptOutput = OpAdaptTimeListRoi(parent=self)        

        # connect internal operators
        self._objectExtraction.RawImage.connect(self.RawImage)
        self._objectExtraction.BinaryImage.connect(self.BinaryImage)
        
        self._objectExtraction.Features.connect(self.FeatureNamesVigra)
        self._objectExtraction.LabelInputHdf5.connect(self.LabelInputHdf5)
        self._objectExtraction.RegionFeaturesCacheInput.connect(self.RegionFeaturesCacheInputVigra)
        self.LabelOutputHdf5.connect(self._objectExtraction.LabelOutputHdf5)
        self.CleanLabelBlocks.connect(self._objectExtraction.CleanLabelBlocks)
        self.RegionFeaturesCleanBlocksVigra.connect(self._objectExtraction.RegionFeaturesCleanBlocks)
        self.ObjectCenterImage.connect(self._objectExtraction.ObjectCenterImage)
        self.LabelImage.connect(self._objectExtraction.LabelImage)
        self.BlockwiseRegionFeaturesVigra.connect(self._objectExtraction.BlockwiseRegionFeatures)     
        self.RegionFeaturesVigra.connect(self._objectExtraction.RegionFeatures)    
                
        self._opDivFeats.LabelImage.connect(self.LabelImage)
        self._opDivFeats.DivisionFeatureNames.connect(self.FeatureNamesDivision)
        self._opDivFeats.CacheInput.connect(self.RegionFeaturesCacheInputDivision)
        self._opDivFeats.RegionFeaturesVigra.connect(self._objectExtraction.BlockwiseRegionFeatures)
        self.RegionFeaturesCleanBlocksDivision.connect(self._opDivFeats.CleanBlocks)        
        self.BlockwiseRegionFeaturesDivision.connect(self._opDivFeats.Output)
        
        self._opDivFeatsAdaptOutput.Input.connect(self._opDivFeats.Output)
        self.RegionFeaturesDivision.connect(self._opDivFeatsAdaptOutput.Output)
        
        # As soon as input data is available, check its constraints
        self.RawImage.notifyReady( self._checkConstraints )
        self.BinaryImage.notifyReady( self._checkConstraints )
    
               
    def setupOutputs(self, *args, **kwargs):
        self.ComputedFeatureNamesAll.meta.assignFrom(self.FeatureNamesVigra.meta)
        self.ComputedFeatureNamesNoDivisions.meta.assignFrom(self.FeatureNamesVigra.meta)
        self.RegionFeaturesAll.meta.assignFrom(self.RegionFeaturesVigra.meta)
        
    def execute(self, slot, subindex, roi, result):
        if slot == self.ComputedFeatureNamesAll:
            feat_names_vigra = self.FeatureNamesVigra([]).wait()
            feat_names_div = self.FeatureNamesDivision([]).wait()        
            for plugin_name in feat_names_vigra.keys():
                assert plugin_name not in feat_names_div, "feature name dictionaries must be mutually exclusive"
            for plugin_name in feat_names_div.keys():
                assert plugin_name not in feat_names_vigra, "feature name dictionaries must be mutually exclusive"
            result = dict(feat_names_vigra.items() + feat_names_div.items())

            return result
        elif slot == self.ComputedFeatureNamesNoDivisions:
            feat_names_vigra = self.FeatureNamesVigra([]).wait()
            result = dict(feat_names_vigra.items())

            return result
        elif slot == self.RegionFeaturesAll:
            feat_vigra = self.RegionFeaturesVigra(roi).wait()
            feat_div = self.RegionFeaturesDivision(roi).wait()
            assert np.all(feat_vigra.keys() == feat_div.keys())
            result = {}        
            for t in feat_vigra.keys():
                for plugin_name in feat_vigra[t].keys():
                    assert plugin_name not in feat_div[t], "feature dictionaries must be mutually exclusive"
                for plugin_name in feat_div[t].keys():
                    assert plugin_name not in feat_vigra[t], "feature dictionaries must be mutually exclusive"                    
                result[t] = dict(feat_div[t].items() + feat_vigra[t].items())            
            return result
        else:
            assert False, "Shouldn't get here."

    def propagateDirty(self, slot, subindex, roi):
        if slot == self.FeatureNamesVigra or slot == self.FeatureNamesDivision:
            self.ComputedFeatureNamesAll.setDirty(roi)
            self.ComputedFeatureNamesNoDivisions.setDirty(roi)

    def setInSlot(self, slot, subindex, roi, value):
        assert slot == self.LabelInputHdf5 or slot == self.RegionFeaturesCacheInputVigra or \
            slot == self.RegionFeaturesCacheInputDivision, "Invalid slot for setInSlot(): {}".format(slot.name)
           
    def _checkConstraints(self, *args):
        if self.RawImage.ready():
            rawTaggedShape = self.RawImage.meta.getTaggedShape()
            if 't' not in rawTaggedShape or rawTaggedShape['t'] < 2:
                msg = "Raw image must have a time dimension with at least 2 images.\n"\
                    "Your dataset has shape: {}".format(self.RawImage.meta.shape)
                    
        if self.BinaryImage.ready():
            rawTaggedShape = self.BinaryImage.meta.getTaggedShape()
            if 't' not in rawTaggedShape or rawTaggedShape['t'] < 2:
                msg = "Binary image must have a time dimension with at least 2 images.\n"\
                    "Your dataset has shape: {}".format(self.BinaryImage.meta.shape)
                    
        if self.RawImage.ready() and self.BinaryImage.ready():
            rawTaggedShape = self.RawImage.meta.getTaggedShape()
            binTaggedShape = self.BinaryImage.meta.getTaggedShape()
            rawTaggedShape['c'] = None
            binTaggedShape['c'] = None
            if dict(rawTaggedShape) != dict(binTaggedShape):
                logger.info("Raw data and other data must have equal dimensions (different channels are okay).\n"\
                      "Your datasets have shapes: {} and {}".format( self.RawImage.meta.shape, self.BinaryImage.meta.shape ))
                
                msg = "Raw data and other data must have equal dimensions (different channels are okay).\n"\
                      "Your datasets have shapes: {} and {}".format( self.RawImage.meta.shape, self.BinaryImage.meta.shape )
                raise DatasetConstraintError( "Object Extraction", msg ) 


class OpCachedDivisionFeatures(Operator):
    """Caches the division features computed by OpDivisionFeatures."""    
    LabelImage = InputSlot()
    CacheInput = InputSlot(optional=True)
    DivisionFeatureNames = InputSlot(rtype=List, stype=Opaque)
    RegionFeaturesVigra = InputSlot()

    Output = OutputSlot()
    CleanBlocks = OutputSlot()

    def __init__(self, *args, **kwargs):
        super(OpCachedDivisionFeatures, self).__init__(*args, **kwargs)

        # Hook up the labeler
        self._opDivisionFeatures = OpDivisionFeatures(parent=self)        
        self._opDivisionFeatures.LabelVolume.connect(self.LabelImage)
        self._opDivisionFeatures.DivisionFeatureNames.connect(self.DivisionFeatureNames)
        self._opDivisionFeatures.RegionFeaturesVigra.connect(self.RegionFeaturesVigra)

        # Hook up the cache.
        self._opCache = OpArrayCache(parent=self)
        self._opCache.name = "OpCachedDivisionFeatures._opCache"
        self._opCache.Input.connect(self._opDivisionFeatures.BlockwiseDivisionFeatures)

        # Hook up our output slots
        self.Output.connect(self._opCache.Output)
        self.CleanBlocks.connect(self._opCache.CleanBlocks)

    def setupOutputs(self):        
        taggedOutputShape = self.LabelImage.meta.getTaggedShape()        

        if 't' not in taggedOutputShape.keys() or taggedOutputShape['t'] < 2:
            raise DatasetConstraintError( "Tracking Feature Extraction",
                                          "Label Image must have a time axis with more than 1 image.\n"\
                                          "Label Image shape: {}"\
                                          "".format(self.LabelImage.meta.shape))

        
        # Every value in the region features output is cached separately as it's own "block"
        blockshape = (1,) * len(self._opDivisionFeatures.BlockwiseDivisionFeatures.meta.shape)
        self._opCache.blockShape.setValue(blockshape)

    def setInSlot(self, slot, subindex, roi, value):
        assert slot == self.CacheInput
        slicing = roiToSlice(roi.start, roi.stop)
        self._opCache.Input[ slicing ] = value

    def execute(self, slot, subindex, roi, destination):
        assert False, "Shouldn't get here."

    def propagateDirty(self, slot, subindex, roi):
        pass # Nothing to do...

    