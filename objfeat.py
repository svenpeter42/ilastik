#Python
from collections import defaultdict
import cgi
import sys
import copy
import weakref
from itertools import groupby

#SciPy

import vigra, numpy

#PyQt
from PyQt4.QtGui import *
from PyQt4.QtCore import *

#-----------------------------------------------------------------------------

class PluginInfo(object):
    """Meta Information for a Plugin
    """
    
    def __init__(self, key, name):
        self.key  = key
        self.name = name
        self.about = ""
        
        self.features = []
        
#-----------------------------------------------------------------------------

class ObjectFeatureInfo(object):
    """Meta Information for an Object Feature
    """
    
    def __init__(self, key, humanName, size, group):
        self.key = key
        self.humanName = humanName
        self.group  = group
        self.meaning = None
        self.neighborhoodPossible = False
        
        #a weak reference back to the plugin that provides this feature
        self.plugin = None
        
        #private:
        self._size = size
        
    def size(self, dim, ch):
        """return the size of the feature vector
           this size depends on the dimensionality of the data 'dim'
           and the number of channels 'ch'
        """
        
        if ch == 0:
            ch = 1
        if isinstance(self._size, int):
            return self._size
        if self._size == "coor":
            return 2 if dim == 2 else 3
        if self._size == "coor2":
            return 4 if dim == 2 else 9
        elif self._size == "ch":
            return ch
        elif self._size == "ch2":
            return ch*ch
        else:
            raise RuntimeError("not implemented")

#-----------------------------------------------------------------------------

def getVigraObjectFeatureInfos():
    r = []

    o = ObjectFeatureInfo("Coord<ArgMaxWeight >", "Coordinate of pixel with maximal intensity" ,"coor",   "coordinates")
    o.meaning = "position of the point with maximum intensity"
    r.append(o)

    o = ObjectFeatureInfo("Coord<ArgMinWeight >", "Coordinate of pixel with minimal intensity" ,"coor",   "coordinates")
    o.meaning = "position of the point with minimum intensity"
    r.append(o)

    o = ObjectFeatureInfo("Coord<Maximum >", "Lower right coordinate of bounding box" ,"coor",   "coordinates")
    o.meaning = "upper bound of the regions bounding box"
    r.append(o)

    o = ObjectFeatureInfo("Coord<Minimum >", "Upper left coordinate of bounding box" ,"coor",   "coordinates")  
    o.meaning = "lower bound of the regions bounding box"
    r.append(o)
    
    o = ObjectFeatureInfo("Count", "Pixel count" ,1,   "shape")
    o.meaning = "size of the region (number of pixels)"
    r.append(o)
    
    o = ObjectFeatureInfo("Global<Maximum >", "Maximal intensity (search entire image)", 1, "global")
    o.meaning = "TODO"
    r.append(o)
    
    o = ObjectFeatureInfo("Global<Minimum >", "Minimal intensity (search entire image)", 1, "global")
    o.meaning = "TODO"
    r.append(o)
    
    o = ObjectFeatureInfo("Histogram", "Intensity Histogram",64,   "intensity")
    o.neighborhoodPossible = True
    o.meaning = "TODO"
    r.append(o)
    
    o = ObjectFeatureInfo("Kurtosis", "Kurtosis (4th moment) of intensities", "ch", "intensity")
    o.meaning = "intensity kurtosis (computed per channel)"
    o.neighborhoodPossible = True
    r.append(o)
    
    o = ObjectFeatureInfo("Maximum", "Maximal intensity","ch", "intensity")
    o.meaning = "maximum intensity (computed per channel)"
    o.neighborhoodPossible = True
    r.append(o)
    
    o = ObjectFeatureInfo("Minimum", "Minimal intensity" ,"ch", "intensity")
    o.meaning = "minimum intensity (computed per channel)"
    o.neighborhoodPossible = True
    r.append(o)

    o = ObjectFeatureInfo("Mean", "Mean intensity" ,"ch", "intensity")  
    o.meaning = "mean intensity (computed per channel)"
    o.neighborhoodPossible = True
    r.append(o)
    
    o = ObjectFeatureInfo("Quantiles", "Quantiles (0%, 10%, 25%, 50%, 75%, 90%, 100%) of intensities", 7, "intensity")
    o.meaning = "quantiles of the intensity"
    r.append(o)
    
    o =  ObjectFeatureInfo("RegionAxes", "Eigenvectors from PCA (each pixel has unit mass)", "coor2", "shape",)
    o.meaning = "axes of a local coordinate system aligned to the region"
    r.append(o)
        
    o = ObjectFeatureInfo("RegionCenter", "Center of mass (each pixel has unit mass)", "coor", "coordinates")
    o.meaning = "geometric center of the region"
    r.append(o)

    o = ObjectFeatureInfo("RegionRadii", "Eigenvalues from PCA (each pixel has unit mass)", "coor", "shape")
    o.meaning = "radii of the major and minor region axes"
    r.append(o)
    
    o = ObjectFeatureInfo("Skewness", "Skewness (3rd moment) of intensities", "ch", "intensity")
    o.meaning = "intensity skewness (computed per channel)"
    o.neighborhoodPossible = True
    r.append(o)

    o = ObjectFeatureInfo("Sum", "Sum of pixel intensities", "ch", "intensity")
    o.meaning = "sum of the intensities (computed per channel)"
    o.neighborhoodPossible = True
    r.append(o)

    o = ObjectFeatureInfo("Variance", "Variance (2nd moment) of intensities", "ch", "intensity")
    o.meaning = "intensity variance (computed per channel)"
    o.neighborhoodPossible = True
    r.append(o)

    o = ObjectFeatureInfo("Covariance", "Covariance", "ch2", "intensity")
    o.meaning = "covariance matrix for multi-channel data"
    o.neighborhoodPossible = True
    r.append(o)

    o = ObjectFeatureInfo("Weighted<RegionAxes>", "Eigenvectors from PCA (each pixel has mass according to intensity)", "coor2", "shape")
    o.meaning = "axes of inertia, when intensities are interpreted as mass"
    r.append(o)

    o = ObjectFeatureInfo("Weighted<RegionCenter>", "Center of mass (each pixel has mass according to its intensity)", "coor", "shape")
    o.meaning = "center of mass"
    r.append(o)
    
    o = ObjectFeatureInfo("Weighted<RegionRadii>", "Eigenvalues from PCA (each pixel has mass according to intensity)", "coor", "shape")
    o.meaning = "square-root of the moments of inertia"
    r.append(o)
    
    o = ObjectFeatureInfo("Central<PowerSum<2> >", "","ch", "unused")
    o.meaning = "second central moment of the intensities"
    r.append(o)

    o = ObjectFeatureInfo("Central<PowerSum<3> >", "","ch", "unused")
    o.meaning = "third central moment"
    r.append(o)

    o = ObjectFeatureInfo("Central<PowerSum<4> >", "","ch", "unused")
    o.meaning = "fourth central moment"
    r.append(o)

    o = ObjectFeatureInfo("Coord<DivideByCount<Principal<PowerSum<2> > > >", "","coor", "unused")
    r.append(o)

    o = ObjectFeatureInfo("Coord<PowerSum<1> >", "","coor", "unused")
    r.append(o)

    o = ObjectFeatureInfo("Coord<Principal<Kurtosis > >", "","coor", "unused")
    r.append(o)
    
    o =  ObjectFeatureInfo("Coord<Principal<PowerSum<2> > >", "","coor", "unused")
    r.append(o)
    
    o = ObjectFeatureInfo("Coord<Principal<PowerSum<3> > >", "","coor", "unused")
    r.append(o)

    o =  ObjectFeatureInfo("Coord<Principal<PowerSum<4> > >", "","coor", "unused")
    r.append(o)

    o =  ObjectFeatureInfo("Coord<Principal<Skewness > >", "","coor", "unused")
    r.append(o)

    o =  ObjectFeatureInfo("Weighted<Coord<DivideByCount<Principal<PowerSum<2> > > > >", "","coor", "unused")
    r.append(o)

    o =  ObjectFeatureInfo("Weighted<Coord<PowerSum<1> > >", "","coor", "unused")
    r.append(o)

    o =  ObjectFeatureInfo("Weighted<Coord<Principal<Kurtosis > > >", "","coor", "unused")
    o.meaning = "kurtosis along axes of inertia"
    r.append(o)

    o =  ObjectFeatureInfo("Weighted<Coord<Principal<PowerSum<2> > > >", "","coor", "unused")
    r.append(o)

    o =  ObjectFeatureInfo("Weighted<Coord<Principal<PowerSum<3> > > >", "","coor", "unused")
    r.append(o)

    o =  ObjectFeatureInfo("Weighted<Coord<Principal<PowerSum<4> > > >", "","coor", "unused")
    r.append(o)

    o =  ObjectFeatureInfo("Weighted<Coord<Principal<Skewness > > >", "","coor", "unused")
    o.meaning = "skewness along axes of inertia"
    r.append(o)

    o =  ObjectFeatureInfo("Weighted<PowerSum<0> >", "","ch", "unused")
    r.append(o)

    o =   ObjectFeatureInfo("Principal<Maximum >", "","ch", "unused")
    r.append(o)
    
    o =  ObjectFeatureInfo("Principal<Kurtosis >", "kurtosis of intensities after principal component projection","ch", "intensity")
    o.meaning = "kurtosis of intensities after principal component projection"
    r.append(o)
   
    o =  ObjectFeatureInfo("Principal<Minimum >", "","ch", "unused")
    r.append(o)

    o =  ObjectFeatureInfo("Principal<PowerSum<2> >", "","ch", "unused")
    r.append(o)

    o =  ObjectFeatureInfo("Principal<PowerSum<3> >", "","ch", "unused")
    r.append(o)

    o =  ObjectFeatureInfo("Principal<PowerSum<4> >", "","ch", "unused")
    r.append(o)

    o =  ObjectFeatureInfo("Principal<Skewness >", "skewness of intensities after principal component projection","ch", "intensity")
    o.meaning = "skewness of intensities after principal component projection"
    r.append(o)
    
    o =  ObjectFeatureInfo("Principal<Variance>", "variance of intensities after principal component projection","ch", "intensity")
    o.meaning = "variance of intensities after principal component projection"
    r.append(o)

    o =  ObjectFeatureInfo("PrincipalAxes", "eigenvectors of the PCA of the intensities","ch2", "intensity")
    o.meaning = "eigenvectors of the PCA of the intensities"
    r.append(o)
    
    return r

#-----------------------------------------------------------------------------


def testObjectFeatureDefinitions(features):
    r =  {x.key: x for x in features}
    
    """Unit test for the vigra object features.
    
       Test for various shapes and various number of channels
       whether the definition of ObjectFeatureInfo.size() is correct.
    """
    
    sys.stdout.write("unit test: object feature definitions ...")
    sys.stdout.flush()
    shapes = [
        (30,40,50),
        (30,40),
    ]

    for channel in [0, 2, 3, 4]:
        for shape in shapes:
            if channel == 0:
                data = numpy.random.random(shape).astype(numpy.float32)
            else:
                data = numpy.random.random(shape+(channel,)).astype(numpy.float32)
            seg  = numpy.zeros(shape, dtype=numpy.uint32)
            #seg.flat = numpy.arange(1,numpy.prod(seg.shape)+1)
            seg[0:10,0:10] = 1
            seg[0:10,10:20] = 2
            
            features = vigra.analysis.extractRegionFeatures(data, seg, features="all")
            
            for k in features.keys():
                if k == "Kurtosis" or k == "Principal<Kurtosis >":
                    continue
                
                assert k in r, "feature %s not available for shape=%r, channel=%d" % (k, shape, channel)
                info = r[k]
                #assert info.meaning is not None
                
                try:
                    feat = features[k]
                except Exception as e:
                    print "ERROR at %s | shape = %r, channel = %r" % (k, shape, channel)
                    raise e
                
                realSize = numpy.prod(feat.shape[1:]) if isinstance(feat, numpy.ndarray) and len(feat.shape) > 1 else 1
                assert info.size(len(shape), channel) == realSize, "%s has real size %d, but needs %d (shape=%r, channels=%d)" % (k, realSize, info.size(len(shape), channel), shape, channel)
                    
            grouped = defaultdict(list)
            from itertools import groupby
            for key, group in groupby(r, lambda x: r[x].group):
                for thing in group:
                    grouped[key].append(thing) 
                    
    sys.stdout.write(" done\n")
                    
#-----------------------------------------------------------------------------
   
class ObjectFeatureSelectionWidget(QWidget):
    
    msg_NoFeatureSelected = "No feature selected"
    msg_FeaturesSelected  = "%d features selected, %d channels in total"
    msg_NeighborhoodSize  = "neighborhood size in pixels:"
    
    default_neighborhood  = (30,30,1)
    
    def __init__(self, dim, channels, plugin_infos, parent=None):
        super(ObjectFeatureSelectionWidget, self).__init__(parent)
        
        self.dim        = dim
        self.channels   = channels
        self.treeWidget = None
        self.label      = None
        self.item2id    = {}
        self.help       = QTextBrowser(self)
        self.infos      = {}
        
        self.treeWidget = QTreeWidget()
        self.treeWidget.header().close()
        
        plugin2root = {}
        for p in plugin_infos:
            pluginRoot = QTreeWidgetItem()
            pluginRoot.setText(0, p.name)
            self.treeWidget.insertTopLevelItem(0, pluginRoot)
            self.label = QLabel(self)
            self.label.setText(self.msg_NoFeatureSelected)
            plugin2root[p.key] = pluginRoot
        
        nbLayout = QHBoxLayout()
        nbLayout.addSpacerItem(QSpacerItem(0,0,QSizePolicy.Expanding,QSizePolicy.Fixed))
        nbLayout.addWidget(QLabel(self.msg_NeighborhoodSize))
        self.nbSpin = [None, None, None]
        self.axes = ["X", "Y", "Z"]
        for i in range(3):
            self.nbSpin[i] = QSpinBox()
            self.nbSpin[i].setValue(self.default_neighborhood[i])
            nbLayout.addWidget(QLabel(self.axes[i]))
            nbLayout.addWidget(self.nbSpin[i])
        
        v = QVBoxLayout()
        v.addWidget(self.treeWidget)
        v.addLayout(nbLayout)
        v.addWidget(self.label)
        
        h = QSplitter(self)
        w = QWidget(self)
        w.setLayout(v)
        h.addWidget(w)
        h.addWidget(self.help)
        
        v2 = QHBoxLayout()
        v2.addWidget(h)
        self.setLayout(v2)
        
        for p in plugin_infos:
            grouped = defaultdict(list)
            for featureInfo in p.features:
                grouped[featureInfo.group].append(featureInfo)
        
            for group, featureInfos in grouped.iteritems():
                if group == "unused":
                    continue
                groupRoot = QTreeWidgetItem()
                groupRoot.setText(0, group)
                plugin2root[p.key].addChild(groupRoot)
                groupRoot.setExpanded(True)
                
                def addItem(info):
                    child = QTreeWidgetItem()
                    child.setText(0, info.humanName)
                    self.item2id[child] = info
                    groupRoot.addChild(child)
                    child.setCheckState(0, Qt.Unchecked)
                    
                for featureInfo in featureInfos:
                    addItem(featureInfo)
        
        pluginRoot.setExpanded(True)
        self.treeWidget.itemChanged.connect(self._handleItemChanged)
        self.treeWidget.itemSelectionChanged.connect(self._handleSelectionChanged)
        
    def selectedFeatures(self):
        sel = []
        for item, featureInfo in self.item2id.iteritems():
            if not item.checkState(0) == Qt.Checked:
                continue
            sel.append(featureInfo.key)
        return sorted(sel)
    
    def neighborhoodSize(self):
        return tuple(x.value() for x in self.nbSpin)

    #private:

    def _handleSelectionChanged(self):
        sel = self.treeWidget.selectedItems()
        assert len(sel) <= 1
        if not len(sel) or sel[0] not in self.item2id:
            self.help.setText("")
            return
        
        sel = sel[0]
        
        info = self.item2id[sel]
        
        self.help.setText("<h2>%s</h2><p>vigra function: <tt>%s</tt></p><p>#channels: %d</p><p><i>Meaning:</i><br />%s</p>" \
            % (info.humanName, cgi.escape(self.item2id[sel].key), info.size(self.dim, self.channels), "n/a" if info.meaning is None else info.meaning))

    def _handleChecked(self, checked, item, column):
        checked_info = self.item2id[item]
        print "%s/%s: checked=%r" % (checked_info.plugin().name, checked_info.key, checked)
      
        nCh = 0
        nFeat = 0
        for item, featureInfo in self.item2id.iteritems():
            if not item.checkState(0) == Qt.Checked:
                continue
            nCh += featureInfo.size(self.dim, self.channels)
            nFeat += 1
            
        if nFeat == 0:
            self.label.setText(self.msg_NoFeatureSelected)
        else:
            self.label.setText(self.msg_FeaturesSelected % (nFeat, nCh))
    
    def _handleItemChanged(self, item, column):
        self.treeWidget.blockSignals(True)
        if item.checkState(column) == Qt.Checked:
            self._handleChecked(True, item, column)
        elif item.checkState(column) == Qt.Unchecked:
            self._handleChecked(False, item, column)
        self.treeWidget.blockSignals(False)
        
#-----------------------------------------------------------------------------

if __name__ == "__main__":
    infos = getVigraObjectFeatureInfos()
    testObjectFeatureDefinitions(infos)

    app = QApplication([])
    
    p = PluginInfo("vigra", "Vigra Object Features")
    p.features = infos
    for f in p.features:
        f.plugin = weakref.ref(p)
        
    p2 = PluginInfo("test", "testing")
    p2.features = copy.deepcopy(infos)
    
    t = ObjectFeatureSelectionWidget(2, 0, [p, p2])
    t.show()
    print t.neighborhoodSize()
    app.exec_()
