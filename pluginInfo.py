import weakref

class PluginInfo(object):
    """Meta Information for a Plugin
    """
    
    def __init__(self, key, name):
        self.key  = key   #unique key identifying this plugin
        self.name = name  #human readable short name of this plugin
        self.about = ""   #short paragraph describing this plugin
        
        #private:
        self._features = []
        
    @property
    def features(self):
        return self._features
       
    @features.setter
    def features(self, feat):
        self._features = []
        for f in feat:
            f.plugin = weakref.ref(self)
            self._features.append(f)
            
    def __len__(self):
        return len(self._features)
      