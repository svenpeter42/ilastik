# to ensure that plugin system is available
from ilastik.plugins import pluginManager

import logging
logger = logging.getLogger(__name__)

from objectClassificationWorkflow import \
    ObjectClassificationWorkflowPixel, \
    ObjectClassificationWorkflowBinary, \
    ObjectClassificationWorkflowPrediction

try:
    from objectClassificationWorkflow import ObjectClassificationWorkflowGraphcut
except ImportError as e:
    logger.warn("Failed to import object workflow; check dependencies: " + str(e))
