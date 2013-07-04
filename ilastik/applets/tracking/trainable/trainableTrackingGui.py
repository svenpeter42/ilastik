from PyQt4 import uic, QtGui
import os

import logging
from ilastik.applets.layerViewer.layerViewerGui import LayerViewerGui
import sys
import traceback
import re

logger = logging.getLogger(__name__)
traceLogger = logging.getLogger('TRACE.' + __name__)

class TrainableTrackingGui( LayerViewerGui ):
    def _loadUiFile(self):
        # Load the ui file (find it in our own directory)
        localDir = os.path.split(__file__)[0]
        self._drawer = uic.loadUi(localDir+"/drawer.ui")        
        return self._drawer
    
    def initAppletDrawerUi(self):
        super(TrainableTrackingGui, self).initAppletDrawerUi()    
