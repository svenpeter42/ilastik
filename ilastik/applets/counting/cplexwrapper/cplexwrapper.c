#include <ilcplex/cplex.h>
#include <stdlib.h>
#include <math.h>

/* Bring in the declarations for the string functions */
#include <inttypes.h>
#include <string.h>

/* Include declaration for function at end of program */


#define NUMROWS    2
#define NUMCOLS    3
#define NUMNZ      6
#define NUMQNZ     7

static void
   free_and_null (char **ptr);



/* This simple routine frees up the pointer *ptr, and sets *ptr to NULL */

static void
free_and_null (char **ptr)
{
   if ( *ptr != NULL ) {
      free (*ptr);
      *ptr = NULL;
   }
} /* END free_and_null */


/* The problem we are optimizing will have 2 rows, 3 columns,
   6 nonzeros, and 7 nonzeros in the quadratic coefficient matrix. */

int printfarray(const double * array, int numrows, int numcols, char * name) {
  printf("%s\n", name);
  int i,j;
  for (i = 0; i < numrows; ++i) {
    for (j = 0; j < numcols; ++j) {
      printf("%f\t", array[i * numcols + j]);
    }
    printf("\n");
  }
}
int printiarray(const int * array, int numrows, int numcols, char * name) {
  printf("%s\n", name);
  int i,j;
  for (i = 0; i < numrows; ++i) {
    for (j = 0; j < numcols; ++j) {
      printf("%d\t", array[i * numcols + j]);
    }
    printf("\n");
  }

}

int fit(const double * X_p, const double * Yl_p, double* w, int postags, int numSamples, int numFeatures, double C, double epsilon,
        int numBoxConstraints, const double * boxValues, const int64_t * boxIndices, const double * boxMatrix)
{
  int i,j,k;
  CPXENVptr     env = NULL;
  CPXLPptr      lp = NULL;
  int status;
  char probname[] = "Testproblem";
  env = CPXopenCPLEX (&status);
  lp = CPXcreateprob (env, &status, probname);
  status = CPXsetintparam (env, CPX_PARAM_SCRIND, CPX_ON);
  if ( status ) {
    fprintf (stderr,
             "Failure to turn on screen indicator, error %d.\n", status);
    goto TERMINATE;
  }

  int numrows = postags + numSamples;
  int numcols = numFeatures + 1 + numrows;
  
  char *sense = (char*) malloc((numrows) * sizeof(char));
  double *lb = (double*) malloc(numcols * sizeof(double));
  double *ub = (double*) malloc(numcols * sizeof(double));;
  double *obj = (double*) malloc(numcols * sizeof(double));
  double *rhs = (double*) malloc(numrows * sizeof(double));
  double *tagarray = (double*) malloc(numrows * sizeof(double));

  int      *matbeg = (int*) malloc(numcols * sizeof(int));
  int      *matcnt = (int*) malloc(numcols * sizeof(int));
  int      *matind = (int*) malloc(numcols * numrows * sizeof(int));
  double   *matval = (double* ) malloc(numcols * numrows * sizeof(double));
  double   *qsepvec = (double*) malloc((numcols + 2 * numBoxConstraints) * sizeof(double));

  double* dens = NULL;
  double* boxConstraints = NULL;
  int      *boxrmatbeg = NULL;
  int      *boxrmatind = NULL;
 
  if (sense == NULL || lb == NULL || ub == NULL || obj == NULL 
      || rhs == NULL || tagarray == NULL || qsepvec == NULL) {
    status = 1;
    goto TERMINATE;
  }





  printf("rows: %d, cols: %d\n", numrows, numcols);
  printf("postags: %d", postags);

  for (i = 0; i < postags; ++i) {
    tagarray[i] = 1;
    sense[i] = 'G';
  }
  printf("Status ok\n");
  for (i = postags; i < numrows; ++i) {
    tagarray[i] = -1;
    sense[i] = 'L';
  }
  printf("Status ok\n");
  for (i = 0; i < postags; ++i) {
    rhs[i] = Yl_p[i] - tagarray[i] * epsilon ;
  }
  printf("Status ok\n");
  for (i = postags; i < numrows; ++i) {
    rhs[i] = Yl_p[i - postags] - tagarray[i] * epsilon ;
  }
  printf("Status ok\n");
  for (i = 0; i < numFeatures + 1; ++i) {
    lb[i] = -CPX_INFBOUND;
    ub[i] = CPX_INFBOUND;
    matbeg[i] = i * (numrows);
    matcnt[i] = numrows;
  }
  for (i = numFeatures + 1; i < numcols; ++i) {
    lb[i] = 0;
    ub[i] = CPX_INFBOUND;
    matbeg[i] = (numFeatures + 1) * numrows + (i - numFeatures - 1);
    matcnt[i] = 1;
  }

  for (j = 0; j < numFeatures; ++j) {
    for (i = 0; i < postags; ++i) {
      matind[j * numrows + i] = i;
      matval[j * (numrows) + i] = X_p[i * numFeatures + j];
    }
    for (i = postags; i < numrows; ++i) {
      matind[j * numrows + i] = i;
      matval[j * (numrows) + i] = X_p[(i - postags) * numFeatures + j];
    }
  }

  printf("Status ok\n");
  for (i = 0; i < numrows; ++i) {
    matind[numFeatures * numrows + i] = i;
    matval[numFeatures * numrows + i] = 1;
  }

  for (i = 0; i < numrows; ++i) {
    matind[(numFeatures + 1) * numrows + i] = i;
    matval[(numFeatures + 1) * numrows + i] = tagarray[i];
  }

  /*for (int i = 0; i < numrows * numcols; ++i) {
    printf("rmatind: %d, rmatval: %f\n", rmatind[i], rmatval[i]);
    }*/

  for (i = 0; i < numFeatures; ++i){
    qsepvec[i] = 1;
    obj[i] = 0;
  }
  obj[numFeatures] = 0;
  qsepvec[numFeatures] = 0;
  for (i = numFeatures + 1; i < numcols; ++i){
    qsepvec[i] = 2 * C;
    obj[i] = 0;
  }


  //float *slack = (float*) malloc(())
  //    if (zqsepvec == NULL)
  //    {
  //      status = 1;
  //      goto TERMINATE;
  //    }

  //status = CPXaddrows(env, lp, numcols, numrows, (numFeatures+2) * numrows, rhs, sense, rmatbeg, rmatind, rmatval, NULL, NULL);
  printf("Status ok\n");
  status = CPXcopylp (env, lp, numcols, numrows, 1, obj, rhs,
                      sense, matbeg, matcnt, matind, matval,
                      lb, ub, NULL);
  printf("Status ok\n");

  status = CPXcopyqpsep (env, lp, qsepvec);
  status = CPXwriteprob (env, lp, "qpex1.lp", NULL);
  status = CPXqpopt (env, lp);
  status = CPXgetx (env, lp, w, 0, numFeatures);

  if (numBoxConstraints > 0) {
    printf("Implementing Box Constraints\n");
    int numBoxSamples = boxIndices[numBoxConstraints];

    dens = (double*) malloc(numBoxSamples * sizeof(double));
    boxConstraints = (double*) calloc(numBoxConstraints * (numFeatures + 2), sizeof(double));
    boxrmatbeg = (int*) malloc(numBoxConstraints * sizeof(int));
    boxrmatind = (int*) malloc(numBoxConstraints * (numFeatures + 2) * sizeof(int));
  
    if (dens == NULL || boxConstraints == NULL || boxrmatbeg == NULL || boxrmatind == NULL) {
      status = 1;
      goto TERMINATE;
    }


    //double   *boxrmatval = (double* ) malloc( * sizeof(double));


    //for every entry in the box features, check if it's background or
    //foreground
    for (i = 0; i < numBoxSamples; ++i) {
      dens[i] = w[numFeatures];
      for (j = 0; j < numFeatures; ++j) {
        dens[i] += boxMatrix[i * numFeatures + j] * w[j];
      }
    } 
    for (i = 0; i < numBoxSamples; ++i) {
      if (dens[i] > 0){
        dens[i] = 1;
      }
      else {
        dens[i] = 0;
      }
     // printf("Density: %f\n", dens[i]);
    }

    printfarray(boxConstraints, numBoxConstraints, numFeatures + 2, "boxConstraints"); 
    for (k = 0; k < numBoxConstraints; ++k) {
      boxrmatbeg[k] = k * (numFeatures + 2);
      for (i = boxIndices[k]; i < boxIndices[k + 1]; ++i){
        for (j = 0; j < numFeatures; ++j){
          boxConstraints[k * (numFeatures + 2) + j]  += dens[i] * boxMatrix[i * numFeatures + j];
        }
        boxConstraints[k * (numFeatures + 2) + numFeatures] += dens[i];
      }
    }
    for (i = 0; i < numBoxConstraints; ++i) {
      for (j = 0; j < numFeatures + 1; ++j) {
        boxrmatind[i * (numFeatures + 2) + j] = j;
      } 
      boxrmatind[i * (numFeatures + 2) + numFeatures + 1] = numcols + i;
    }

    char * boxSense = (char*) malloc(numBoxConstraints * sizeof(char));
    for (i = 0; i < numBoxConstraints; ++i) { 
      boxSense[i] = 'L';
    }
    for (i = 0; i < numBoxConstraints; ++i) {
      boxConstraints[i * (numFeatures + 2) + numFeatures+1] = - 1;
    }
    status = CPXaddrows(env, lp, numBoxConstraints, numBoxConstraints, numBoxConstraints * (numFeatures + 2), boxValues,
                        boxSense, boxrmatbeg, boxrmatind, boxConstraints, NULL, NULL);
    for (i = 0; i < numBoxConstraints; ++i) {
      boxrmatind[i * (numFeatures + 2) + numFeatures + 1] = numcols + numBoxConstraints + i;
    }
    
    for (i = 0; i < numBoxConstraints; ++i) { 
      boxSense[i] = 'G';
    }
    for (i = 0; i < numBoxConstraints; ++i) {
      boxConstraints[i * (numFeatures + 2) + numFeatures+1] = + 1;
    }
    status = CPXaddrows(env, lp, numBoxConstraints, numBoxConstraints, numBoxConstraints * (numFeatures + 2), boxValues,
                        boxSense, boxrmatbeg, boxrmatind, boxConstraints, NULL, NULL);

    for (i = 0; i < numBoxConstraints; ++i) {
      qsepvec[numcols + i] = 2 * C / sqrt((boxIndices[i + 1] - boxIndices[i]));
      qsepvec[numcols + i + numBoxConstraints] = 2 * C / sqrt((boxIndices[i + 1] - boxIndices[i]));
      printf("%d, %d\n",boxIndices[i], boxIndices[i + 1]);
      printf("%f, %f\n", qsepvec[numcols+i], qsepvec[numcols + i + numBoxConstraints]);
    }

    printf("WHY IS NOTHING HAPPENING\n");
    status = CPXcopyqpsep (env, lp, qsepvec);
    status = CPXwriteprob (env, lp, "qpex1.lp", NULL);
    status = CPXqpopt (env, lp);
    status = CPXgetx (env, lp, w, 0, numFeatures);
  }


//status = CPXsolution(env, lp, &solstat, &objval, x, pi, slack, dj);

TERMINATE:

  free_and_null ((char **) &obj);
  free_and_null ((char **) &rhs);
  free_and_null ((char **) &sense);
  free_and_null ((char **) &tagarray);
  free_and_null ((char **) &lb);
  free_and_null ((char **) &ub);
  free_and_null ((char **) &matbeg);
  free_and_null ((char **) &matcnt);
  free_and_null ((char **) &matind);
  free_and_null ((char **) &matval);
  free_and_null ((char **) &qsepvec);
  
  free_and_null ((char **) &dens);
  free_and_null ((char **) &boxConstraints);
  free_and_null ((char **) &boxrmatbeg);
  free_and_null ((char **) &boxrmatind);
return (status);

}



/* This function fills in the data structures for the quadratic program:

   Maximize
obj: x1 + 2 x2 + 3 x3
- 0.5 ( 33x1*x1 + 22*x2*x2 + 11*x3*x3
-  12*x1*x2 - 23*x2*x3 )
Subject To
c1: - x1 + x2 + x3 <= 20
c2: x1 - 3 x2 + x3 <= 30
Bounds
0 <= x1 <= 40
End
*/

