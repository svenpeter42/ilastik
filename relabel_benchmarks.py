import numpy

original_labels = None
mapping = None
sorted_mapping_keys = None
index_array = None

# TODO: Ensure that all labels are present in mapping dict
#       because none of these functions work otherwise.

def using_index_array():
    consecutivized_labels = numpy.searchsorted( sorted_mapping_keys, original_labels )
    return index_array[ consecutivized_labels ]

def using_frompyfunc():
    vectorized_relabel = numpy.frompyfunc(mapping.__getitem__, 1, 1)
    return vectorized_relabel( original_labels )

def using_frompyfunc_with_lambda():
    vectorized_relabel = numpy.frompyfunc(lambda x: mapping[x], 1, 1)
    return vectorized_relabel( original_labels )

def using_vectorize():
    vectorized_relabel = numpy.vectorize(mapping.__getitem__)
    return vectorized_relabel( original_labels )    

def using_vectorize_with_lambda():
    vectorized_relabel = numpy.vectorize(lambda x: mapping[x])
    return vectorized_relabel( original_labels )    

def using_plain_forloop():
    # This turns out to be ridiculously slow.
    result = numpy.ndarray( shape=original_labels.shape, dtype=original_labels.dtype )
    result_flat = result.flat
    original_flat = original_labels.flat
    for i in xrange( len(result_flat) ):
        result_flat[i] = mapping[original_flat[i]]
    return result

# Quick consistency check on a small image...
original_labels = (100*numpy.random.random( (100,100) )).astype(numpy.uint32)
mapping = { k : k + 99 for k in range(100) }
expected = original_labels + 99
sorted_mapping_keys = numpy.asarray( sorted( mapping.iterkeys() ), dtype=numpy.uint32 )
index_array = numpy.array( sorted( mapping.iteritems() ) )[:, 1]
assert ( expected == using_index_array() ).all()
assert ( expected == using_vectorize_with_lambda() ).all()
assert ( expected == using_frompyfunc_with_lambda() ).all()
assert ( expected == using_frompyfunc() ).all()
assert ( expected == using_vectorize() ).all()
assert ( expected == using_plain_forloop() ).all()

import timeit

original_labels = (100*numpy.random.random( (10000,10000) )).astype(numpy.uint32)
mapping = { k : k + 99 for k in range(100) }
sorted_mapping_keys = numpy.asarray( sorted( mapping.iterkeys() ), dtype=numpy.uint32 )
index_array = numpy.array( sorted( mapping.iteritems() ) )[:, 1]
print "With 100 labels:\n"
#print "using_vectorize_with_lambda", timeit.timeit( "using_vectorize_with_lambda()", "from __main__ import using_vectorize_with_lambda", number=1 )
#print "using_frompyfunc_with_lambda", timeit.timeit( "using_frompyfunc_with_lambda()", "from __main__ import using_frompyfunc_with_lambda", number=1 )
#print "using_vectorize", timeit.timeit( "using_vectorize()", "from __main__ import using_vectorize", number=1 )
print "using_frompyfunc", timeit.timeit( "using_frompyfunc()", "from __main__ import using_frompyfunc", number=1 )
print "using_index_array", timeit.timeit( "using_index_array()", "from __main__ import using_index_array", number=1 )
#print "using_plain_forloop", timeit.timeit( "using_plain_forloop()", "from __main__ import using_plain_forloop", number=1 )
print ""

original_labels = (10000*numpy.random.random( (10000,10000) )).astype(numpy.uint32)
mapping = { k : k + 99 for k in range(10000) }
sorted_mapping_keys = numpy.asarray( sorted( mapping.iterkeys() ), dtype=numpy.uint32 )
index_array = numpy.array( sorted( mapping.iteritems() ) )[:, 1]
print "With 10000 labels:\n"
#print "using_vectorize_with_lambda", timeit.timeit( "using_vectorize_with_lambda()", "from __main__ import using_vectorize_with_lambda", number=1 )
#print "using_frompyfunc_with_lambda", timeit.timeit( "using_frompyfunc_with_lambda()", "from __main__ import using_frompyfunc_with_lambda", number=1 )
#print "using_vectorize", timeit.timeit( "using_vectorize()", "from __main__ import using_vectorize", number=1 )
print "using_frompyfunc", timeit.timeit( "using_frompyfunc()", "from __main__ import using_frompyfunc", number=1 )
print "using_index_array", timeit.timeit( "using_index_array()", "from __main__ import using_index_array", number=1 )
#print "using_plain_forloop", timeit.timeit( "using_plain_forloop()", "from __main__ import using_plain_forloop", number=1 )

original_labels = (30000*numpy.random.random( (10000,10000) )).astype(numpy.uint32)
mapping = { k : k + 99 for k in range(1000000) }
sorted_mapping_keys = numpy.asarray( sorted( mapping.iterkeys() ), dtype=numpy.uint32 )
index_array = numpy.array( sorted( mapping.iteritems() ) )[:, 1]
print "With 30,000 labels using 1M entry map:\n"
print "using_index_array", timeit.timeit( "using_index_array()", "from __main__ import using_index_array", number=1 )
print "using_frompyfunc", timeit.timeit( "using_frompyfunc()", "from __main__ import using_frompyfunc", number=1 )
print ""

original_labels = (30000*numpy.random.random( (10000,10000) )).astype(numpy.uint32)
mapping = { k : k + 99 for k in range(10000000) }
sorted_mapping_keys = numpy.asarray( sorted( mapping.iterkeys() ), dtype=numpy.uint32 )
index_array = numpy.array( sorted( mapping.iteritems() ) )[:, 1]
print "With 30,000 labels using 10M entry map:\n"
print "using_index_array", timeit.timeit( "using_index_array()", "from __main__ import using_index_array", number=1 )
print "using_frompyfunc", timeit.timeit( "using_frompyfunc()", "from __main__ import using_frompyfunc", number=1 )
print ""
