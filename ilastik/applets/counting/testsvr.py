
import matplotlib
from matplotlib import tri
import matplotlib.pyplot as plt

#
def create_triangulation(locations, ratio):
    selection = np.random.random_integers(low = 0, high = len(locations[0]) -1, size = locations[0].shape[0] * ratio)
    triang = tri.Triangulation(locations[0][selection],locations[1][selection])
    trifinder = triang.get_trifinder()
    index = trifinder(locations[0],locations[1])
    return triang, index


def calculate_features(index, locations, list_features):
    allpoints = np.transpose(np.vstack(locations))
    num_simplex = np.max(index) + 1

    triangulation_features = np.zeros((num_simplex, len(list_features)))

    for i in range(allpoints.shape[0]):
        p_index = allpoints[i,:]
        s_index = index[i]
        for j, feature in enumerate(list_features):
            triangulation_features[s_index,j] += feature(p_index[0],p_index[1])
        #triangulation_dots[s_index]       += triangulation_dot[p_index[0], p_index[1]]

    return triangulation_features


def plot_triang(triang):
    plt.figure()
    plt.gca().set_aspect('equal')
    plt.triplot(triang, 'bo-')
    plt.title('triplot of Delaunay triangulation')



def predict_triangles(shape, ratio, list_features, counter):
    test_locations = np.indices(shape)
    test_locations = test_locations.reshape((2,-1))
    test_triang, test_index = create_triangulation(test_locations, ratio)
    print "calculate features"
    test_features = calculate_features(test_index, test_locations, list_features)
    print "end test triangulation"
    res = counter.predict(test_features)
    print "finished prediction"
    pixelres = np.zeros(test_index.shape)
    for i,pixel in enumerate(pixelres):
        triangdens = res[test_index[i]]
        triangcount = test_features[test_index[i],0]
        if test_index[i] != -1:
            pixelres[i] += triangdens / triangcount

    return pixelres

    
def create_boxes(size, shape, offset = 0):
    
    #shape = (20,20)
    test_index = np.zeros(shape)
    r = np.arange(shape[0] - offset)

    mmax = shape[0] / size
    
    test_index[0,offset:] = r / size
    test_index[:,:] = test_index[0,:]
    test_index = test_index + mmax * test_index.transpose()
    #go.db
    #test_index1.transpose()
    #test_index2[:,0] = r / size
    #go.db
    #test_index2[:,:] = test_index2[:,0]

    test_locations = np.indices(shape)
    test_locations = test_locations.reshape((2,-1))
    #print test_locations.shape
    #print test_index.reshape(-1)

    return test_index.reshape(-1), test_locations


def predict_squares(shape, ratio, list_features, counter):
    
    print "finished prediction"
    #just create test_index, test_locations and list_features correctly
    #example:
    #test_index = [0,0,0,0], test_locations = [[0,1,0,1],[0,0,1,1]]
    test_index, test_locations = create_boxes(3, shape)
    test_features = calculate_features(test_index, test_locations, list_features)
    res = counter.predict(test_features)
    pixelres = np.zeros(test_index.shape)
    for i,pixel in enumerate(pixelres):
        triangdens = res[test_index[i]]
        triangcount = test_features[test_index[i],0]
        if test_index[i] != -1:
            pixelres[i] += triangdens / triangcount

    return pixelres


if __name__ == "__main__":
    from countingsvr import *


    np.set_printoptions(precision=4)
    np.set_printoptions(threshold = 'nan')
    img = np.load("img.npy")
    dot = np.load("dot.npy")
    #img = img[...,[2]]
    #img = img[..., None]
    
    DENSITYBOUND=False

    backup_image = np.copy(img)
    backup_dot = np.copy(dot)
    sigma = 2.5
    methods = ["BoxedRegressionCplex", "BoxedRegressionGurobi", "RandomForest"]
    Counter = SVR(method = methods[0], Sigma= sigma)
    testdot, testmapping, testtags = Counter.prepareData(dot,smooth = True)
#    testimg = img.reshape((-1, img.shape[-1]))
#    #print "blub", testimg.shape
#    #print testimg
#    #print testdot, np.sum(testdot)
#    
#    boxIndices = np.array([0, 1600])
#    boxFeatures = np.array(img[40:80,40:80],dtype=np.float64)
#    boxValues = np.array([2])
#    boxFeatures = boxFeatures.reshape((-1, boxFeatures.shape[-1]))
#    
#    boxConstraints = {"boxValues": boxValues, "boxIndices" : boxIndices, "boxFeatures" :boxFeatures}
#    #boxConstraints = None
#
#    #print testtags
#    numRegressors = 1
#    success = Counter.fitPrepared(testimg[testmapping,:], testdot[testmapping], testtags,
#                                  boxConstraints = boxConstraints, numRegressors = numRegressors)
#
#    newdot = Counter.predict(backup_image)
#
#    print "prediction"
#    #print img
#    #print newdot
#    print "sum", np.sum(newdot) / numRegressors
#    #try: 
#    #    import matplotlib.pyplot as plt
#    #    import matplotlib
#    #    fig = plt.figure()
#    #    fig.add_subplot(1,3,1)
#    #    plt.imshow(testimg[...,0].astype('uint8').reshape(backup_image.shape[:-1]), cmap=matplotlib.cm.gray)
#    #    fig.add_subplot(1,3,2)
#    #    plt.imshow(newdot.reshape(backup_image.shape[:-1]), cmap=matplotlib.cm.gray)
#    #    fig.add_subplot(1,3,3)
#    #    plt.imshow(testdot.reshape(backup_image.shape[:-1]), cmap=matplotlib.cm.gray)
#    #    plt.show()
#    #except:
#    #    pass
#
#


    #Howto: first randomly sample points to get a triangulation
    
    triangulation_image = np.copy(backup_image)
    triangulation_dot = np.copy(testdot)
    triangulation_dot = triangulation_dot.reshape(backup_image.shape[:-1])
    #do features for foreground
    locations = np.where(triangulation_dot> 0.0001)
    ratio = 0.2

    triang,index = create_triangulation(locations, ratio)

    list_features = [
        lambda x,y: 1,
        lambda x,y: backup_image[x,y,2], 
        lambda x,y: backup_image[x,y,5],
        lambda x,y: backup_image[x,y,6],
        lambda x,y: backup_image[x,y,7],
        lambda x,y: backup_image[x,y,8],
        lambda x,y: backup_image[x,y,9],
        lambda x,y: backup_image[x,y,10]
    ]
    features = calculate_features(index, locations, list_features)
    #print features

    
    #plot_triang(triang)

    dot_feature = [
        lambda x,y: triangulation_dot[x,y]
    ]
    dots = calculate_features(index, locations, dot_feature)

    background_locations = np.where(backup_dot == 2)
    background_triang, background_index = create_triangulation(background_locations, 1)
    background_features = calculate_features(background_index, background_locations, list_features)
    background_dots = calculate_features(background_index, background_locations, dot_feature)
    #print background_features

    #do features for background


    #plt.show()


    triang_features = np.vstack((features, background_features))
    triang_dots = np.vstack((dots, background_dots)).reshape(-1)
    triang_tags = [dots.shape[0], background_dots.shape[0]]
    #print testimg.shape
    #print testdot.shape
    #print triang_features.shape
    #print triang_dots.shape
    
    print "fitting"
    success = Counter.fitPrepared(triang_features, triang_dots, triang_tags,
                                  None)
    print "finished fitting"

    print "start test triangulation"

    pixelres = predict_triangles((256,256), ratio, list_features, Counter)
    pixelres2 = predict_squares((256, 256), ratio, list_features, Counter)
    print "finished conversion"

    

    
    #convert triangle densities into pixel-level results

    #go.db
    

    print np.sum(pixelres)
    print np.sum(pixelres2)
    fig = plt.figure()
    fig.add_subplot(1,3,1)
    plt.imshow(backup_image[:,:,2].reshape(backup_image.shape[:-1]),cmap=matplotlib.cm.gray)
    fig.add_subplot(1,3,2)
    plt.imshow(pixelres.reshape(backup_image.shape[:-1]),cmap=matplotlib.cm.gray)
    fig.add_subplot(1,3,3)
    plt.imshow(pixelres2.reshape(backup_image.shape[:-1]),cmap=matplotlib.cm.gray)
    plt.show()


    #from scipy.spatial import Delaunay
    #tri = Delaunay(points)
    #index = tri.find_simplex(allpoints)
    ##now calculate features for each triangle
    ##features: size, average_feat2
    #print backup_image.shape

    
    #print triangulation_features[:,1].shape
    #plt.imshow(triangulation_features[:,1].reshape(backup_image.shape[:-1]),cmap=matplotlib.cm.gray)
    #plt.triplot(points[:,0], points[:,1], tri.simplices.copy())
    #plt.plot(points[:,0], points[:,1], 'o')
    #plt.show()
