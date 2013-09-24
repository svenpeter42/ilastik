#===============================================================================
# Implements a mechanism to updte a graphic element from an operator and the other
# way round
#===============================================================================


from PyQt4 import QtCore,QtGui
from PyQt4.QtCore import QObject, QRect, QSize, pyqtSignal, QEvent, QPoint
from PyQt4.QtGui import QRubberBand,QRubberBand,qRed,QPalette,QBrush,QColor,QGraphicsColorizeEffect
from PyQt4 import uic
from PyQt4.QtCore import Qt, pyqtSlot,QTimer,SIGNAL
from PyQt4.QtGui import QMainWindow,QGraphicsRectItem
from PyQt4.QtGui import QApplication


from volumina.pixelpipeline.datasources import LazyflowSource
from volumina.api import Viewer
from volumina.layerstack import LayerStackModel
from volumina.layer import GrayscaleLayer,ColortableLayer
from volumina.colortables import jet

import numpy as np
import vigra

from lazyflow.operator import InputSlot
from lazyflow.graph import Operator, OutputSlot, Graph
from lazyflow.operators.generic import OpSubRegion


class MyGraphicsView(QtGui.QGraphicsView):
    #useful class for debug
    def __init__ (self,parent=None):
        super (MyGraphicsView, self).__init__ (parent)


    def mousePressEvent(self,  event):
        super(MyGraphicsView, self).mousePressEvent(event)
        itemUnderMouse = self.itemAt(event.pos())
        print "here",itemUnderMouse

        
def create_qt_default_env():
    from PyQt4.QtGui import QGraphicsScene,QGraphicsView,QApplication
    # 1 make the application
    app=QApplication([])
    # 2 then we need a main window to display stuff
    window=QMainWindow()
    # 3 then we a scene that we want to display
    scene=QGraphicsScene(0,0,400,400)
    
    # 4 view on the scene: open a widget on the main window which dispaly the scene
    view=MyGraphicsView(scene)
    window.setCentralWidget(view)
    #window.show()
    
    return app,window,view,scene


class Signaller(QObject):
    signalHasMoved = pyqtSignal()
    #signalIsMoving = pyqtSignal()



class ResizableRect(QGraphicsRectItem):
    hoverColor    = QColor(255, 0, 0)
    normalColor   = QColor(0, 0, 255)
    
    
    
    def __init__(self,x,y,h,w,scene):
        
        
        ##Note: need to do like this because the x,y of the graphics item fix the position 
        # of the zero relative to the scene
        QGraphicsRectItem.__init__(self,0,0,h,w,scene=scene)
        
        self.moveBy(x,y)
        
        self.height=h
        self.width=w
        
        self.Signaller=Signaller(parent=self.parentObject())
        self.setFlag(QtGui.QGraphicsItem.ItemIsMovable,True  )
        self.setFlag(QtGui.QGraphicsItem.ItemIsSelectable,True)
        self.setFlag(QtGui.QGraphicsItem.ItemSendsGeometryChanges ,True)
        
        self.setAcceptHoverEvents(True)
        self.hovering=False
        self.updateColor()
        #self.setAcceptedMouseButtons(QtCore.Qt.RightButton)
        #self.updateColor()
         
         
        self.textItem=QtGui.QGraphicsTextItem(QtCore.QString(""),parent=self)
        textItem=self.textItem
        
        
        
        
        #textItem.setParent(self.parentObject())
        
#         print textItem.pos().x(),textItem.pos().y()
#         print self.mapToScene(self.pos()).x()
#         print textItem.parent(),"KK",self
#         print textItem.scene(),"JJJ"
        #FIXME: make position data dependent
        textItem.setPos(QtCore.QPointF(0,0)) #upper left corner relative to the father        
        textItem.setDefaultTextColor(QColor(255, 255, 255))
        self.has_moved=False
        
    def hoverEnterEvent(self, event):
        event.setAccepted(True)
        self.hovering = True
        #elf.setCursor(QtCore.Qt.BlankCursor)
        #self.radius = self.radius # modified radius b/c hovering
        self.updateColor()
        super(ResizableRect,self)
  
    def hoverLeaveEvent(self, event):
        event.setAccepted(True)
        self.hovering = False
        #self.setCursor(CURSOR)
        #self.radius = self.radius # no longer hovering
        self.updateColor()
      
    def updateColor(self):
        
        color = self.hoverColor if self.hovering  else self.normalColor 
        
        
        self.setPen(QtGui.QPen(color,3))
        self.setBrush(QtGui.QBrush(color, QtCore.Qt.NoBrush))
    
    
    def dataPos(self):
        dataPos = self.scene().scene2data.map(self.scenePos())
        pos = [dataPos.x(), dataPos.y()]
        return pos 
    
        
    def mouseMoveEvent(self,event):
        pos=self.dataPos()
        
        
        
        self.has_moved=True
        super(ResizableRect, self).mouseMoveEvent(event)
        
        string=str(self.pos()).split("(")[1][:-1]
        
        #self.Signaller.signalIsMoving.emit()
#         dataPos = self.scene().scene2data.map(self.scenePos())
#         pos = [dataPos.x(), dataPos.y()]
        
        
        self.updateText("("+string+")"+" "+str(pos))
        
    def mouseDoubleClickEvent(self, event):
        print "DOUBLE CLICK ON NODE"
        #FIXME: Implement me
        event.accept()
    
    def updateText(self,string):
        self.textItem.setPlainText(QtCore.QString(string))
    
    
    def mouseReleaseEvent(self, event):
        
        if self.has_moved:
            self.Signaller.signalHasMoved.emit()
            #self.has_moved=False
        
            self.has_moved=False
        return QGraphicsRectItem.mouseReleaseEvent(self, event)
    
    def itemChange(self, change,value):
        if change==QGraphicsRectItem.ItemPositionChange:
            newPos=value.toPointF()
            rect = self.scene().sceneRect()

#             if not rect.contains(newPos):
#                 newPos.setX(min(rect.right(), max(newPos.x(), rect.left())))
#                 newPos.setY(min(rect.bottom(), max(newPos.y(), rect.top())))
#                 return newPos
#             
            #if not rect.contains(newPos2):
            #    newPos.setX(min(rect.right()-self.width, max(newPos.x()-self.width, rect.left())));
            #    newPos.setY(min(rect.bottom()-self.height, max(newPos.y()-self.height, rect.top())));
            #    return newPos
            if not rect.contains(value.toRectF()) :
                newPos.setX(min(rect.right()-self.width, max(newPos.x(), rect.left())));
                newPos.setY(min(rect.bottom()-self.height, max(newPos.y(), rect.top())));
                return newPos
            
        return QGraphicsRectItem.itemChange(self, change,value)



class OpSumAll(Operator):
    name = "SumRegion"
    description = ""

    #Inputs
    Input = InputSlot() 
   
    #Outputs
    Output = OutputSlot()
    
    
    def setupOutputs(self):
        inputSlot = self.inputs["Input"]
        self.Output.meta.shape = (1,)
        self.Output.meta.dtype = np.float
        self.Output.meta.axistags = None


    def execute(self, slot, subindex, roi, result):
        #key = roi.toSlice()
        arr = self.inputs["Input"][:].wait()
        result[:]=np.sum(arr)
        return result

    def propagateDirty(self, slot, subindex, roi):
        key = roi.toSlice()
        # Check for proper name because subclasses may define extra inputs.
        # (but decline to override notifyDirty)
        if slot.name == 'Input':
            self.outputs["Output"].setDirty(slice(None))
        else:
            # If some input we don't know about is dirty (i.e. we are subclassed by an operator with extra inputs),
            # then mark the entire output dirty.  This is the correct behavior for e.g. 'sigma' inputs.
            self.outputs["Output"].setDirty(slice(None))
    
            
    
    
class OpArrayPiper2(Operator):
    name = "ArrayPiper"
    description = "simple piping operator"

    #Inputs
    Input = InputSlot() 
   
    #Outputs
    Output = OutputSlot()

    def setupOutputs(self):
        inputSlot = self.inputs["Input"]
        self.outputs["Output"].meta.assignFrom(inputSlot.meta)

        self.Output.meta.axistags = vigra.AxisTags([vigra.AxisInfo("t"), vigra.AxisInfo("x"), vigra.AxisInfo("y"), vigra.AxisInfo("z"), vigra.AxisInfo("c")])

    def execute(self, slot, subindex, roi, result):
        key = roi.toSlice()
        req = self.inputs["Input"][key].writeInto(result)
        req.wait()
        return result

    def propagateDirty(self, slot, subindex, roi):
        key = roi.toSlice()
        # Check for proper name because subclasses may define extra inputs.
        # (but decline to override notifyDirty)
        if slot.name == 'Input':
            self.outputs["Output"].setDirty(key)
        else:
            # If some input we don't know about is dirty (i.e. we are subclassed by an operator with extra inputs),
            # then mark the entire output dirty.  This is the correct behavior for e.g. 'sigma' inputs.
            self.outputs["Output"].setDirty(slice(None))

    def setInSlot(self, slot, subindex, roi, value):
        # Forward to output
        assert subindex == ()
        assert slot == self.Input
        key = roi.toSlice()
        self.outputs["Output"][key] = value



if __name__=="__main__":

    #===========================================================================
    # Example of how to do the thing
    # we generate a dot at random position every 200 milliseconds
    # when the dot happen to be in the centre of the movable squere in the
    # image then we show a one on the top left corner
    #===========================================================================
        
        
    g = Graph()
        
    app = QApplication([])
    cron = QTimer()
    cron.start(200)
    
    
    op = OpArrayPiper2(graph=g) #Generate random noise
    opsub = OpSubRegion(graph=g) #Get the sum over a subregion of the random noise
    
    
    
    #opsub.Input.connect(op.Output)
    shape=(1,500,500,1,1)
    
    array = np.random.randint(0,255,500*500).reshape(shape).astype(np.uint8)
    op.Input.setValue(array)
    
    def do():
        #Generate 
        #array[:] = np.random.randint(0,255,500*500).reshape(shape).astype(np.uint8)
        a = np.zeros(500*500).reshape(500,500).astype(np.uint8)
        ii=np.random.randint(0,500,1)
        jj=np.random.randint(0,500,1)
        a[ii,jj]=1
        a=vigra.filters.discDilation(a,radius=20)
        array[:]=a.reshape(shape).view(np.ndarray)*255
        op.Input.setDirty()
    
    do()
    cron.connect(cron, SIGNAL('timeout()'), do)
    
    start=(0,50,50,0,0)
    stop=(1,100,100,1,1)
    opsub.Input.connect(op.Output)
    opsub.Start.setValue(start)
    opsub.Stop.setValue(stop)
    
    opsum=OpSumAll(graph=g)
    # print opsub.Output.meta.shape
    opsum.Input.connect(opsub.Output)
    
    
    # print "JJJJ", opsum.outputs["Output"][:].wait()
    # import time
    # time.sleep(1)
    # print "JJJJ", opsum.outputs["Output"][:].wait()
    # print 
    
#==========================================================================
# Show the random noise
#==========================================================================
     
     
    layerstack = LayerStackModel()
     
    ds = LazyflowSource( op.Output )
    layer = ColortableLayer(ds,jet())
    layerstack.append(layer)
     
    mainwin=Viewer()
    mainwin.dataShape=(1,500,500,1,1)
    mainwin.initLayerstackModel(layerstack)
     
     
    rect=ResizableRect(50,50,200,200,mainwin.editor.imageScenes[2])
    print rect.parentObject()
    #print "Here", opsum.outputs["Output"][:].wait()
    
    
    def printer():
    #     newstart=rect.dataPos()
    #     start=np.array((0,newstart[0],newstart[1],0,0))
    #     stop=np.array((1,newstart[0]+rect.width,newstart[1]+rect.height,1,1))
    #     opsub.Stop.setValue(stop)
    #     opsub.Start.setValue(start)
    #     
        print "Sum in the region", opsum.outputs["Output"][:].wait()
        
    
    
    #print when finished moving
    rect.Signaller.signalHasMoved.connect(printer)
    
    
    def updateTextWhenDataChanges(*args, **kw):
        newstart=rect.dataPos()
    
        start=(0,newstart[0],newstart[1],0,0)
        stop=(1,newstart[0]+rect.width,newstart[1]+rect.height,1,1)
        opsub.Start.disconnect()
        opsub.Stop.disconnect()
        
        opsub.Start.setValue(start)
        opsub.Stop.setValue(stop)
    
    
    
        sum= opsum.outputs["Output"][:].wait()[0]
        rect.updateText(str(sum/(sum+1e-16)))
    
    #Important part : when the underlying data changes whe notify directly the graphic element to 
    #update its value
    op.Output.notifyDirty(updateTextWhenDataChanges)
    
    mainwin.show()
     
    print mainwin.centralWidget()    
    app.exec_()
