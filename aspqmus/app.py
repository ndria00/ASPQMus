import sys
import argparse

import tempfile
import subprocess
import os
from contextlib import ExitStack


from aspqmus.rewriters.AdornmentProgramRewriter import AdornmentProgramRewriter, AdornmentType, AdornmentOption
from aspqmus.utils import Settings

def entrypoint():
    parser = argparse.ArgumentParser(prog = "aspqmus", description = "TODO\n")

    parser.add_argument('--problem', help="path to problem file\n", required=True)
    parser.add_argument('--mus', help="compute mus of input ptogram - by default MCSes are computed\n", required=False, action="store_true")
    parser.add_argument('--adornment', choices=list(AdornmentOption), default=AdornmentOption.FACTS_ONLY, help='choose adornment option')

    args = parser.parse_args()

    encoding_path = args.problem
    try:
        encoding_program = "\n".join(open(encoding_path).readlines())
    except:
        print("Could not open problem file")
        exit(1)

    ad_option = AdornmentOption(args.adornment)
    ad_type = AdornmentType("mus") if args.mus else AdornmentType("mcs")
    adornment_rewriter = AdornmentProgramRewriter(encoding_program, Settings.OBJECTIVE_ATOM_O_NAME, Settings.OBJECTIVE_ATOM_U_NAME,Settings.UNSAT_ATOM_NAME, ad_type, ad_option)
    
    for program in adornment_rewriter.programs:
        print(program)

    print(adornment_rewriter.global_weak)

    # print(adornment_rewriter.objective_atoms_to_rules)

