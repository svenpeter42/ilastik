# -*- coding: utf-8 -*-
__author__ = 'fabian'

import numpy as np
# import scipy
from PyQt4 import QtCore, QtGui
from PyQt4.QtCore import pyqtRemoveInputHook, pyqtRestoreInputHook
# import pyqtgraph as pg

# import IPython

# from volumina.api import Viewer
from volumina.widgets import layerwidget
from volumina import volumeEditorWidget
from volumina.layer import ColortableLayer, GrayscaleLayer, RGBALayer
from volumina import colortables
from volumina.pixelpipeline.datasourcefactories import createDataSource

from ilastik.applets.pixelClassification import opPixelClassification
from lazyflow.operators import OpFeatureMatrixCache
from ilastik.utility import OpMultiLaneWrapper
from lazyflow import graph

from os import times
import re



# just a container class, nothing fancy here
class FeatureSelectionResult(object):
    def __init__(self, feature_matrix, feature_ids, segmentation, parameters, selection_method, oob_err = None, feature_calc_time = None):
        self.feature_matrix = feature_matrix
        self.segmentation = segmentation
        self.parameters = parameters
        self.selection_method = selection_method
        self.oob_err = oob_err
        self.feature_calc_time = feature_calc_time
        self.feature_ids = feature_ids


        self.name = self._create_name()

    def _create_name(self):
        """
        Returns: name for the method to be displayed in the lower left part of the dialog
        FIXME: make more human readable

        """

        if self.selection_method == "filter" or self.selection_method == "gini":
            if self.parameters["num_of_feat"] == 0:
                name = "%s_%d_feat(auto)" % (self.selection_method, np.sum(self.feature_matrix))
            else:
                name = "%s_%d_feat" % (self.selection_method, self.parameters["num_of_feat"])
        elif self.selection_method == "wrapper":
            name = "%s_c_%1.02f_%i_feat" % (self.selection_method, self.parameters["c"], np.sum(self.feature_matrix))
        else:
            name = self.selection_method
        if self.oob_err is not None:
            name += "_oob:%1.3f" % self.oob_err
        if self.feature_calc_time is not None:
            name += "_ctime:%1.3f" % self.feature_calc_time
        return name

    def change_name(self, name):
        self.name = name



class FeatureSelectionDialog(QtGui.QDialog):
    def __init__(self, current_opFeatureSelection, current_opPixelClassification):
        '''

        :param current_opFeatureSelection: opFeatureSelection from ilastik
        :param current_opPixelClassification: opPixelClassification form Ilastik
        '''
        super(FeatureSelectionDialog, self).__init__()

        self.opPixelClassification = current_opPixelClassification
        self.opFeatureSelection = current_opFeatureSelection

        self._init_feature_matrix = False

        # lazyflow required operator to be connected to a graph, although no interconnection takes place here
        g = graph.Graph()

        # instantiate feature selection operators
        # these operators are not connected to the ilastik lazyflow architecture.
        # Reason provided in self._run_selection()
        self.opFilterFeatureSelection = opPixelClassification.OpFilterFeatureSelection(graph=g)
        self.opWrapperFeatureSelection = opPixelClassification.OpWrapperFeatureSelection(graph=g)
        self.opGiniFeatureSelection = opPixelClassification.OpGiniFeatureSelection(graph=g)

        # retrieve the featurematrixcaches operator from the opPixelclassification. This operator provides the features
        # and labels matrix required by the feature selection operators
        self.opFeatureMatrixCaches = self.opPixelClassification.opFeatureMatrixCaches

        '''FIXME / FixMe: the FeatureSelectionDialog will only display one slice of the dataset. This is for RAM saving
        reasons. By using only one slice, we can simple predict the segmentation of that slice for each feature set and
        store it in RAM. If we allowed to show the whole dataset, then we would have to copy the opFeatureSelection and
        opPixelClassification once for each feature set. This would result in too much feature computation time as
        well as too much RAM usage.
        However, this shortcoming could be overcome by creating something like an opFeatureSubset. Then we would enable
        all features in the opFeatureSelection and the feature sets are created by 'filtering' the output of the
        opFeatureSelection. Thereby, provided that features in the opFeatureSelection are cached (are they?) the
        features would not have to be recalculated for each feature set.'''
        self._xysliceID = -1

        self._initialized_all_features_segmentation_layer = False
        self._initialized_current_features_segmentation_layer = False

        self._selected_feature_set_id = None
        self.selected_features_matrix = None
        self.feature_channel_names = None #this gets initialized when the matrix is set to all features in _run_selection

        self._stackdim = self.opPixelClassification.InputImages.meta.shape

        self.__selection_methods = {
            0: "gini",
            1: "filter",
            2: "wrapper"
        }

        self._selection_params = {
            "num_of_feat": 0,
            "c": 0.1
        }
        self._selection_method = "None"
        self._gui_initialized = False #  is set to true once gui is initialized, prevents multiple initialization
        self._feature_selection_results = []

        self.colortable = colortables.default16
        self.layerstack = layerwidget.LayerStackModel()

        # this initializes the actual GUI
        self._init_gui()

        # set default parameter values
        self.number_of_feat_box.setValue(self._selection_params["num_of_feat"])
        self.spinbox_c_widget.setValue(self._selection_params["c"])

        # connect functionality
        self.cancel_button.clicked.connect(self.reject)
        self.select_set_button.clicked.connect(self.accept)
        self.select_method_cbox.currentIndexChanged.connect(self._handle_selected_method_changed)
        self.spinbox_c_widget.valueChanged.connect(self._update_parameters)
        self.number_of_feat_box.valueChanged.connect(self._update_parameters)
        self.run_button.clicked.connect(self._run_selection)
        self.all_feature_sets_combo_box.currentIndexChanged.connect(self._handle_selected_feature_set_changed)

        # make sure internal variable are in sync with gui
        self._handle_selected_method_changed()
        self._update_parameters()

        self.resize(1366, 768)

    def exec_(self):
        '''
        as explained in the __init__, we only display one slice of the datastack. Here we find out which slice is
        '''
        # currently being viewed in ilastik
        ilastik_editor = self.opPixelClassification.parent.pcApplet.getMultiLaneGui().currentGui().editor
        ilastik_currentslicing = ilastik_editor.posModel.slicingPos
        self._ilastik_currentslicing_5D = ilastik_editor.posModel.slicingPos5D
        current_view = ilastik_editor.imageViews[2]
        current_viewport_rect = current_view.viewportRect().getRect()

        if len(self._stackdim) > 3:
            self._bbox_lower = [np.max([int(current_viewport_rect[0]), 0]), np.max([int(current_viewport_rect[1]), 0])]
            self._bbox_upper = [np.min([int(current_viewport_rect[0] + current_viewport_rect[2]), self._stackdim[1]]),
                          np.min([int(current_viewport_rect[1] + current_viewport_rect[3]), self._stackdim[2]])]
        else:
            self._bbox_lower = [np.max([int(current_viewport_rect[0]), 0]), np.max([int(current_viewport_rect[1]), 0])]
            self._bbox_upper = [np.min([int(current_viewport_rect[0] + current_viewport_rect[2]), self._stackdim[0]]),
                          np.min([int(current_viewport_rect[1] + current_viewport_rect[3]), self._stackdim[1]])]


        self.reset_me()

        # retrieve raw data of current slice and add it to the layerstack
        self._xysliceID = ilastik_currentslicing[-1]

        # remove segmentation layers and feature sets (maybe not optimal, room for improvement here)
        if len(self._stackdim) == 5:
            self.raw_xy_slice = np.squeeze(self.opPixelClassification.InputImages[self._ilastik_currentslicing_5D[0],
                                           self._bbox_lower[0]:self._bbox_upper[0],
                                           self._bbox_lower[1]:self._bbox_upper[1],
                                           self._xysliceID, :].wait())
        elif len(self._stackdim) == 4:
            self.raw_xy_slice = np.squeeze(self.opPixelClassification.InputImages[self._bbox_lower[0]:self._bbox_upper[0],
                                           self._bbox_lower[1]:self._bbox_upper[1], self._xysliceID, :].wait())
        elif len(self._stackdim) == 3:
             self.raw_xy_slice = np.squeeze(self.opPixelClassification.InputImages[self._bbox_lower[0]:self._bbox_upper[0],
                                           self._bbox_lower[1]:self._bbox_upper[1], :].wait())
        else:
            raise Exception

        axistags = self.opFeatureSelection.InputImage.meta['axistags']
        color_index = axistags.index('c')
        if self._stackdim[color_index] > 1:
            self._add_color_layer(self.raw_xy_slice, "raw_data", True)
        else:
            self._add_grayscale_layer(self.raw_xy_slice, "raw_data", True)


        # now launch the dialog
        super(FeatureSelectionDialog, self).exec_()

    def reset_me(self):
        '''
        this deletes everything from the layerstack
        '''
        while(self.layerstack.removeRow(0)):
            pass
        for i in range(len(self._feature_selection_results)):
            self.all_feature_sets_combo_box.removeItem(0)
        # reset feature sets
        self._feature_selection_results = []
        self._initialized_all_features_segmentation_layer = False
        self._initialized_current_features_segmentation_layer = False
        self._initialized_feature_matrix = False
        self.all_feature_sets_combo_box.resetInputContext()
        self._selected_feature_set_id = None

    def _init_gui(self):
        if not self._gui_initialized:
            ###################
            # Layer Widget (displays all available layers and lets the user change their visibility)
            ###################
            self.layer_widget = layerwidget.LayerWidget()
            self.layer_widget.init(self.layerstack)

            ###################
            # Instantiation of the volumeEditor (+ widget)
            ###################
            self.editor = volumeEditorWidget.VolumeEditor(self.layerstack, parent=self)
            self.viewer = volumeEditorWidget.VolumeEditorWidget()
            self.viewer.init(self.editor)

            ###################
            # This section constructs the GUI elements that are displayed on the left side of the window
            ###################
            left_side_panel = QtGui.QListWidget()
            left_side_layout = QtGui.QVBoxLayout()
            method_label = QtGui.QLabel("Feature Selection Method")

            # combo box for selecting desired feature selection method
            self.select_method_cbox = QtGui.QComboBox()
            self.select_method_cbox.addItem("Gini Importance (quick & dirty)")
            self.select_method_cbox.addItem("Filter Method (recommended)")
            self.select_method_cbox.addItem("Wrapper Method (slow but good)")
            self.select_method_cbox.setCurrentIndex(1)


            # number of selected features
            # create a widget containing 2 child widgets in a horizontal layout
            # child widgets: QLabel for text and QSpinBox for selecting an integer value for number of features
            self.number_of_features_selection_widget = QtGui.QWidget()

            text_number_of_feat = QtGui.QLabel("Number of Features (0=auto)")
            self.number_of_feat_box = QtGui.QSpinBox()

            number_of_features_selction_layout = QtGui.QHBoxLayout()
            number_of_features_selction_layout.addWidget(text_number_of_feat)
            number_of_features_selction_layout.addWidget(self.number_of_feat_box)

            self.number_of_features_selection_widget.setLayout(number_of_features_selction_layout)


            # regularization parameter for wrapper
            # create a widget containing 2 child widgets in a horizontal layout
            # child widgets: QLabel for text and QDoubleSpinBox for selecting a float value for c (parameter)
            self.c_widget = QtGui.QWidget()

            text_c_widget = QtGui.QLabel("Set Size Penalty") # not a good text
            self.spinbox_c_widget = QtGui.QDoubleSpinBox()
            # may have to set increment to 0.01
            self.spinbox_c_widget.setSingleStep(0.03)

            c_widget_layout = QtGui.QHBoxLayout()
            c_widget_layout.addWidget(text_c_widget)
            c_widget_layout.addWidget(self.spinbox_c_widget)

            self.c_widget.setLayout(c_widget_layout)

            # run button
            self.run_button = QtGui.QPushButton("Run Feature Selection")


            # text box with explanations
            text_box = QtGui.QTextEdit()
            text_box.setReadOnly(True)
            text_box.setText("<html><b>1) Select the desired feature selection method</b><br>" +
                             "- Gini Importance: inaccurate but fast<br>" +
                             "- Filter Method: recommended<br>" +
                             "- Wrapper Method: slow but provides the best results<br><br>" +
                             "<b>2) Choose the parameters</b><br>" +
                             "- choose <u>number of features</u>: we recommend number of features = 0 (if applicable)<br><br>" +
                             "- choose <u>c</u>: <br>small c (&lt; 0.1): excellent accuracy but larger feature set (=slower predictions) <br>larger c (&gt; 0.1): slightly reduced accuracy but smaller feature set (=faster predictions)<br><br>" +
                             "<b>3) More feature sets</b><br>" +
                             "add as many feature sets (with different parameters) as you like<br><br>" +
                             "<b>4) Compare feature Sets</b><br>" +
                             "Use the viewer (middle) and the segmentation layers (right) to choose the best feature set<br><br>" +
                             "<b>5) Finish</b><br>" +
                             "Select the best set in the box at the bottom and hit 'Select Feature Set'<br><br>"
                             "<br>" +
                             "<b>Explanations:</b><br>" +
                             "<u>oob</u>: out of bag error (in &#37;), lower is better<br>" +
                             "<u>ctime</u>: feature computation time (in seconds), lower is better<br><br>" +
                             "If the segmentation (shown in the viewer) differs a lot between the feature sets and the reference (usualls all features) but the oob values are similar then this is an indication that you should place more labels, especially in the regions where there were differences. Return to the feature selection once you added more labels</html>")

            # now add these widgets together to form the left_side_layout
            left_side_layout.addWidget(method_label)
            left_side_layout.addWidget(self.select_method_cbox)
            left_side_layout.addWidget(self.number_of_features_selection_widget)
            left_side_layout.addWidget(self.c_widget)
            left_side_layout.addWidget(self.run_button)
            left_side_layout.addWidget(text_box)
            left_side_layout.setStretchFactor(text_box, 1)
            # left_side_layout.addStretch(1)
            # assign that layout to the left side widget
            left_side_panel.setLayout(left_side_layout)

            ###################
            # The three widgets create above (left_side_panel, viewer, layerWidget) are now collected into one single
            # widget (centralWidget)
            ###################
            upper_widget_layout = QtGui.QHBoxLayout()
            upper_widget = QtGui.QWidget()

            upper_widget_layout.addWidget(left_side_panel)
            upper_widget_layout.addWidget(self.viewer)
            upper_widget_layout.addWidget(self.layer_widget)

            # make sure the volume viewer gets more space
            upper_widget_layout.setStretchFactor(self.viewer, 8)
            upper_widget_layout.setStretchFactor(left_side_panel, 3)
            upper_widget_layout.setStretchFactor(self.layer_widget, 3)

            upper_widget.setLayout(upper_widget_layout)

            ###################
            # Add 2 buttons and a combo box to the bottom (combo box is used to select feature set, one button for accepting
            # the new set, one for canceling)
            ###################
            self.all_feature_sets_combo_box = QtGui.QComboBox()
            self.all_feature_sets_combo_box.resize(500, 100)
            self.select_set_button = QtGui.QPushButton("Select Feature Set")
            self.cancel_button = QtGui.QPushButton("Cancel")
            show_features_of_selected_set = QtGui.QPushButton("Show Feature Names")
            show_features_of_selected_set.clicked.connect(self._show_feature_name_dialog)

            bottom_widget = QtGui.QWidget()
            bottom_layout = QtGui.QHBoxLayout()
            # bottom_layout.addWidget(self.current_status_label)
            #bottom_layout.addStretch(1)
            bottom_layout.addWidget(self.all_feature_sets_combo_box)
            bottom_layout.addWidget(show_features_of_selected_set)
            bottom_layout.addWidget(self.select_set_button)
            bottom_layout.addWidget(self.cancel_button)

            # bottom_layout.setStretchFactor(self.current_status_label, 1)
            bottom_layout.setStretchFactor(self.all_feature_sets_combo_box, 4)
            bottom_layout.setStretchFactor(show_features_of_selected_set, 1)
            bottom_layout.setStretchFactor(self.select_set_button, 2)
            bottom_layout.setStretchFactor(self.cancel_button, 2)

            bottom_widget.setLayout(bottom_layout)


            central_widget_layout = QtGui.QVBoxLayout()
            central_widget_layout.addWidget(upper_widget)
            central_widget_layout.addWidget(bottom_widget)

            central_widget = QtGui.QWidget()
            central_widget.setLayout(central_widget_layout)

            self.setLayout(central_widget_layout)
            self.setWindowTitle("Feature Selection")

            self._gui_initialized = True

    def _show_feature_name_dialog(self):
        dialog = QtGui.QDialog()
        dialog.resize(350, 650)

        ok_button = QtGui.QPushButton("ok")
        ok_button.clicked.connect(dialog.accept)

        text_edit = QtGui.QTextEdit()
        text_edit.setReadOnly(True)

        layout = QtGui.QVBoxLayout()
        layout.addWidget(text_edit)
        layout.addWidget(ok_button)

        layout.setStretchFactor(text_edit, 1)

        dialog.setLayout(layout)

        if self._selected_feature_set_id is None:
            text_edit.setText("No feature set selected!")
        else:
            selected_ids = np.sort(self._feature_selection_results[self._selected_feature_set_id].feature_ids)
            text = "<html>"

            for id in selected_ids:
                this_channel_name = self.feature_channel_names[id]
                this_channel_name = this_channel_name.replace("\xcf\x83", "&sigma;")
                text += this_channel_name + "<br>"
            text += "</html>"
            text_edit.setText(text)

        dialog.exec_()

    def _add_color_layer(self, data, name=None, visible=False):
        '''
        adds a color layer to the layerstack

        :param data: numpy array (2D, c) containing the data (c is color)
        :param name: name of layer
        :param visible: bool determining whether this layer should be set to visible
        :return:
        '''
        assert len(data.shape) == 3
        data_sources = []
        for i in range(data.shape[2]):
            a, data_shape = createDataSource(data[:,:,i], True)
            data_sources.append(a)
        self.editor.dataShape = list(data_shape)
        if data.shape[2] == 3:
            new_layer = RGBALayer(data_sources[0], data_sources[1], data_sources[2])
        elif data.shape[2] == 4:
            new_layer = RGBALayer(data_sources[0], data_sources[1], data_sources[2], data_sources[3])
        else:
            raise Exception("Unexpected number of colors")

        new_layer.visible = visible
        if name is not None:
            new_layer.name = name
        self.layerstack.append(new_layer)


    def _handle_selected_feature_set_changed(self):
        '''
        If the user selects a specific feature set in the comboBox in the bottom row then the segmentation of this
        feature set will be displayed in the viewer
        '''

        id = self.all_feature_sets_combo_box.currentIndex()
        for i, layer in enumerate(self.layerstack):
            layer.visible = (i == id)
            layer.opacity = 1.
        self._selected_feature_set_id = id
        self.selected_features_matrix = self._feature_selection_results[id].feature_matrix

    def _add_feature_set_to_results(self, feature_set_result):
        '''
        After feature selection, the feature set (and the segmentation achieved with it) will be added to the results
        :param feature_set_result: FeatureSelectionResult instance
        '''
        self._feature_selection_results.insert(0, feature_set_result)
        self._add_segmentation_layer(feature_set_result.segmentation, name=feature_set_result.name)
        self.all_feature_sets_combo_box.insertItem(0, feature_set_result.name)

    def _update_parameters(self):
        self._selection_params["num_of_feat"] = self.number_of_feat_box.value()
        self._selection_params["c"] = self.spinbox_c_widget.value()
        self._update_gui()

    def _update_gui(self):
        '''
        Depending on feature selection method and the number of features in the set some GUI elements are
        enabled/disabled
        '''
        if (self.select_method_cbox.currentIndex() == 0) | (self.select_method_cbox.currentIndex() == 1):
            self.c_widget.setEnabled(False)
            self.number_of_features_selection_widget.setEnabled(True)
        else:
            self.c_widget.setEnabled(True)
            self.number_of_features_selection_widget.setEnabled(False)
        if self.number_of_feat_box.value() == 0:
            self.c_widget.setEnabled(True)

    def _add_segmentation_layer(self, data, name=None, visible=False):
        '''
        adds a segementation layer to the layerstack

        :param data: numpy array (2D) containing the data
        :param name: name of layer
        :param visible: bool determining whether this layer should be set to visible
        :return:
        '''
        assert len(data.shape) == 2
        a, data_shape = createDataSource(data, True)
        self.editor.dataShape = list(data_shape)
        new_layer = ColortableLayer(a, self.colortable)
        new_layer.visible = visible
        new_layer.opacity = 0.5
        if name is not None:
            new_layer.name = name
        self.layerstack.append(new_layer)

    def _add_grayscale_layer(self, data, name=None, visible=False):
        '''
        adds a grayscale layer to the layerstack

        :param data: numpy array (2D) containing the data
        :param name: name of layer
        :param visible: bool determining whether this layer should be set to visible
        :return:
        '''
        assert len(data.shape) == 2
        a, data_shape = createDataSource(data, True)
        self.editor.dataShape = list(data_shape)
        new_layer = GrayscaleLayer(a)
        new_layer.visible = visible
        if name is not None:
            new_layer.name = name
        self.layerstack.append(new_layer)

    def _handle_selected_method_changed(self):
        '''
        activated upon changing the feature selection method
        '''
        self._selection_method = self.__selection_methods[self.select_method_cbox.currentIndex()]
        self._update_gui()

    def retrieve_segmentation(self, feat_matrix):
        '''
        Uses the features of the feat_matrix to retrieve a segmentation of the currently visible slice
        :param feat_matrix: boolean feature matrix as in opFeatureSelection.SelectionMatrix
        :return: segmentation (2d numpy array), out of bag error
        '''
        # remember the currently selected features so that they are not changed in case the user cancels the dialog
        user_defined_matrix = self.opFeatureSelection.SelectionMatrix.value

        # apply new feature matrix and make sure lazyflow applies the changes
        if np.sum(user_defined_matrix != feat_matrix) != 0:
            self.opFeatureSelection.SelectionMatrix.setValue(feat_matrix)
            self.opFeatureSelection.SelectionMatrix.setDirty() # this does not do anything!?!?
            self.opFeatureSelection.setupOutputs()
            # self.opFeatureSelection.change_feature_cache_size()

        start_time = times()[4]

        old_freeze_prediction_value = self.opPixelClassification.FreezePredictions.value
        self.opPixelClassification.FreezePredictions.setValue(False)

        # retrieve segmentation layer(s)
        slice_shape = self.raw_xy_slice.shape[:2]
        segmentation = np.zeros(slice_shape)

        for i, seglayer in enumerate(self.opPixelClassification.SegmentationChannels):
            if len(self._stackdim) == 5:
                single_layer_of_segmentation = np.squeeze(seglayer[self._ilastik_currentslicing_5D[0],
                                                          self._bbox_lower[0]:self._bbox_upper[0],
                                                          self._bbox_lower[1]:self._bbox_upper[1],
                                                          self._xysliceID, 0].wait())
            elif len(self._stackdim) == 4:
                single_layer_of_segmentation = np.squeeze(seglayer[self._bbox_lower[0]:self._bbox_upper[0],
                                                          self._bbox_lower[1]:self._bbox_upper[1],
                                                          self._xysliceID, 0].wait())
            elif len(self._stackdim) == 3:
                single_layer_of_segmentation = np.squeeze(seglayer[self._bbox_lower[0]:self._bbox_upper[0],
                                                        self._bbox_lower[1]:self._bbox_upper[1],
                                                        0].wait())
            else:
                raise Exception
            segmentation[single_layer_of_segmentation != 0] = i

        end_time = times()[4]

        oob_err = 100. * np.mean(self.opPixelClassification.opTrain.outputs['Classifier'].value.oobs)

        # revert changes to matrix and other operators
        if np.sum(user_defined_matrix != feat_matrix) != 0:
            self.opFeatureSelection.SelectionMatrix.setValue(user_defined_matrix)
            self.opFeatureSelection.SelectionMatrix.setDirty() # this does not do anything!?!?
            self.opFeatureSelection.setupOutputs()

        self.opPixelClassification.FreezePredictions.setValue(old_freeze_prediction_value)

        return segmentation, oob_err, end_time-start_time

    def retrieve_segmentation_new(self, feat):
        '''
        Attempt to use the opSimplePixelClassification by Stuart. Could not get this to work so far...
        :param feat:
        :return:
        '''
        import opSimplePixelClassification
        from lazyflow import graph
        from lazyflow.classifiers import ParallelVigraRfLazyflowClassifierFactory

        self.opSimpleClassification = opSimplePixelClassification.OpSimplePixelClassification(parent = self.opPixelClassification.parent.pcApplet.topLevelOperator)
        self.opSimpleClassification.Labels.connect(self.opPixelClassification.opLabelPipeline.Output)
        self.opSimpleClassification.Features.connect(self.opPixelClassification.FeatureImages)
        self.opSimpleClassification.Labels.resize(1)
        self.opSimpleClassification.Features.resize(1)
        self.opSimpleClassification.ingest_labels()
        self.opSimpleClassification.ClassifierFactory.setValue(ParallelVigraRfLazyflowClassifierFactory(100))

        # resize of input slots required, otherwise "IndexError: list index out of range" after this line
        segmentation = self.opSimpleClassification.Predictions[0][0, :, :, 25, 0].wait()

        # now I get:
        '''RuntimeError:
        Precondition violation!
        Sampler(): Requested sample count must be at least as large as the number of strata.
        (/miniconda/conda-bld/work/include/vigra/sampling.hxx:371)'''


        '''
        In [72]: self.opSimpleClassification.Predictions[0].meta.shape
        Out[72]: (1, 300, 275, 50, 1)
        '''


    def _convert_featureIDs_to_featureMatrix(self, selected_feature_IDs):
        '''
        The feature Selection Operators return id's of selected features. Here, these IDs are converted to fit the
        feature matrix as in opFeatureSelection.SelectionMatrix

        :param selected_feature_IDs: lift of selected feature ids
        :return: feature matrix for opFeatureSelection
        '''
        feature_channel_names = self.opPixelClassification.FeatureImages.meta['channel_names']
        scales = self.opFeatureSelection.Scales.value
        featureIDs = self.opFeatureSelection.FeatureIds.value
        new_matrix = np.zeros((len(featureIDs), len(scales)), 'bool')  # initialize new matrix as all False

        # now find out where i need to make changes in the matrix
        # matrix is len(features) by len(scales)
        for feature in selected_feature_IDs:
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

        return new_matrix

    def _convert_featureMatrix_to_featureIDs(self, feature_matrix):
        feature_channel_names = self.opPixelClassification.FeatureImages.meta['channel_names']
        feature_ids = ["Gaussian Smoothing", "Laplacian of Gaussian", "Gaussian Gradient Magnitude",
                       "Difference of Gaussians", "Structure Tensor Eigenvalues", "Hessian of Gaussian Eigenvalues"]
        scales = self.opFeatureSelection.Scales.value
        featureIDs = self.opFeatureSelection.FeatureIds.value

        ids = []

        for i in range(feature_matrix.shape[0]):
            for j in range(feature_matrix.shape[1]):
                if feature_matrix[i, j]:
                    id = feature_ids[i]
                    scale = scales[j]
                    for k in range(len(feature_channel_names)):
                        m1 = re.findall(id, feature_channel_names[k])
                        m2 = re.findall(str(scale), feature_channel_names[k])
                        if (len(m1) > 0) & (len(m2) > 0):
                            ids += [k]


        return ids

    def _auto_select_num_features(self, feature_order):
        '''
        Determines the optimal number of features. This is achieved by sequentially adding features from the
        feature_order to the list and comparing the accuracies achieved with the growing feature sets. These accuracies
        are penalized by the feature set size ('accuracy - size trade-off' from GUI) to prevent the set size from
        becoming too large with too little accuracy benefit
        ToDO: This should actually use the opTrain of Ilastik

        :param feature_order: ordered list of feature IDs
        :return: optimal number of selected features
        '''
        from sklearn.ensemble import RandomForestClassifier
        from ilastik_feature_selection.wrapper_feature_selection import EvaluationFunction


        feature_order = np.array(feature_order)

        rf = RandomForestClassifier(n_jobs=-1, n_estimators=255)
        ev_func = EvaluationFunction(rf, complexity_penalty=self._selection_params["c"])
        n_select = 1
        overshoot = 0
        score = 0.
        X = self.featureLabelMatrix_all_features[:, 1:]
        Y = self.featureLabelMatrix_all_features[:, 0]
        n_select_opt = n_select

        while (overshoot < 3) & (n_select < self.n_features):
            score_old = score
            score = ev_func.evaluate_feature_set_size_penalty(X, Y, None, feature_order[:n_select])

            if score > score_old:
                n_select_opt = n_select
                overshoot = 0
            else:
                overshoot += 1

            n_select += 1

        return n_select_opt

    def _run_selection(self):
        QtGui.QApplication.instance().setOverrideCursor( QtGui.QCursor(QtCore.Qt.WaitCursor) )
        '''
        runs the feature selection based on the selected parameters and selection method. Adds a segmentation layer
        showing the segmentation result achieved with the selected set
        '''
        # self.retrieve_segmentation_new(None)

        user_defined_matrix = self.opFeatureSelection.SelectionMatrix.value

        if not self._initialized_current_features_segmentation_layer:
            self.opFeatureSelection.setupOutputs()  # deletes cache for realistic feature computation time
            segmentation_current_features, oob_user, time_user = self.retrieve_segmentation(user_defined_matrix)
            selected_ids = self._convert_featureMatrix_to_featureIDs(user_defined_matrix)
            current_features_result = FeatureSelectionResult(user_defined_matrix,
                                                             selected_ids,
                                                             segmentation_current_features,
                                                             {'num_of_feat': 'user', 'c': 'None'},
                                                             'user_features', oob_user, time_user)
            self._add_feature_set_to_results(current_features_result)
            self._initialized_current_features_segmentation_layer = True

        all_features_active_matrix = np.zeros(user_defined_matrix.shape, 'bool')
        all_features_active_matrix[:, 1:] = True
        all_features_active_matrix[0, 0] = True
        all_features_active_matrix[1:, 0] = False # do not use any other feature than gauss smooth on sigma=0.3
        self.opFeatureSelection.SelectionMatrix.setValue(all_features_active_matrix)
        self.opFeatureSelection.SelectionMatrix.setDirty() # this does not do anything!?!?
        self.opFeatureSelection.setupOutputs()
        # self.opFeatureSelection.change_feature_cache_size()
        self.feature_channel_names = self.opPixelClassification.FeatureImages.meta['channel_names']

        '''
        Here we retrieve the labels and feature matrix of all features. This is done only once each time the
        FeatureSelectionDialog is opened.

        Reason for not connecting the feature selection operators to the ilastik lazyflow graph:
        Whenever we are retrieving a new segmentation layer of a new feature set we are overriding the SelectionMatrix
        of the opFeatureSelection. If we then wanted to find another feature set, the feature selection operators would
        request the features and label matrix again. In the meantime, the feature set has been changed and changed back,
        however, resulting in the featureLabelMatrix to be dirty. Therefore it would have to be recalculated whenever we
        are requesting a new feature set. The way this is prevented here is by simply retrieving the FeatureLabelMatrix
        once each time the dialog is opened and manually writing it into the inputSlot of the feature selection
        operators. This is possible because the FeatureLabelMatrix cannot change from within the FeatureSelectionDialog
        (it contians feature values and the corresponding labels of all labeled voxels and all features. The labels
        cannot be modified from within this dialog)
        '''
        if not self._initialized_feature_matrix:
            self.featureLabelMatrix_all_features = self.opFeatureMatrixCaches.LabelAndFeatureMatrix.value
            self.opFilterFeatureSelection.FeatureLabelMatrix.setValue(self.featureLabelMatrix_all_features)
            self.opFilterFeatureSelection.FeatureLabelMatrix.resize(1)
            self.opFilterFeatureSelection.setupOutputs()
            self.opWrapperFeatureSelection.FeatureLabelMatrix.setValue(self.featureLabelMatrix_all_features)
            self.opWrapperFeatureSelection.FeatureLabelMatrix.resize(1)
            self.opWrapperFeatureSelection.setupOutputs()
            self.opGiniFeatureSelection.FeatureLabelMatrix.setValue(self.featureLabelMatrix_all_features)
            self.opGiniFeatureSelection.FeatureLabelMatrix.resize(1)
            self.opGiniFeatureSelection.setupOutputs()
            self._initialized_feature_matrix = True
            self.n_features = self.featureLabelMatrix_all_features.shape[1] - 1

        if not self._initialized_all_features_segmentation_layer:
            if np.sum(all_features_active_matrix != user_defined_matrix) != 0:
                segmentation_all_features, oob_all, time_all = self.retrieve_segmentation(all_features_active_matrix)
                selected_ids = self._convert_featureMatrix_to_featureIDs(all_features_active_matrix)
                all_features_result = FeatureSelectionResult(all_features_active_matrix,
                                                             selected_ids,
                                                 segmentation_all_features,
                                                 {'num_of_feat': 'all', 'c': 'None'},
                                                 'all_features', oob_all, time_all)
                self._add_feature_set_to_results(all_features_result)
            self._initialized_all_features_segmentation_layer = True

        # run feature selection using the chosen parameters
        if self._selection_method == "gini":
            if self._selection_params["num_of_feat"] == 0:
                self.opGiniFeatureSelection.NumberOfSelectedFeatures.setValue(self.n_features)
                selected_feature_ids = self.opGiniFeatureSelection.SelectedFeatureIDs.value

                # now decide how many features you would like to use
                # features are ordered by their gini importance
                n_selected = self._auto_select_num_features(selected_feature_ids)
                selected_feature_ids = selected_feature_ids[:n_selected]
            else:
                # make sure no more than n_features are requested
                self.opGiniFeatureSelection.NumberOfSelectedFeatures.setValue(np.min([self._selection_params["num_of_feat"], self.n_features]))
                selected_feature_ids = self.opGiniFeatureSelection.SelectedFeatureIDs.value
        elif self._selection_method == "filter":
            if self._selection_params["num_of_feat"] == 0:
                self.opFilterFeatureSelection.NumberOfSelectedFeatures.setValue(self.n_features)
                selected_feature_ids = self.opFilterFeatureSelection.SelectedFeatureIDs.value

                # now decide how many features you would like to use
                # features are ordered
                n_selected = self._auto_select_num_features(selected_feature_ids)
                selected_feature_ids = selected_feature_ids[:n_selected]
            else:
                # make sure no more than n_features are requested
                self.opFilterFeatureSelection.NumberOfSelectedFeatures.setValue(np.min([self._selection_params["num_of_feat"], self.n_features]))
                selected_feature_ids = self.opFilterFeatureSelection.SelectedFeatureIDs.value
        else:
            self.opWrapperFeatureSelection.ComplexityPenalty.setValue(self._selection_params["c"])
            selected_feature_ids = self.opWrapperFeatureSelection.SelectedFeatureIDs.value

        # create a new layer for display in the volumina viewer
        # make sure to save the feature matrix used to obtain it
        # maybe also write down feature computation time and oob error
        new_matrix = self._convert_featureIDs_to_featureMatrix(selected_feature_ids)
        new_segmentation, new_oob, new_time = self.retrieve_segmentation(new_matrix)
        new_feature_selection_result = FeatureSelectionResult(new_matrix,
                                                              selected_feature_ids,
                                                              new_segmentation,
                                                              self._selection_params,
                                                              self._selection_method,
                                                              oob_err=new_oob,
                                                              feature_calc_time=new_time)
        self._add_feature_set_to_results(new_feature_selection_result)

        # revert changes to matrix
        self.opFeatureSelection.SelectionMatrix.setValue(user_defined_matrix)
        self.opFeatureSelection.SelectionMatrix.setDirty() # this does not do anything!?!?
        self.opFeatureSelection.setupOutputs()
        QtGui.QApplication.instance().restoreOverrideCursor()


## Start Qt event loop unless running in interactive mode.
if __name__ == '__main__':
    #import sys
    #if (sys.flags.interactive != 1) or not hasattr(QtCore, 'PYQT_VERSION'):
    #    QtGui.QApplication.instance().exec_()
    app = QtGui.QApplication([])
    win = QtGui.QMainWindow()
    win.resize(800, 800)

    feat_dial = FeatureSelectionDialog()
    button = QtGui.QPushButton("open feature selection dialog")
    button.clicked.connect(feat_dial.show)

    central_widget = QtGui.QWidget()
    layout2 = QtGui.QHBoxLayout()
    layout2.addWidget(button)

    central_widget.setLayout(layout2)
    win.setCentralWidget(central_widget)

    win.show()
    QtGui.QApplication.instance().exec_()