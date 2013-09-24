import argparse
parser = argparse.ArgumentParser()
parser.add_argument('--hello-there')
parser.add_argument('input_files', nargs='*', help='List of input files to process.')

namespace, unused_args = parser.parse_known_args()
print namespace.__dict__
print "Unused: ", unused_args


