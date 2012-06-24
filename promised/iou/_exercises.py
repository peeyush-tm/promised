import time
from iou import promise
from iou.result import Result
from iou.result import AsynchronousResult

def returns(value):
    def invoke(*args):
        print "invoke%r -> %r" % (args, value)
        return value
    return invoke

def raises(error):
    def invoke(*args):
        print "raises%r -> %r" % (args, error)
        raise error
    return invoke

def callbacks(description="", cb=None, eb=None):
    def callback(*result):
        output = ", ".join([repr(item) for item in result])
        print "Callback[%r]: %r" % (description, output)
        if cb:
            result = cb(*result)
        elif len(result) == 1:
            result = result[0]
        return result
    def errback(error):
        print "Errback%r: %r" % (description, error)
        if eb:
            return eb(error)
        raise error
    return (callback,errback)

def callback(description=""):
    return callbacks(description)[0]

def errback(description=""):
    return callbacks(description)[1]


def cb(value):
    return value + 1

def eb(error):
    raise error

def register(promise, cb, eb, count=100):
    return [promise.then(cb, eb) for i in range(count)]

def chain(promise, cb, eb, count=100):
    promises = []
    for i in range(count):
        promise = promise.then(cb, eb)
        promises.append(promise)
    return promises

def showreturn(cb=None, eb=None):
    def callback(*value):
        if len(value) == 1:
            value = value[0]
        if cb:
            try:
                output = cb(value)
            except Exception,error:
                print "%r > cb %r: raised %r" % (value, cb.__name__, error)
                raise
            else:
                print "%r > cb %r: returned %r" % (value, cb.__name__, output)
        else:
            print "%r > cb None: re-return %r" % (value, value)
            output = value
        return output
    def errback(*error):
        if len(error) == 1:
            error = error[0]
        if eb:
            try:
                output = eb(error)
            except Exception,eberror:
                print "%r > eb %r: raised %r" % (error, eb.__name__, eberror)
                raise
            else:
                print "%r > eb %r: returned %r" % (error, eb.__name__, output)
        else:
            print "%r > eb None: re-raised %r" % (error, error)
            raise error
        return output
    return (callback,errback)

if __name__ == "__main__":
    
    p1 = promise.Promise()
    p2 = p1.then(*callbacks("p1 output"))
    p4 = p1.after(callback("after p1"))
    p3 = p2.then(*callbacks("p2 output", returns("shane")))
    
    p1.resolve("value")
    
    
    p1 = promise.Promise()
    t1 = time.time() 
    ps = [p1.then(cb,eb) for i in range(100)]; t2 = time.time()
    print "Took %0.5f seconds to attach" % (t2 - t1)
    
    t1 = time.time(); p1.resolve(0); t2 = time.time()
    print "Took %0.5f seconds to resolve" % (t2 - t1)
    
    p1 = promise.Promise()
    t1 = time.time(); ps = register(p1, cb, eb, 100); t2 = time.time()
    print "Took %0.5f seconds to attach" % (t2 - t1)
    t1 = time.time(); p1.resolve(0); t2 = time.time()
    print "Took %0.5f seconds to resolve" % (t2 - t1)
    
    p1 = promise.Promise()
    t1 = time.time(); ps = chain(p1, cb, eb, 100); t2 = time.time()
    print "Took %0.5f seconds to attach" % (t2 - t1)
    t1 = time.time(); p1.resolve(0); t2 = time.time()
    print "Took %0.5f seconds to resolve" % (t2 - t1)
    
    p1.then(cb).then(callback())
    
    p1 = promise.Promise()
    t1 = time.time() 
    p2 = p1.chained([(cb,eb) for i in range(100)]); t2 = time.time()
    print "Took %0.5f seconds to attach" % (t2 - t1)
    t1 = time.time(); p1.resolve(0); t2 = time.time()
    print "Took %0.5f seconds to resolve" % (t2 - t1)


