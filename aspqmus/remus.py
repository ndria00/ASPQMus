from pyqasp.pyqaspsolver import PyQASPSolver
from asp_muses.lattice import AssumptionsLattice
from asp_muses.hitting_set import HittingSet
from bidict import frozenbidict
import clingo

PYQASP_ASSUMPTION_TRUE_TRUTH_VALUE = False

def shrink_qasp_core(solver, assumptions):
	wset = set(assumptions)

	for a in assumptions:
		wset.remove(a)
		model, exit_code = solver.solve(wset)

		if exit_code == 10:
			wset.add(a)

	if len(wset) == 0:
		return []

	return wset

def parse_objective_atoms_from_pyqasp_model(pyqasp_model):
	return [clingo.parse_term(x) for x in pyqasp_model['literals'] if x.startswith('o(')]


def enumerate_muses(solver, objective_atoms_ids_to_atoms):
	return remus_mus(solver, objective_atoms_ids_to_atoms)

def enumerate_mcses(solver, objective_atoms_ids_to_atoms):
	return remus_mcs(solver, objective_atoms_ids_to_atoms)

def remus_mus(solver, objective_atoms_ids_to_atoms):
	objective_atoms = [clingo.parse_term(x) for x in objective_atoms_ids_to_atoms.values()]
	lattice = AssumptionsLattice(objective_atoms)

	found_muses = []
	found_mcses = []

	while True:
		msm = lattice.minimal_subset()
		if msm is None:
			break

		assumptions = [
			(str(i), PYQASP_ASSUMPTION_TRUE_TRUTH_VALUE)
			for i in msm
		]

		model, exit_code = solver.solve(assumptions)
		if exit_code != 10: # UNSAT
			# qasp_core = shrink_qasp_core(solver, assumptions)
			# core = [clingo.parse_term(s) for s, _ in qasp_core]
			lattice.block_up(msm)

			found_muses.append(msm)

			yield tuple(str(z) for z in msm)

		else: # SAT
			qasp_model = parse_objective_atoms_from_pyqasp_model(model)

			lattice.block_down(qasp_model)
			mcs = set(objective_atoms).difference(qasp_model)

			found_mcses.append(mcs)

def remus_mcs(solver, objective_atoms_ids_to_atoms):
	objective_atoms = [clingo.parse_term(x) for x in objective_atoms_ids_to_atoms.values()]
	lattice = AssumptionsLattice(objective_atoms)

	found_muses = []
	found_mcses = []

	while mss := lattice.maximal_subset():
		assumptions = [
			(str(i), PYQASP_ASSUMPTION_TRUE_TRUTH_VALUE)
			for i in mss
		]

		model, exit_code = solver.solve(assumptions)
		if exit_code != 10: # UNSAT
			qasp_core = shrink_qasp_core(solver, assumptions)
			core = [clingo.parse_term(s) for s, _ in qasp_core]
			lattice.block_up(core)

			found_muses.append(core)

		else: # SAT
			lattice.block_down(mss)
			mcs = set(objective_atoms).difference(mss)

			found_mcses.append(mcs)
			yield tuple(str(z) for z in mcs)