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
    from pluginInfo import PluginInfo
    from objFeatInfo import ObjectFeatureInfo
    from vigraObjFeatures import getVigraObjectFeatureInfos
    
    infos = getVigraObjectFeatureInfos()

    app = QApplication([])
    
    p = PluginInfo("vigra", "Vigra Object Features")
    p.features = infos
        
    p2 = PluginInfo("test", "testing")
    p2.features = copy.deepcopy(infos)
    
    t = ObjectFeatureSelectionWidget(2, 0, [p, p2])
    t.show()
    print t.neighborhoodSize()
    app.exec_()
