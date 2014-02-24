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