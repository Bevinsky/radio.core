import config
import os
import logging
from threading import Thread, Event, RLock
from Queue import Empty, Queue

OKAY = 0
UNKNOWN_ERR = 1
START_ERR = 2
STOP_ERR = 3
NOTSUPPORTED_ERR = 4

logging.getLogger().setLevel(config.loglevel)
def get_logger(name=None):
    """returns a process safe logger, best set to the global variable
    'logging' when used in a separate process"""
    import logging
    import logging.handlers
    logger = logging.getLogger()
    try:
        logger.setLevel(config.loglevel)
    except (AttributeError):
        logger.setLevel(logging.INFO)
    if (not os.path.exists("./logs")):
        os.makedirs("./logs")
    handler = logging.handlers.RotatingFileHandler("./logs/{name}.log"\
                                         .format(name=name), maxBytes=5120,
                                         backupCount=5)
    logger.addHandler(handler)
    return logger
    
class Controller(Thread):
    """The controller of all the modules, should only be used from the public
    methods"""
    _loaded_modules = {} # Loaded mods
    _state_save = {} # For saving states
    def __init__(self):
        Thread.__init__(self)
        self.name = "Bootstrap Controller"
        self._alive = Event()
        self._queue = Queue()
        self._lock = RLock()
        logging.info("THREADING: Starting Bootstrap Controller")
        self.start()
    def run(self):
        self._processor()
        logging.info("THREADING: Stopping Bootstrap Controller")
    def load(self, name, **kwargs):
        """Load a module"""
        try:
            self._queue.put((0, name, kwargs))
        except:
            logging.exception("Don't do this you ass")
            
    def stop(self, name, **kwargs):
        """Stop a module"""
        try:
            self._queue.put((1, name, kwargs))
        except:
            logging.exception("Don't do this you ass")
            
    def stop_all(self):
        """Stops all modules"""
        try:
            self._queue.put((2, None, None))
        except:
            logging.exception("Don't do this you ass")
            
    def reload(self, name, **kwargs):
        """Reloads a module"""
        try:
            self._queue.put((3, name, kwargs))
        except:
            logging.exception("Don't do this you ass")
            
    def _processor(self):
        while not self._alive.is_set():
            try:
                id, name, kwargs = self._queue.get(timeout=2)
            except Empty:
                pass
            else:
                with self._lock:
                    try:
                        if (id == 0): # load
                            self._load(name, **kwargs)
                        elif (id == 1): # stop
                            self._stop(name, **kwargs)
                        elif (id == 2): # stop_all
                            self._stop_all()
                        else: # reload
                            self._reload(name, **kwargs)
                    except:
                        logging.exception("Controller engaged an exception")
                        
    def _load(self, name, **kwargs):
        """Internal method"""
        try:
            mod = __import__(name)
        except (ImportError):
            raise
        else:
            state = self._state_save.get(name, None)
            try:
                item = mod.start(state)
            except:
                # Something went derpiedoo, put it into the log instead of re-raising
                logging.exception("{name} failed to start".format(name=name))
                return START_ERR
            else:# Add return item because it can be the class we should use for cleaning
                self._loaded_modules[name] = (item, mod)
                return OKAY
        return UNKNOWN_ERR
    def _stop(self, name, **kwargs):
        """Internal method"""
        if (name in self._loaded_modules):
            obj, module = self._loaded_modules[name]
            if (hasattr(module, "shutdown")):
                callee = module.shutdown
            else:
                try:
                    callee = obj.shutdown
                except (AttributeError):
                    # Remove them since the module doesn't require cleanup
                    del self._loaded_modules[name]
                    return NOTSUPPORTED_ERR
            try:
                state = callee(**kwargs)
            except:
                # Put it into logging so it can be examined
                logging.exception("{name} failed to shutdown cleanly"\
                                  .format(name=name))
                return STOP_ERR
            else:
                self._state_save[name] = state
                try:
                    del self._loaded_modules[name]
                except (KeyError):
                    pass
                return OKAY
        else:
            return OKAY
    def _stop_all(self):
        """Internal method"""
        from copy import copy
        loaded_copy = copy(self._loaded_modules)
        for name in loaded_copy:
            kwargs = {}
            if (name == "afkstreamer"):
                kwargs = {"force": True}
            value = self._stop(name, **kwargs)
            if (value != OKAY):
                logging.error("Failed to cleanly stop {name}".format(name=name))
            else:
                logging.info("Stopped {name} correctly".format(name=name))
    
    def _reload(self, name, **kwargs):
        """Internal method"""
        obj = module = None
        if (name in self._loaded_modules):
            obj, module = self._loaded_modules[name]
        value = self._stop(name)
        if (module):
            module = reload(module)
        value = self._load(name)
        return value
    def count(self):
        return len(self._loaded_modules)
    def get(self, name):
        return self._loaded_modules.get(name, [None])[0]
    def shutdown(self):
        self.stop_all()
        self._alive.set()
        self.join()
    def stats(self):
        """Returns information about all things running currently,
        
        returns a tuple that contains the following:
            The amount of threads running
            The names of the threads running
            The amount of processes running
            The names of the processes running
            The amount of modules loaded
        """
        import threading, multiprocessing
        try:
            tnames = [thread.name for thread in threading.enumerate()]
            threads = threading.active_count()
            modules = len(self._loaded_modules)
            processes = len(multiprocessing.active_children())
            pnames = [process.name for process in multiprocessing.active_children()]
        except (AttributeError):
            tnames = []
            threads = 0
            modules = 0
            processes = 0
            pnames = []
        locations = ["afkstreamer", "requests"]
        for loc in locations:
            if (loc in self._loaded_modules):
                try:
                    result = self._loaded_modules[loc][0].stats()
                except (IndexError, AttributeError):
                    result = ([], 0)
                else:
                    tnames = tnames + result[0]
                    threads = threads + result[1]
        return (threads, tnames, processes, pnames, modules)
# Return values for various functions

