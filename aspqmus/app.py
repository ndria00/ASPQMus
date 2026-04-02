import argparse
import tempfile
import subprocess
import re
import json

from aspqmus.rewriters.AdornmentProgramRewriter import AdornmentProgramRewriter, AdornmentType, AdornmentOption
from aspqmus.utils import Settings, Logger

def entrypoint():
    parser = argparse.ArgumentParser(prog = "aspqmus", description = "TODO\n")

    parser.add_argument('--problem', help="path to problem file\n", required=True)
    parser.add_argument('--mus', help="compute mus of input ptogram - by default MCSes are computed\n", required=False, action="store_true")
    parser.add_argument('--adornment', choices=list(AdornmentOption), default=AdornmentOption.FACTS_ONLY, help='choose adornment option')
    parser.add_argument('--pyqasp', help="path to pyqasp executable - if not specified it assumes that the solver is callable as pyqasp\n", required=False)
    parser.add_argument('--debug', help="enable debug prints\n", required=False, action="store_true")

    args = parser.parse_args()

    encoding_path = args.problem
    try:
        encoding_program = "\n".join(open(encoding_path).readlines())
    except:
        print("Could not open problem file")
        exit(1)

    logger = Logger(args.debug)
    ad_option = AdornmentOption(args.adornment)
    ad_type = AdornmentType("mus") if args.mus else AdornmentType("mcs")
    adornment_rewriter = AdornmentProgramRewriter(encoding_program, Settings.OBJECTIVE_ATOM_O_NAME, Settings.OBJECTIVE_ATOM_U_NAME,Settings.UNSAT_ATOM_NAME, ad_type, ad_option)

    for program in adornment_rewriter.programs:
        logger.print(program)
    logger.print(adornment_rewriter.global_weak)

    if args.pyqasp:
        pyqasp_executable = args.pyqasp
    else:
        pyqasp_executable = "pyqasp"

    with tempfile.NamedTemporaryFile(mode="w", prefix="apqmus_", suffix=".aspq", delete_on_close=False) as program, tempfile.NamedTemporaryFile(mode="w", prefix="apqmus_", suffix=".asp", delete_on_close=False) as weak:
        for prg in adornment_rewriter.programs:
            program.write(str(prg))
        weak.write(adornment_rewriter.global_weak.rules)
        program.close()
        weak.close()
        with open(program.name, mode="r") as program_pyqasp ,open(weak.name, mode="r") as weak_pyqasp:
            command = [pyqasp_executable, "-g", "gringo", "-s" , "quabs", "--no-wf", "-w", weak_pyqasp.name, program_pyqasp.name]
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
                    for literal in optimum_as_json["literals"]:
                        lit = str(literal)
                        if ad_type == AdornmentType.MCS:
                            #MCS is the complement of true objective atoms
                            if not re.match(f"not {Settings.OBJECTIVE_ATOM_O_NAME}\\(\d+,\d+\\)", lit) is None: 
                                print(adornment_rewriter.objective_atoms_to_rules[lit.replace("not ", "")])
                        else:
                            if not re.match(f"{Settings.OBJECTIVE_ATOM_U_NAME}\\(\d+,\d+\\)", lit) is None: 
                                print(adornment_rewriter.objective_atoms_to_rules[lit])
                except:
                    print("Error while parsing pyqasp output")
                    exit(1)

                program_pyqasp.close()
                weak_pyqasp.close()
                exit(proc.returncode)