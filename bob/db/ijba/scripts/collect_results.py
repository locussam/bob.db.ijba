#!/usr/bin/env python
# vim: set fileencoding=utf-8 :
# Tiago de Freitas Pereira <tiago.pereira@idiap.ch>

from __future__ import print_function

"""
This script parses through the given directory, collects all results of
verification experiments that are stored in file with the given file name.
It supports the split into development and test set of the data, as well as
ZT-normalized scores.

All result files are parsed and evaluated. For each directory, the following
information are given in columns:

  * The Equal Error Rate of the development set
  * The Equal Error Rate of the development set after ZT-Normalization
  * The Half Total Error Rate of the evaluation set
  * The Half Total Error Rate of the evaluation set after ZT-Normalization
  * The sub-directory where the scores can be found

The measure type of the development set can be changed to compute "HTER" or
"FAR" thresholds instead, using the --criterion option.
"""


import sys, os,  glob
import argparse
import numpy

import bob.measure
import bob.core
logger = bob.core.log.setup("bob.bio.base")

from bob.bio.base.script.collect_results import Result, recurse, add_results
#, command_line_arguments

far_thresholds = [0.1, 0.01, 0.001]



def table(results):
  """Generates a table containing all results in a nice format."""
  A = " "*2 + 'dev  nonorm'+ " "*5 + 'dev  ztnorm' + " "*6 + 'eval nonorm' + " "*4 + 'eval ztnorm' + " "*12 + 'directory\n'
  A += "-"*100+"\n"
  for r in results:
    if r.valid():
      A += str(r) + "\n"
  return A


def command_line_arguments(command_line_parameters):
  """Parse the program options"""

  # set up command line parser
  parser = argparse.ArgumentParser(description=__doc__,
      formatter_class=argparse.ArgumentDefaultsHelpFormatter)

  parser.add_argument('-D', '--directory', default=".", help = "The directory where the results should be collected from; might include search patterns as '*'.")
  parser.add_argument('-o', '--output', help = "Name of the output file that will contain the EER/HTER scores")
  parser.add_argument('-r', '--report-type', type=str, default="comparison", choices=("comparison", "search"), help = "Type of the report. For `comparison`, CMC(rank=1) and TPIR (FAR=[0.1, 0.01 and 0.001] ) will be reported. For the search DIR (rank=1) and TPIR (FAR=[0.1, 0.01 and 0.001] is reported")

  parser.add_argument('--self-test', action='store_true', help=argparse.SUPPRESS)

  bob.core.log.add_command_line_option(parser)

  # parse arguments
  args = parser.parse_args(command_line_parameters)

  bob.core.log.set_verbosity_level(logger, args.verbose)

  return args


def search_results(args, directories):
  """
  Navigates throught the directories collection evaluation results
  """
  results = []
  for directory in directories:
    r = recurse(args, directory)
    if r is not None:
      results += r

  return results
  

def compute_comparison(args, directories):
  """
  Plot evaluation table for the comparison protocol
  """

  def plot_comparison_table(cmc_r1, fnmr):
    grid =  "+-----------------+-----------------+-----------------+-----------------+--------------------------+\n"
    grid += "|    CMC% (R=1)   | TPIR% (FAR=0.1) | TPIR% (FAR=0.01)|TPIR% (FAR=0.001)| split                    |\n"
    grid += "+=================+=================+=================+=================+==========================+\n"
    
    for cmc, fnmr_0, fnmr_1, fnmr_2, split in zip(cmc_r1, fnmr[0], fnmr[1], fnmr[2], range(len(cmc_r1))):
      grid += "|{:17s}|{:17s}|{:17s}|{:17s}|{:26s}|\n".format(str(round(cmc.nonorm_dev,5)*100),
                                                             str(round(fnmr_0.nonorm_dev,5)*100),
                                                             str(round(fnmr_1.nonorm_dev,5)*100),
                                                             str(round(fnmr_2.nonorm_dev,5)*100),
                                                             "split {0}".format(split))
      grid +=  "+-----------------+-----------------+-----------------+-----------------+--------------------------+\n"
    return grid

  def compute_fnmr(args_augmented, directories):
    fnmr = []  
    for f in far_thresholds:
      args_augmented.criterion = "FAR"
      args_augmented.far_threshold = f
      
      # Computing TPIR
      frr = search_results(args_augmented, directories)
      for rr in frr:
        rr.nonorm_dev = 1.-rr.nonorm_dev
      fnmr.append(frr)

    return fnmr


  args_augmented = args
  args_augmented.rank = 1
  args_augmented.criterion = "RR"
  cmc_r1 = search_results(args_augmented, directories)
  fnmr = compute_fnmr(args_augmented, directories)
  return plot_comparison_table(cmc_r1, fnmr)


def compute_search(args, directories):
  """
  Plot evaluation table for the search protocol
  """

  def plot_search_table(dira):
    grid =  "+-----------------+-----------------+-----------------+--------------------------+\n"
    grid += "| DIR% (FAR=0.1)  | DIR% (FAR=0.01) | DIR% (FAR=0.001)| split                    |\n"
    grid += "+=================+=================+=================+==========================+\n"

    n_splits = len(dira[0])
    for dira_0, dira_1, dira_2, split in zip(dira[0], dira[1], dira[2], range(n_splits)):
      grid += "|{:17s}|{:17s}|{:17s}|{:26s}|\n".format(str(round(dira_0.nonorm_dev,5)*100),
                                                       str(round(dira_1.nonorm_dev,5)*100),
                                                       str(round(dira_2.nonorm_dev,5)*100),
                                                       "split {0}".format(split))
      grid +=  "+-----------------+-----------------+-----------------+--------------------------+\n"
    return grid

  def compute_dir(args_augmented, directories):
    dira = []  
    for f in far_thresholds:
      args_augmented.criterion = "DIR"
      args_augmented.far_threshold = f      
      dira.append(search_results(args_augmented, directories))

    return dira


  args_augmented = args
  args_augmented.rank = 1
  args_augmented.criterion = "DIR"

  dira = compute_dir(args_augmented, directories)
  return plot_search_table(dira)


def main(command_line_parameters = None):
  """Iterates through the desired directory and collects all result files."""
  args = command_line_arguments(command_line_parameters)

  # collect results
  directories = glob.glob(args.directory)
  
  # Injecting some variables
  args.dev = "scores-dev"
  args.eval = "scores-eval"  
  args.nonorm = "nonorm"
  args.ztnorm = "ztnorm"
  
  if args.report_type == "comparison":
    print(compute_comparison(args, directories))
  else:
    print(compute_search(args, directories))

