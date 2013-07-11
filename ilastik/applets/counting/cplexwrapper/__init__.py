import os
currentdir = os.path.dirname(__file__) 
import ctypes
libraryname = "libcplexwrapper.so"
dllname = "cplexwrapper.dll"
dllabspath = os.path.dirname(os.path.abspath(__file__)) + os.path.sep + libraryname
extlib = ctypes.cdll.LoadLibrary(dllabspath)
