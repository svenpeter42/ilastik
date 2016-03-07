###############################################################################
#   ilastik: interactive learning and segmentation toolkit
#
#       Copyright (C) 2011-2014, the ilastik developers
#                                <team@ilastik.org>
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# In addition, as a special exception, the copyright holders of
# ilastik give you permission to combine ilastik with applets,
# workflows and plugins which are not covered under the GNU
# General Public License.
#
# See the LICENSE file for details. License information is also available
# on the ilastik web site at:
#		   http://ilastik.org/license.html
###############################################################################
# Built-in
import os
import logging
import collections
from functools import partial

# Third-party
import numpy
from PyQt4 import uic
from PyQt4.QtCore import Qt, pyqtSlot, QVariant, pyqtRemoveInputHook, pyqtRestoreInputHook
from PyQt4.QtGui import QMessageBox, QColor, QIcon, QMenu, QDialog, QVBoxLayout, QDialogButtonBox, QListWidget, QListWidgetItem, QApplication, QCursor

# HCI
from volumina.api import LazyflowSource, AlphaModulatedLayer, GrayscaleLayer, ColortableLayer
from volumina.utility import ShortcutManager, PreferencesManager

from lazyflow.utility import PathComponents
from lazyflow.roi import slicing_to_string
from lazyflow.operators.opReorderAxes import OpReorderAxes
from lazyflow.operators.ioOperators import OpInputDataReader
from lazyflow.operators import OpFeatureMatrixCache

# ilastik
from ilastik.config import cfg as ilastik_config
from ilastik.utility import bind
from ilastik.utility.gui import threadRouted
from ilastik.shell.gui.iconMgr import ilastikIcons
from ilastik.applets.labeling.labelingGui import LabelingGui
from ilastik.applets.dataSelection.dataSelectionGui import DataSelectionGui, H5VolumeSelectionDlg
from ilastik.shell.gui.variableImportanceDialog import VariableImportanceDialog

import IPython
import featureSelectionDlg

try:
    from volumina.view3d.volumeRendering import RenderingManager
except ImportError:
    pass

# Loggers
logger = logging.getLogger(__name__)

def _listReplace(old, new):
    if len(old) > len(new):
        return new + old[len(new):]
    else:
        return new

class ClassifierSelectionDlg(QDialog):
    """
    A simple window to let the user select a classifier type.
    """
    def __init__(self, opPixelClassification, parent):
        super( QDialog, self ).__init__(parent=parent)
        self._op = opPixelClassification
        classifier_listwidget = QListWidget(parent=self)
        classifier_listwidget.setSelectionMode( QListWidget.SingleSelection )

        classifier_factories = self._get_available_classifier_factories()
        for name, classifier_factory in classifier_factories.items():
            item = QListWidgetItem( name )
            item.setData( Qt.UserRole, QVariant(classifier_factory) )
            classifier_listwidget.addItem(item)

        buttonbox = QDialogButtonBox( Qt.Horizontal, parent=self )
        buttonbox.setStandardButtons( QDialogButtonBox.Ok | QDialogButtonBox.Cancel )
        buttonbox.accepted.connect( self.accept )
        buttonbox.rejected.connect( self.reject )
        
        layout = QVBoxLayout()
        layout.addWidget( classifier_listwidget )
        layout.addWidget( buttonbox )

        self.setLayout(layout)
        self.setWindowTitle( "Select Classifier Type" )
        
        # Save members
        self._classifier_listwidget = classifier_listwidget
        
    def _get_available_classifier_factories(self):
        # FIXME: Replace this logic with a proper plugin mechanism
        from lazyflow.classifiers import VigraRfLazyflowClassifierFactory, SklearnLazyflowClassifierFactory, \
                                         ParallelVigraRfLazyflowClassifierFactory, VigraRfPixelwiseClassifierFactory,\
                                         LazyflowVectorwiseClassifierFactoryABC, LazyflowPixelwiseClassifierFactoryABC
        classifiers = collections.OrderedDict()
        classifiers["Parallel Random Forest (VIGRA)"] = ParallelVigraRfLazyflowClassifierFactory(100)
        
        try:
            from sklearn.ensemble import RandomForestClassifier, AdaBoostClassifier
            from sklearn.naive_bayes import GaussianNB
            from sklearn.tree import DecisionTreeClassifier
            from sklearn.neighbors import KNeighborsClassifier
            from sklearn.lda import LDA
            from sklearn.qda import QDA
            from sklearn.svm import SVC, NuSVC
            classifiers["Random Forest (scikit-learn)"] = SklearnLazyflowClassifierFactory( RandomForestClassifier, 100 )
            classifiers["Gaussian Naive Bayes (scikit-learn)"] = SklearnLazyflowClassifierFactory( GaussianNB )
            classifiers["AdaBoost (scikit-learn)"] = SklearnLazyflowClassifierFactory( AdaBoostClassifier, n_estimators=100 )
            classifiers["Single Decision Tree (scikit-learn)"] = SklearnLazyflowClassifierFactory( DecisionTreeClassifier, max_depth=5 )
            classifiers["K-Neighbors (scikit-learn)"] = SklearnLazyflowClassifierFactory( KNeighborsClassifier )
            classifiers["LDA (scikit-learn)"] = SklearnLazyflowClassifierFactory( LDA )
            classifiers["QDA (scikit-learn)"] = SklearnLazyflowClassifierFactory( QDA )
            classifiers["SVM C-Support (scikit-learn)"] = SklearnLazyflowClassifierFactory( SVC, probability=True )
            classifiers["SVM Nu-Support (scikit-learn)"] = SklearnLazyflowClassifierFactory( NuSVC, probability=True )
        except ImportError:
            import warnings
            warnings.warn("Couldn't import sklearn. Scikit-learn classifiers not available.")

        # Debug classifiers
        classifiers["Parallel Random Forest with Variable Importance (VIGRA)"] = ParallelVigraRfLazyflowClassifierFactory(100, variable_importance_enabled=True)        
        classifiers["(debug) Single-threaded Random Forest (VIGRA)"] = VigraRfLazyflowClassifierFactory(100)
        classifiers["(debug) Pixelwise Random Forest (VIGRA)"] = VigraRfPixelwiseClassifierFactory(100)
        
        return classifiers
        
    def accept(self):
        # Configure the operator with the newly selected classifier factory
        selected_item = self._classifier_listwidget.selectedItems()[0]
        selected_factory = selected_item.data(Qt.UserRole).toPyObject()
        self._op.ClassifierFactory.setValue( selected_factory )

        # Close the dlg
        super( ClassifierSelectionDlg, self ).accept()
    
class PixelClassificationGui(LabelingGui):

    ###########################################
    ### AppletGuiInterface Concrete Methods ###
    ###########################################
    def centralWidget( self ):
        return self

    def stopAndCleanUp(self):
        for fn in self.__cleanup_fns:
            fn()

        # Base class
        super(PixelClassificationGui, self).stopAndCleanUp()

    def viewerControlWidget(self):
        return self._viewerControlUi

    def menus( self ):
        menus = super( PixelClassificationGui, self ).menus()

        # For now classifier selection is only available in debug mode
        if ilastik_config.getboolean('ilastik', 'debug'):
            advanced_menu = QMenu("Advanced", parent=self)
                        
            def handleClassifierAction():
                dlg = ClassifierSelectionDlg(self.topLevelOperatorView, parent=self)
                dlg.exec_()
            
            classifier_action = advanced_menu.addAction("Classifier...")
            classifier_action.triggered.connect( handleClassifierAction )
            
            def showVarImpDlg():
                varImpDlg = VariableImportanceDialog(self.topLevelOperatorView.Classifier.value.named_importances, parent=self)
                varImpDlg.exec_()
                
            advanced_menu.addAction("Variable Importance Table").triggered.connect(showVarImpDlg)            
            
            def handleImportLabelsAction():
                # Find the directory of the most recently opened image file
                mostRecentImageFile = PreferencesManager().get( 'DataSelection', 'recent image' )
                if mostRecentImageFile is not None:
                    defaultDirectory = os.path.split(mostRecentImageFile)[0]
                else:
                    defaultDirectory = os.path.expanduser('~')
                fileNames = DataSelectionGui.getImageFileNamesToOpen(self, defaultDirectory)
                fileNames = map(str, fileNames)
                
                # For now, we require a single hdf5 file
                if len(fileNames) > 1:
                    QMessageBox.critical(self, "Too many files", 
                                         "Labels must be contained in a single hdf5 volume.")
                    return
                if len(fileNames) == 0:
                    # user cancelled
                    return
                
                file_path = fileNames[0]
                internal_paths = DataSelectionGui.getPossibleInternalPaths(file_path)
                if len(internal_paths) == 0:
                    QMessageBox.critical(self, "No volumes in file", 
                                         "Couldn't find a suitable dataset in your hdf5 file.")
                    return
                if len(internal_paths) == 1:
                    internal_path = internal_paths[0]
                else:
                    dlg = H5VolumeSelectionDlg(internal_paths, self)
                    if dlg.exec_() == QDialog.Rejected:
                        return
                    selected_index = dlg.combo.currentIndex()
                    internal_path = str(internal_paths[selected_index])

                path_components = PathComponents(file_path)
                path_components.internalPath = str(internal_path)
                
                try:
                    top_op = self.topLevelOperatorView
                    opReader = OpInputDataReader(parent=top_op.parent)
                    opReader.FilePath.setValue( path_components.totalPath() )
                    
                    # Reorder the axes
                    op5 = OpReorderAxes(parent=top_op.parent)
                    op5.AxisOrder.setValue( top_op.LabelInputs.meta.getAxisKeys() )
                    op5.Input.connect( opReader.Output )
                
                    # Finally, import the labels
                    top_op.importLabels( top_op.current_view_index(), op5.Output )
                        
                finally:
                    op5.cleanUp()
                    opReader.cleanUp()

            def print_label_blocks(sorted_axis):
                sorted_column = self.topLevelOperatorView.InputImages.meta.getAxisKeys().index(sorted_axis)
                
                input_shape = self.topLevelOperatorView.InputImages.meta.shape
                label_block_slicings = self.topLevelOperatorView.NonzeroLabelBlocks.value

                sorted_block_slicings = sorted(label_block_slicings, key=lambda s: s[sorted_column])

                for slicing in sorted_block_slicings:
                    # Omit channel
                    order = "".join( self.topLevelOperatorView.InputImages.meta.getAxisKeys() )
                    line = order[:-1].upper() + ": "
                    line += slicing_to_string( slicing[:-1], input_shape )
                    print line

            labels_submenu = QMenu("Labels")
            self.labels_submenu = labels_submenu # Must retain this reference or else it gets auto-deleted.
            
            import_labels_action = labels_submenu.addAction("Import Labels...")
            import_labels_action.triggered.connect( handleImportLabelsAction )

            self.print_labels_submenu = QMenu("Print Label Blocks")
            labels_submenu.addMenu(self.print_labels_submenu)
            
            for axis in self.topLevelOperatorView.InputImages.meta.getAxisKeys()[:-1]:
                self.print_labels_submenu\
                    .addAction("Sort by {}".format( axis.upper() ))\
                    .triggered.connect( partial(print_label_blocks, axis) )

            advanced_menu.addMenu(labels_submenu)
            
            menus += [advanced_menu]

        return menus

    ###########################################
    ###########################################

    def __init__(self, parentApplet, topLevelOperatorView, labelingDrawerUiPath=None ):
        self.parentApplet = parentApplet
        # Tell our base class which slots to monitor
        labelSlots = LabelingGui.LabelingSlots()
        labelSlots.labelInput = topLevelOperatorView.LabelInputs
        labelSlots.labelOutput = topLevelOperatorView.LabelImages
        labelSlots.labelEraserValue = topLevelOperatorView.opLabelPipeline.opLabelArray.eraser
        labelSlots.labelDelete = topLevelOperatorView.opLabelPipeline.DeleteLabel
        labelSlots.labelNames = topLevelOperatorView.LabelNames

        self.__cleanup_fns = []

        # We provide our own UI file (which adds an extra control for interactive mode)
        if labelingDrawerUiPath is None:
            labelingDrawerUiPath = os.path.split(__file__)[0] + '/labelingDrawer.ui'

        # Base class init
        super(PixelClassificationGui, self).__init__( parentApplet, labelSlots, topLevelOperatorView, labelingDrawerUiPath )
        
        self.topLevelOperatorView = topLevelOperatorView

        self.interactiveModeActive = False
        # Immediately update our interactive state
        self.toggleInteractive( not self.topLevelOperatorView.FreezePredictions.value )

        self._currentlySavingPredictions = False

        self.labelingDrawerUi.labelListView.support_merges = True

        self.labelingDrawerUi.liveUpdateButton.setEnabled(False)
        self.labelingDrawerUi.liveUpdateButton.setIcon( QIcon(ilastikIcons.Play) )
        self.labelingDrawerUi.liveUpdateButton.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.labelingDrawerUi.liveUpdateButton.toggled.connect( self.toggleInteractive )

        self.initFeatSelDlg()
        self.labelingDrawerUi.suggestFeaturesButton.clicked.connect(self.show_feature_selection_dialog)
        self.featSelDlg.accepted.connect(self.update_features_from_dialog)

        self.topLevelOperatorView.LabelNames.notifyDirty( bind(self.handleLabelSelectionChange) )
        self.__cleanup_fns.append( partial( self.topLevelOperatorView.LabelNames.unregisterDirty, bind(self.handleLabelSelectionChange) ) )
        
        self._initShortcuts()


        # FIXME: We MUST NOT enable the render manager by default,
        #        since it will drastically slow down the app for large volumes.
        #        For now, we leave it off by default.
        #        To re-enable rendering, we need to allow the user to render a segmentation 
        #        and then initialize the render manager on-the-fly. 
        #        (We might want to warn the user if her volume is not small.)
        self.render = False
        self._renderMgr = None
        self._renderedLayers = {} # (layer name, label number)
        
        # Always off for now (see note above)
        if self.render:
            try:
                self._renderMgr = RenderingManager( self.editor.view3d )
            except:
                self.render = False

        # toggle interactive mode according to freezePredictions.value
        self.toggleInteractive(not self.topLevelOperatorView.FreezePredictions.value)
        def FreezePredDirty():
            self.toggleInteractive(not self.topLevelOperatorView.FreezePredictions.value)
        # listen to freezePrediction changes
        self.topLevelOperatorView.FreezePredictions.notifyDirty( bind(FreezePredDirty) )
        self.__cleanup_fns.append( partial( self.topLevelOperatorView.FreezePredictions.unregisterDirty, bind(FreezePredDirty) ) )

    def initFeatSelDlg(self):
        thisOpFeatureSelection = self.topLevelOperatorView.parent.featureSelectionApplet.topLevelOperator.innerOperators[0]

        from FeatureSelectionDialog import FeatureSelectionDialog
        self.featSelDlg = FeatureSelectionDialog(thisOpFeatureSelection, self.topLevelOperatorView)

        '''
        self.featSelDlg = featureSelectionDlg.FeatureSelectionDlg()
        self.featSelDlg.accepted.connect(self.selectFeatures)'''

    def show_feature_selection_dialog(self):
        self.featSelDlg.exec_()


    def update_features_from_dialog(self):
        thisOpFeatureSelection = self.topLevelOperatorView.parent.featureSelectionApplet.topLevelOperator.innerOperators[0]


        thisOpFeatureSelection.SelectionMatrix.setValue(self.featSelDlg.selected_features_matrix)
        thisOpFeatureSelection.SelectionMatrix.setDirty()
        thisOpFeatureSelection.setupOutputs()
        '''
        method = self.featSelDlg.selectedMethod

        QApplication.instance().setOverrideCursor( QCursor(Qt.WaitCursor) )

        pyqtRemoveInputHook()  # i need to do this if i want to get into the ipython shell. This line (and the one on
        # the bottom) must be removed before release because they freeze the gui

        import IPython
        import numpy as np


        # activate all features
        current_matrix = thisOpFeatureSelection.SelectionMatrix.value
        current_matrix[:,1:] = True
        current_matrix[0, 0] = True
        current_matrix[1:, 0] = False # do not use any other feature than gauss smooth on sigma=0.3
        thisOpFeatureSelection.SelectionMatrix.setValue(current_matrix)
        thisOpFeatureSelection.SelectionMatrix.setDirty() # this does not do anything!?!?
        IPython.embed()
        thisOpFeatureSelection.setupOutputs()


        # we should be able to modify this via a gui element
        # this should also be controlled by the gui

        if method == "Filter":
            self.topLevelOperatorView.opFilterFeatureSelection.NumberOfSelectedFeatures.setValue(8)
            selected_feature_ids = self.topLevelOperatorView.opFilterFeatureSelection.SelectedFeatureIDs.value
        elif method == "Wrapper":
            selected_feature_ids = self.topLevelOperatorView.opWrapperFeatureSelection.SelectedFeatureIDs.value
        elif method == "Gini":
            self.topLevelOperatorView.opGiniFeatureSelection.NumberOfSelectedFeatures.setValue(8)
            selected_feature_ids = self.topLevelOperatorView.opGiniFeatureSelection.SelectedFeatureIDs.value
        else:
            raise Exception("invalid feature selection method: %s" % method)


        # now it gets pretty messy... There must be another way to identify which values in the feature matrix need to
        # be modified...
        feature_channel_names = self.topLevelOperatorView.FeatureImages.meta['channel_names']
        scales = thisOpFeatureSelection.Scales.value
        featureIDs = thisOpFeatureSelection.FeatureIds.value
        current_matrix = thisOpFeatureSelection.SelectionMatrix.value
        new_matrix = np.zeros(current_matrix.shape, 'bool')  # initialize new matrix as all False

        # now find out where i need to make changes in the matrix
        # matrix is len(features) by len(scales)
        for feature in selected_feature_ids:
            channel_name = feature_channel_names[feature]
            eq_sign_pos = channel_name.find("=")
            right_bracket_pos = channel_name.find(")")
            scale = float(channel_name[eq_sign_pos + 1 : right_bracket_pos])
            if "Smoothing" in channel_name:
                featureID = "GaussianSmoothing"
            elif "Laplacian" in channel_name:
                featureID = "LaplacianOfGaussian"
            elif "Magnitude" in channel_name:
                featureID = "GaussianGradientMagnitude"
            elif "Difference" in channel_name:
                featureID = "DifferenceOfGaussians"
            elif "Structure" in channel_name:
                featureID = "StructureTensorEigenvalues"
            elif "Hessian" in channel_name:
                featureID = "HessianOfGaussianEigenvalues"
            else:
                raise Exception("Unkown feature encountered!")

            col_position_in_matrix = scales.index(scale)
            row_position_in_matrix = featureIDs.index(featureID)
            new_matrix[row_position_in_matrix, col_position_in_matrix] = True


        thisOpFeatureSelection.SelectionMatrix.setValue(new_matrix)
        thisOpFeatureSelection.SelectionMatrix.setDirty()
        thisOpFeatureSelection.setupOutputs()

        QApplication.instance().restoreOverrideCursor()

        pyqtRestoreInputHook()
        '''

    def initViewerControlUi(self):
        localDir = os.path.split(__file__)[0]
        self._viewerControlUi = uic.loadUi( os.path.join( localDir, "viewerControls.ui" ) )

        # Connect checkboxes
        def nextCheckState(checkbox):
            checkbox.setChecked( not checkbox.isChecked() )
        self._viewerControlUi.checkShowPredictions.nextCheckState = partial(nextCheckState, self._viewerControlUi.checkShowPredictions)
        self._viewerControlUi.checkShowSegmentation.nextCheckState = partial(nextCheckState, self._viewerControlUi.checkShowSegmentation)

        self._viewerControlUi.checkShowPredictions.clicked.connect( self.handleShowPredictionsClicked )
        self._viewerControlUi.checkShowSegmentation.clicked.connect( self.handleShowSegmentationClicked )

        # The editor's layerstack is in charge of which layer movement buttons are enabled
        model = self.editor.layerStack
        self._viewerControlUi.viewerControls.setupConnections(model)
       
    def _initShortcuts(self):
        mgr = ShortcutManager()
        ActionInfo = ShortcutManager.ActionInfo
        shortcutGroupName = "Predictions"

        mgr.register( "p", ActionInfo( shortcutGroupName,
                                       "Toggle Prediction",
                                       "Toggle Prediction Layer Visibility",
                                       self._viewerControlUi.checkShowPredictions.click,
                                       self._viewerControlUi.checkShowPredictions,
                                       self._viewerControlUi.checkShowPredictions ) )

        mgr.register( "s", ActionInfo( shortcutGroupName,
                                       "Toggle Segmentaton",
                                       "Toggle Segmentaton Layer Visibility",
                                       self._viewerControlUi.checkShowSegmentation.click,
                                       self._viewerControlUi.checkShowSegmentation,
                                       self._viewerControlUi.checkShowSegmentation ) )

        mgr.register( "l", ActionInfo( shortcutGroupName,
                                       "Live Prediction",
                                       "Toggle Live Prediction Mode",
                                       self.labelingDrawerUi.liveUpdateButton.toggle,
                                       self.labelingDrawerUi.liveUpdateButton,
                                       self.labelingDrawerUi.liveUpdateButton ) )

    def _setup_contexts(self, layer):
        def callback(pos, clayer=layer):
            name = clayer.name
            if name in self._renderedLayers:
                label = self._renderedLayers.pop(name)
                self._renderMgr.removeObject(label)
                self._update_rendering()
            else:
                label = self._renderMgr.addObject()
                self._renderedLayers[clayer.name] = label
                self._update_rendering()

        if self.render:
            layer.contexts.append(('Toggle 3D rendering', callback))

    def setupLayers(self):
        """
        Called by our base class when one of our data slots has changed.
        This function creates a layer for each slot we want displayed in the volume editor.
        """
        # Base class provides the label layer.
        layers = super(PixelClassificationGui, self).setupLayers()

        ActionInfo = ShortcutManager.ActionInfo

        if ilastik_config.getboolean('ilastik', 'debug'):

            # Add the label projection layer.
            labelProjectionSlot = self.topLevelOperatorView.opLabelPipeline.opLabelArray.Projection2D
            if labelProjectionSlot.ready():
                projectionSrc = LazyflowSource(labelProjectionSlot)
                try:
                    # This colortable requires matplotlib
                    from volumina.colortables import jet
                    projectionLayer = ColortableLayer( projectionSrc, 
                                                       colorTable=[QColor(0,0,0,128).rgba()]+jet(N=255), 
                                                       normalize=(0.0, 1.0) )
                except (ImportError, RuntimeError):
                    pass
                else:
                    projectionLayer.name = "Label Projection"
                    projectionLayer.visible = False
                    projectionLayer.opacity = 1.0
                    layers.append(projectionLayer)

        # Show the mask over everything except labels
        maskSlot = self.topLevelOperatorView.PredictionMasks
        if maskSlot.ready():
            maskLayer = self._create_binary_mask_layer_from_slot( maskSlot )
            maskLayer.name = "Mask"
            maskLayer.visible = True
            maskLayer.opacity = 1.0
            layers.append( maskLayer )

        # Add the uncertainty estimate layer
        uncertaintySlot = self.topLevelOperatorView.UncertaintyEstimate
        if uncertaintySlot.ready():
            uncertaintySrc = LazyflowSource(uncertaintySlot)
            uncertaintyLayer = AlphaModulatedLayer( uncertaintySrc,
                                                    tintColor=QColor( Qt.cyan ),
                                                    range=(0.0, 1.0),
                                                    normalize=(0.0, 1.0) )
            uncertaintyLayer.name = "Uncertainty"
            uncertaintyLayer.visible = False
            uncertaintyLayer.opacity = 1.0
            uncertaintyLayer.shortcutRegistration = ( "u", ActionInfo( "Prediction Layers",
                                                                       "Uncertainty",
                                                                       "Show/Hide Uncertainty",
                                                                       uncertaintyLayer.toggleVisible,
                                                                       self.viewerControlWidget(),
                                                                       uncertaintyLayer ) )
            layers.append(uncertaintyLayer)

        labels = self.labelListData

        # Add each of the segmentations
        for channel, segmentationSlot in enumerate(self.topLevelOperatorView.SegmentationChannels):
            if segmentationSlot.ready() and channel < len(labels):
                ref_label = labels[channel]
                segsrc = LazyflowSource(segmentationSlot)
                segLayer = AlphaModulatedLayer( segsrc,
                                                tintColor=ref_label.pmapColor(),
                                                range=(0.0, 1.0),
                                                normalize=(0.0, 1.0) )

                segLayer.opacity = 1
                segLayer.visible = False #self.labelingDrawerUi.liveUpdateButton.isChecked()
                segLayer.visibleChanged.connect(self.updateShowSegmentationCheckbox)

                def setLayerColor(c, segLayer_=segLayer, initializing=False):
                    if not initializing and segLayer_ not in self.layerstack:
                        # This layer has been removed from the layerstack already.
                        # Don't touch it.
                        return
                    segLayer_.tintColor = c
                    self._update_rendering()

                def setSegLayerName(n, segLayer_=segLayer, initializing=False):
                    if not initializing and segLayer_ not in self.layerstack:
                        # This layer has been removed from the layerstack already.
                        # Don't touch it.
                        return
                    oldname = segLayer_.name
                    newName = "Segmentation (%s)" % n
                    segLayer_.name = newName
                    if not self.render:
                        return
                    if oldname in self._renderedLayers:
                        label = self._renderedLayers.pop(oldname)
                        self._renderedLayers[newName] = label

                setSegLayerName(ref_label.name, initializing=True)

                ref_label.pmapColorChanged.connect(setLayerColor)
                ref_label.nameChanged.connect(setSegLayerName)
                #check if layer is 3d before adding the "Toggle 3D" option
                #this check is done this way to match the VolumeRenderer, in
                #case different 3d-axistags should be rendered like t-x-y
                #_axiskeys = segmentationSlot.meta.getAxisKeys()
                if len(segmentationSlot.meta.shape) == 4:
                    #the Renderer will cut out the last shape-dimension, so
                    #we're checking for 4 dimensions
                    self._setup_contexts(segLayer)
                layers.append(segLayer)
        
        # Add each of the predictions
        for channel, predictionSlot in enumerate(self.topLevelOperatorView.PredictionProbabilityChannels):
            if predictionSlot.ready() and channel < len(labels):
                ref_label = labels[channel]
                predictsrc = LazyflowSource(predictionSlot)
                predictLayer = AlphaModulatedLayer( predictsrc,
                                                    tintColor=ref_label.pmapColor(),
                                                    range=(0.0, 1.0),
                                                    normalize=(0.0, 1.0) )
                predictLayer.opacity = 0.25
                predictLayer.visible = self.labelingDrawerUi.liveUpdateButton.isChecked()
                predictLayer.visibleChanged.connect(self.updateShowPredictionCheckbox)

                def setLayerColor(c, predictLayer_=predictLayer, initializing=False):
                    if not initializing and predictLayer_ not in self.layerstack:
                        # This layer has been removed from the layerstack already.
                        # Don't touch it.
                        return
                    predictLayer_.tintColor = c

                def setPredLayerName(n, predictLayer_=predictLayer, initializing=False):
                    if not initializing and predictLayer_ not in self.layerstack:
                        # This layer has been removed from the layerstack already.
                        # Don't touch it.
                        return
                    newName = "Prediction for %s" % n
                    predictLayer_.name = newName

                setPredLayerName(ref_label.name, initializing=True)
                ref_label.pmapColorChanged.connect(setLayerColor)
                ref_label.nameChanged.connect(setPredLayerName)
                layers.append(predictLayer)

        # Add the raw data last (on the bottom)
        inputDataSlot = self.topLevelOperatorView.InputImages        
        if inputDataSlot.ready():                        
            inputLayer = self.createStandardLayerFromSlot( inputDataSlot )
            inputLayer.name = "Input Data"
            inputLayer.visible = True
            inputLayer.opacity = 1.0
            # the flag window_leveling is used to determine if the contrast 
            # of the layer is adjustable
            if isinstance( inputLayer, GrayscaleLayer ):
                inputLayer.window_leveling = True
            else:
                inputLayer.window_leveling = False

            def toggleTopToBottom():
                index = self.layerstack.layerIndex( inputLayer )
                self.layerstack.selectRow( index )
                if index == 0:
                    self.layerstack.moveSelectedToBottom()
                else:
                    self.layerstack.moveSelectedToTop()

            inputLayer.shortcutRegistration = ( "i", ActionInfo( "Prediction Layers",
                                                                 "Bring Input To Top/Bottom",
                                                                 "Bring Input To Top/Bottom",
                                                                 toggleTopToBottom,
                                                                 self.viewerControlWidget(),
                                                                 inputLayer ) )
            layers.append(inputLayer)
            
            # The thresholding button can only be used if the data is displayed as grayscale.
            if inputLayer.window_leveling:
                self.labelingDrawerUi.thresToolButton.show()
            else:
                self.labelingDrawerUi.thresToolButton.hide()
        
        self.handleLabelSelectionChange()
        return layers

    def toggleInteractive(self, checked):
        logger.debug("toggling interactive mode to '%r'" % checked)

        if checked==True:
            if not self.topLevelOperatorView.FeatureImages.ready() \
            or self.topLevelOperatorView.FeatureImages.meta.shape==None:
                self.labelingDrawerUi.liveUpdateButton.setChecked(False)
                mexBox=QMessageBox()
                mexBox.setText("There are no features selected ")
                mexBox.exec_()
                return

        # If we're changing modes, enable/disable our controls and other applets accordingly
        if self.interactiveModeActive != checked:
            if checked:
                self.labelingDrawerUi.labelListView.allowDelete = False
                self.labelingDrawerUi.AddLabelButton.setEnabled( False )
            else:
                num_label_classes = self._labelControlUi.labelListModel.rowCount()
                self.labelingDrawerUi.labelListView.allowDelete = ( num_label_classes > self.minLabelNumber )
                self.labelingDrawerUi.AddLabelButton.setEnabled( ( num_label_classes < self.maxLabelNumber ) )
        self.interactiveModeActive = checked

        self.topLevelOperatorView.FreezePredictions.setValue( not checked )
        self.labelingDrawerUi.liveUpdateButton.setChecked(checked)
        # Auto-set the "show predictions" state according to what the user just clicked.
        if checked:
            self._viewerControlUi.checkShowPredictions.setChecked( True )
            self.handleShowPredictionsClicked()

        # Notify the workflow that some applets may have changed state now.
        # (For example, the downstream pixel classification applet can 
        #  be used now that there are features selected)
        self.parentApplet.appletStateUpdateRequested.emit()

    @pyqtSlot()
    def handleShowPredictionsClicked(self):
        checked = self._viewerControlUi.checkShowPredictions.isChecked()
        for layer in self.layerstack:
            if "Prediction" in layer.name:
                layer.visible = checked

    @pyqtSlot()
    def handleShowSegmentationClicked(self):
        checked = self._viewerControlUi.checkShowSegmentation.isChecked()
        for layer in self.layerstack:
            if "Segmentation" in layer.name:
                layer.visible = checked

    @pyqtSlot()
    def updateShowPredictionCheckbox(self):
        predictLayerCount = 0
        visibleCount = 0
        for layer in self.layerstack:
            if "Prediction" in layer.name:
                predictLayerCount += 1
                if layer.visible:
                    visibleCount += 1

        if visibleCount == 0:
            self._viewerControlUi.checkShowPredictions.setCheckState(Qt.Unchecked)
        elif predictLayerCount == visibleCount:
            self._viewerControlUi.checkShowPredictions.setCheckState(Qt.Checked)
        else:
            self._viewerControlUi.checkShowPredictions.setCheckState(Qt.PartiallyChecked)

    @pyqtSlot()
    def updateShowSegmentationCheckbox(self):
        segLayerCount = 0
        visibleCount = 0
        for layer in self.layerstack:
            if "Segmentation" in layer.name:
                segLayerCount += 1
                if layer.visible:
                    visibleCount += 1

        if visibleCount == 0:
            self._viewerControlUi.checkShowSegmentation.setCheckState(Qt.Unchecked)
        elif segLayerCount == visibleCount:
            self._viewerControlUi.checkShowSegmentation.setCheckState(Qt.Checked)
        else:
            self._viewerControlUi.checkShowSegmentation.setCheckState(Qt.PartiallyChecked)

    @pyqtSlot()
    @threadRouted
    def handleLabelSelectionChange(self):
        enabled = False
        if self.topLevelOperatorView.LabelNames.ready():
            enabled = True
            enabled &= len(self.topLevelOperatorView.LabelNames.value) >= 2
            enabled &= numpy.all(numpy.asarray(self.topLevelOperatorView.CachedFeatureImages.meta.shape) > 0)
            # FIXME: also check that each label has scribbles?
        
        if not enabled:
            self.labelingDrawerUi.liveUpdateButton.setChecked(False)
            self._viewerControlUi.checkShowPredictions.setChecked(False)
            self._viewerControlUi.checkShowSegmentation.setChecked(False)
            self.handleShowPredictionsClicked()
            self.handleShowSegmentationClicked()

        self.labelingDrawerUi.liveUpdateButton.setEnabled(enabled)
        self._viewerControlUi.checkShowPredictions.setEnabled(enabled)
        self._viewerControlUi.checkShowSegmentation.setEnabled(enabled)

    def _getNext(self, slot, parentFun, transform=None):
        numLabels = self.labelListData.rowCount()
        value = slot.value
        if numLabels < len(value):
            result = value[numLabels]
            if transform is not None:
                result = transform(result)
            return result
        else:
            return parentFun()

    def _onLabelChanged(self, parentFun, mapf, slot):
        parentFun()
        new = map(mapf, self.labelListData)
        old = slot.value
        slot.setValue(_listReplace(old, new))

    def _onLabelRemoved(self, parent, start, end):
        # Call the base class to update the operator.
        super(PixelClassificationGui, self)._onLabelRemoved(parent, start, end)

        # Keep colors in sync with names
        # (If we deleted a name, delete its corresponding colors, too.)
        op = self.topLevelOperatorView
        if len(op.PmapColors.value) > len(op.LabelNames.value):
            for slot in (op.LabelColors, op.PmapColors):
                value = slot.value
                value.pop(start)
                # Force dirty propagation even though the list id is unchanged.
                slot.setValue(value, check_changed=False)

    def getNextLabelName(self):
        return self._getNext(self.topLevelOperatorView.LabelNames,
                             super(PixelClassificationGui, self).getNextLabelName)

    def getNextLabelColor(self):
        return self._getNext(
            self.topLevelOperatorView.LabelColors,
            super(PixelClassificationGui, self).getNextLabelColor,
            lambda x: QColor(*x)
        )

    def getNextPmapColor(self):
        return self._getNext(
            self.topLevelOperatorView.PmapColors,
            super(PixelClassificationGui, self).getNextPmapColor,
            lambda x: QColor(*x)
        )

    def onLabelNameChanged(self):
        self._onLabelChanged(super(PixelClassificationGui, self).onLabelNameChanged,
                             lambda l: l.name,
                             self.topLevelOperatorView.LabelNames)

    def onLabelColorChanged(self):
        self._onLabelChanged(super(PixelClassificationGui, self).onLabelColorChanged,
                             lambda l: (l.brushColor().red(),
                                        l.brushColor().green(),
                                        l.brushColor().blue()),
                             self.topLevelOperatorView.LabelColors)


    def onPmapColorChanged(self):
        self._onLabelChanged(super(PixelClassificationGui, self).onPmapColorChanged,
                             lambda l: (l.pmapColor().red(),
                                        l.pmapColor().green(),
                                        l.pmapColor().blue()),
                             self.topLevelOperatorView.PmapColors)

    def _update_rendering(self):
        if not self.render:
            return
        shape = self.topLevelOperatorView.InputImages.meta.shape[1:4]
        if len(shape) != 5:
            #this might be a 2D image, no need for updating any 3D stuff 
            return
        
        time = self.editor.posModel.slicingPos5D[0]
        if not self._renderMgr.ready:
            self._renderMgr.setup(shape)

        layernames = set(layer.name for layer in self.layerstack)
        self._renderedLayers = dict((k, v) for k, v in self._renderedLayers.iteritems()
                                if k in layernames)

        newvolume = numpy.zeros(shape, dtype=numpy.uint8)
        for layer in self.layerstack:
            try:
                label = self._renderedLayers[layer.name]
            except KeyError:
                continue
            for ds in layer.datasources:
                vol = ds.dataSlot.value[time, ..., 0]
                indices = numpy.where(vol != 0)
                newvolume[indices] = label

        self._renderMgr.volume = newvolume
        self._update_colors()
        self._renderMgr.update()

    def _update_colors(self):
        for layer in self.layerstack:
            try:
                label = self._renderedLayers[layer.name]
            except KeyError:
                continue
            color = layer.tintColor
            color = (color.red() / 255.0, color.green() / 255.0, color.blue() / 255.0)
            self._renderMgr.setColor(label, color)
