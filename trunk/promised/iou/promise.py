from __future__ import with_statement
import traceback
from functools import wraps
from collections import deque
from threading import RLock
from threading import Condition
from thread import allocate_lock
from contextlib import contextmanager
from result import AsynchronousResult

def promised(callable, promise):
    """
        Binds callable with promise, which will be 
        resolved or rejected based on callable's output 
        when invoked.
        
        @return: wrapper invokes 'callable' and completes 'promise'. 
        @note: use 'promises' when decorator is needed.  
    """
    @wraps(callable)
    def execute(*args, **kw):
        try:
            value = callable(*args, **kw)
        except Exception,error:
            promise.reject(error)
        else:
            promise.resolve(value)
    return execute

def promises(promise):
    """
        Decorator returns binds decorated with promise.
    """
    def executes(callable):
        return promised(callable, promise)
    return executes

class Promise(object):
    def __init__(self):
        # Strictly adhering to the _MINE
        # philosophy, even though it looks bad.
        self._dispatchers = deque()
        self._predispatchers = deque()
        self._postdispatchers = deque()
        self._synclock = allocate_lock()
        self._result = AsynchronousResult(self._synclock)
        super(Promise, self).__init__()
    def ready(self):
        """
            Is the promised result ready?
        """
        return self._result.ready()
    def pending(self):
        """
            Is the promised result still pending?
        """
        return not self.ready()
    def resolved(self):
        """
            Is the result ready, and was resolved (success)?
        """
        return self.ready() and self._result.successful()
    def rejected(self):
        """
            Is the result ready and rejected (failure)?
        """
        return self.ready() and not self._result.successful()
    def resolve(self, *value):
        """
            Complete promise with value from successful operation.
        """
        self._result.set(value, False)
        self._notify_attached_dispatchers()
    def reject(self, *error):
        """
            Complete promise with error from failed operation.
        """
        self._result.set(error, True)
        self._notify_attached_dispatchers()
    def get(self, timeout=15):
        """
            Get resolved promise's value, 
            or raise rejected promise's error.
        """
        return self._result.get(timeout)[0]
    def then(self, callback=None, errback=None, cbargs=(), ebargs=(), **kw):
        """
            Attach callback and/or errback handler to be invoked 
            with resolved promise's value or rejected promises 
            error, when available.
            
            @return: Promise instance for output of callback invocation.
            @note: Use returned Promise for callback chaining.
        """
        promise = Promise()
        def dispatcher(results, rejected=False):
            #==========================================================
            # Closure handles callback invocation and 
            # completes bound Promise instance with output.
            #==========================================================
            if rejected:
                args = ebargs
                handler = errback
            else:
                args = cbargs
                handler = callback
            try:
                if handler:
                    value = handler(*(results + args), **kw)
                else:
                    value = None
            except Exception,error:
                promise.reject(error)
            else:
                if isinstance(value, Promise):
                    value.then(promise.resolve, promise.reject)
                else:
                    promise.resolve(value)
        self._attach_dispatcher(dispatcher)
        # Promised output from callback invocation. 
        return promise
    def before(self, callback, *args, **kw):
        """
            Attach handler to be notified of Promise's completion, 
            regardless of whether resolved or rejected.
            
            Invokes:
                callback(self, *args, **kw)
            Where 'self' is the Promise instance itself.
            
            @note: invoked *before* registered callbacks and errbacks.   
            @note: after initial completion of Promise, callbacks 
            attached by 'before' differ from 'then' only by callback 
            signature.  They are invoked immediately, and the concept 
            of 'before'/'after' disappears.
        """
        promise = Promise()
        @promises(promise)
        def notify(*ignores):
            return callback(*args, **kw)
        self._attach_pre_dispatcher(notify)
        return promise
    def after(self, callback, *args, **kw):
        """
            Attach handler to be notified of Promise's completion, 
            regardless of whether resolved or rejected.
            
            Invokes:
                callback(self, *args, **kw)
            Where 'self' is the Promise instance itself.
            
            @note: invoked *after* registered callbacks and errbacks.
            @note: after initial completion of Promise, callbacks 
            attached by 'after' differ from 'then' only by callback 
            signature.  They are invoked immediately, and the concept 
            of 'before'/'after' disappears.    
        """
        promise = Promise()
        @promises(promise)
        def notify(*ignores):
            return callback(*args, **kw)
        self._attach_post_dispatcher(notify)
        return promise
    def when_resolved(self, callback, *args, **kw):
        """
            Register callback for resolved promise only.
        """
        return self.then(callback, None, args, (), **kw)
    def when_rejected(self, errback, *args, **kw):
        """
            Register error-handler for rejected promise only.
            
            Supports attaching additional args and kw.
        """
        @wraps(errback)
        def closure(result):
            return errback(result, *args, **kw)
        return self.then(None, closure)
    @contextmanager
    def resolution(self):
        """
            Boss-magic context-manager wraps operation that 
            sets promised result or raises rejection.  
            
            Raised error caught automatically rejects the promise.
            
            Usage:
                with result.resolution() as resolve:
                    resolve(operation(*args, **kw))
                
            @note: where 'result' is promised output of 'operation'.
            @note: there is no need to reject promise explicitly.
        """
        self._synclock.acquire()
        try:
            assert self.__pending()
            yield self.__setresult
        except Exception,error:
            self.__seterror(error)
        else:
            assert not self.__pending()
        finally:
            self._synclock.release()
        # This line does not execute iff assert not pending fails.
        # Otherwise it runs regardless of whether yield threw error.
        # Because operation is a contenxt-manager, there is no need 
        # re-raise any error explicitly.  They are automatically 
        # propagated back to exit point as long if we don't return True.
        # Dispatchers are notified automatically, but outside lock.
        self._notify_attached_dispatchers()
    def chained(self, callbacks):
        """
            Get Promise() for result of handling chain.
            Arguments may be callback or (callback,errback) item.
        """
        promise = self
        for handlers in callbacks:
            if not isinstance(handlers, (list,tuple)):
                handlers = (handlers,None)
            promise = promise.then(*handlers)
        return promise
    def __pending(self):
        return not self._result._ready._get()
    def __setresult(self, *value):
        self._result._set(value, False)
    def __seterror(self, *error):
        self._result._set(error, True)
    def _attach_dispatcher(self, dispatcher):
        with self._synclock:
            if self.__pending():
                self._dispatchers.append(dispatcher)
                return
        self._notify_dispatchers(dispatcher)
    def _attach_pre_dispatcher(self, dispatcher):
        with self._synclock:
            if self.__pending():
                self._predispatchers.append(dispatcher)
                return
        self._notify_dispatchers(dispatcher)
    def _attach_post_dispatcher(self, dispatcher):
        with self._synclock:
            if self.__pending():
                self._postdispatchers.append(dispatcher)
                return
        self._notify_dispatchers(dispatcher)
    def _notify_dispatchers(self, *dispatchers):
        results = self._result.value()
        rejected = self.rejected()
        for dispatch in dispatchers:
            dispatch(results, rejected)
        return
    def _notify_attached_dispatchers(self):
        """
            Handle notifying every dispatcher enqueued 
            of the promised result's value or error.
            
            Then notify all post-dispatchers that Promise 
            is completed.
            
            Replaces both attach-dispatcher methods with 
            dispatch method so that all future calls will 
            automatically be dispatched and not enqueued. 
        """
        dispatchers = []
        predispatchers = []
        postdispatchers = []
        with self._synclock:
            self._attach_pre_dispatcher = self._notify_dispatchers
            predispatchers.extend(self._predispatchers)
            self._predispatchers = ()
        if predispatchers:
            self._notify_dispatchers(*predispatchers)
        with self._synclock:
            self._attach_dispatcher = self._notify_dispatchers
            dispatchers.extend(self._dispatchers)
            self._dispatchers = ()
        if dispatchers:
            self._notify_dispatchers(*dispatchers)
        with self._synclock:
            self._attach_post_dispatcher = self._notify_dispatchers
            postdispatchers.extend(self._postdispatchers)
            self._postdispatchers = ()
        if postdispatchers:
            self._notify_dispatchers(*postdispatchers)
        return (len(predispatchers),len(dispatchers),len(postdispatchers))
    def __str__(self):
        return "%s(%s)" % (type(self).__name__, self._result)
    def __repr__(self):
        return "<%s object at %#x>" % (self, id(self))

def when(input, callback=None, errback=None, cbargs=(), ebargs=(), **kw):
    """
        Normalizes handling of result as input.
        
        Usage: 
            result = channel.read(1024)
            when(result, collector.feed)
            
        @note: handler 'callback.feed' will be invoked with 'input' 
        value, whether 'input' is promised value or actual value.
        @note: handler invoked immediately if 'input' is not Promise, 
        or 'input' is completed Promise.  
        @return: Promised output of callback handler, can be used to 
        get output regardless of whether 'input' is promise or value.
    """
    if isinstance(input, Promise):
        promise = input
    else:
        # Input is normal value (i.e., not eventual result), 
        # create new promise and complete with appropriate 
        # operation.
        promise = Promise()
        if isinstance(input, Exception):
            promise.reject(input)
        else:
            promise.resolve(input)
    # Return promised output of callback handler returned by 'then'.
    return promise.then(callback, errback, cbargs, ebargs, **kw)
