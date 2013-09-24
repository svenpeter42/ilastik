import numpy
import vigra

indices = numpy.indices((100,100))

# Test image.  Mostly zeros with a small square of 1s in the middle.
input = numpy.ones( (100,100) )
input = numpy.logical_and(input, indices[0] >= 30)
input = numpy.logical_and(input, indices[0] <  70)
input = numpy.logical_and(input, indices[1] >= 30)
input = numpy.logical_and(input, indices[1] <  70)

# Invert (small square of zeros surrounded by 1s)
input = numpy.logical_not(input).astype(numpy.uint8)
vigra.impex.writeImage((input*255).astype(numpy.uint8), 'input.png')

seeds = numpy.zeros((100,100), dtype=numpy.uint32)
seeds[50,50] = 1

ws, max_label = vigra.analysis.watersheds( input*2,
                                seeds=seeds,
                                method='RegionGrowing',
                                terminate=vigra.analysis.SRGType.StopAtThreshold,
                                max_cost=1 )

vigra.impex.writeImage((ws*255).astype(numpy.uint8), 'ws.png')
