import argparse
import tempfile
import subprocess
import re
import json
import os
from pyqasp.pyqaspsolver import PyQASPSolver
from aspqmus.rewriters.AdornmentProgramRewriter import AdornmentProgramRewriter, AdornmentType, AdornmentOption
from aspqmus.utils import Settings, Logger
from aspqmus.remus import enumerate_muses, enumerate_mcses
import sys

def entrypoint():
    parser = argparse.ArgumentParser(prog = "aspqmus", description = "TODO\n")

    parser.add_argument('--problem', help="path to problem file\n", required=True)
    parser.add_argument('--mus', help="compute mus of input ptogram - by default MCSes are computed\n", required=False, action="store_true")
    parser.add_argument('--remus', help="compute MUS or MCS using a remus approach\n", required=False, action="store_true")
    parser.add_argument('--adornment', choices=list(AdornmentOption), default=AdornmentOption.FACTS_ONLY, help='choose adornment option')
    parser.add_argument('--pyqasp', help="path to pyqasp executable - if not specified it assumes that the solver is callable as pyqasp\n", required=False)
    parser.add_argument('--debug', help="enable debug prints\n", required=False, action="store_true")
    parser.add_argument('--tmpdir', help="directory for temporary files", required=False, default=None)
    parser.add_argument('--print-adorned-rules', help="print rules that are adorned for mus - useful for debug\n", required=False, action="store_true")
    args = parser.parse_args()

    if args.tmpdir:
        tempfile.tempdir = args.tmpdir

    encoding_path = args.problem
    try:
        encoding_program = "\n".join(open(encoding_path).readlines())
    except:
        print("Could not open problem file")
        exit(1)

    logger = Logger(args.debug)
    ad_option = AdornmentOption(args.adornment)
    ad_type = AdornmentType("mus") if args.mus else AdornmentType("mcs")
    create_enforce = True if args.remus else False
    adornment_rewriter = AdornmentProgramRewriter(encoding_program, Settings.OBJECTIVE_ATOM_O_NAME, Settings.OBJECTIVE_ATOM_U_NAME,Settings.UNSAT_ATOM_NAME, ad_type, ad_option, create_enforce)

    for program in adornment_rewriter.programs:
        logger.print(program)
    if not args.remus:
        logger.print(adornment_rewriter.global_weak)
    if args.pyqasp: 
        pyqasp_executable = args.pyqasp
    else:
        pyqasp_executable = "pyqasp"
    
    if args.remus:
        logger.print("Doing remus")
        try:
            with tempfile.NamedTemporaryFile(mode="w", prefix="aspqmus_", suffix=".aspq", delete=False) as program:
                program_name = program.name
                for prg in adornment_rewriter.programs:
                    program.write(str(prg))
                program.close()

            with open(program.name, mode="r") as program_pyqasp:
                solver = PyQASPSolver(program.name)
                solver.ground()
                objective_atoms_map = adornment_rewriter.get_objective_map()
                # for i, o in objective_atoms_map.items():
                #     print(i, "<->", o)

                if ad_type == AdornmentType.MUS:
                    for mus_id, mus in enumerate(enumerate_muses(solver, objective_atoms_map), start=1):
                        print(f"[MUS #{mus_id}]")
                        print(adornment_rewriter.print_subprogram(mus))
                        exit(0)
                else:
                    for mcs_id, mcs in enumerate(enumerate_mcses(solver, objective_atoms_map), start=1):
                        print(f"[MCS #{mcs_id}]")
                        print(adornment_rewriter.print_subprogram(mcs))
                        exit(0)

                solver.close()
                print("Remus finished")
            
        finally:
            if program_name: os.unlink(program_name)

    else:
        logger.print("Using weak constraints")
        try:
            with tempfile.NamedTemporaryFile(mode="w", prefix="aspqmus_", suffix=".aspq", delete=False) as program, tempfile.NamedTemporaryFile(mode="w", prefix="aspqmus_", suffix=".asp", delete=False) as weak:
                program_name = program.name
                weak_name = weak.name
                for prg in adornment_rewriter.programs:
                    program.write(str(prg))
                weak.write(adornment_rewriter.global_weak.rules)
                program.close()
                weak.close()
                with open(program.name, mode="r") as program_pyqasp ,open(weak.name, mode="r") as weak_pyqasp:
                    command = [pyqasp_executable, "-g", "gringo", "-s" , "quabs", "--no-wf", "-w", weak_pyqasp.name, program_pyqasp.name]
                    logger.print("Executing PyQASP")
                    proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    stdout, stderr = proc.communicate()
                    if proc.returncode not in [10,20,30]:
                        if stderr.decode() != "":
                            print(stderr.decode())
                        program_pyqasp.close()
                        weak_pyqasp.close()
                        exit(proc.returncode)
                    else:
                        out = stdout.decode()
                        logger.print(out)
                        logger.print(f"{ad_type} found")
                        
                        #take last quantified answer set
                        optimum = "{" +re.findall("\"literals\": \\[.*?\\]", out)[-1] + "}"
                        try:
                            logger.print(f"Subprogram involved in {ad_type}:")
                            optimum_as_json = json.loads(optimum)
                            at_least_one = False
                            print("{", end="")
                            print("\"MCS\": " if ad_type == AdornmentType.MCS else "\"MUS\": ", end="")
                            rules = []
                            for literal in optimum_as_json["literals"]:
                                lit = str(literal)
                                if not re.match(rf"{Settings.OBJECTIVE_ATOM_U_NAME}\(\d+,\d+\)", lit) is None:
                                    rules.append(f"\"{adornment_rewriter.objective_atoms_to_rules[lit]}\"")
                                    at_least_one = True
                            adorned_rules_in_mus = rules.copy()  
                            if ad_type == AdornmentType.MUS and at_least_one:
                                for r in adornment_rewriter.non_adorned_rules:
                                    rules.append(r)

                            print("[", ", ".join(rules), "]", end="")
                            
                            if not at_least_one:
                                logger.print("**********WARNING**********")
                                logger.print("The input program was coherent")
                            else:
                                if ad_type == AdornmentType.MUS and args.print_adorned_rules:
                                    print(", \"ADORNED\": [", ", ".join(adorned_rules_in_mus), "]", end="")
                            print("}", end="")
                        except:
                            logger.print("Error while parsing pyqasp output")

                        program_pyqasp.close()
                        weak_pyqasp.close()
        finally:
            if program_name: os.unlink(program_name)
            if weak_name: os.unlink(weak_name)
            
