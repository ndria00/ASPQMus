from pyqasp.pyqaspsolver import PyQASPSolver
from asp_muses.lattice import AssumptionsLattice
from asp_muses.hitting_set import HittingSet
from bidict import frozenbidict

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


def enumerate_muses(solver, objective_atoms_ids_to_atoms):
	return remus(solver, objective_atoms_ids_to_atoms, 'MUS')

def enumerate_mcses(solver, objective_atoms_ids_to_atoms):
	return remus(solver, objective_atoms_ids_to_atoms, 'MCS')

def remus(solver, objective_atoms_ids_to_atoms, mode):
	if mode not in ('MCS', 'MUS'):
		raise RuntimeError(f"Unknown REMUS mode: {mode}")
	# solver: pyqasp solver
	# objective_atoms: list[str] ~ atoms

	lattice = AssumptionsLattice(list(objective_atoms_ids_to_atoms))

	found_muses = []
	found_mcses = []

	while mss := lattice.maximal_subset():
		assumptions = [
			(objective_atoms_ids_to_atoms[i], PYQASP_ASSUMPTION_TRUE_TRUTH_VALUE)
			for i in mss
		]

		model, exit_code = solver.solve(assumptions)
		if exit_code != 10: # UNSAT
			qasp_core = shrink_qasp_core(solver, assumptions)
			core_lits = [objective_atoms_ids_to_atoms.inv[i] for i, _ in qasp_core]
			lattice.block_up(core_lits)

			found_muses.append(core_lits)

			if mode == 'MUS':
				yield tuple(i for i, j in qasp_core)

		else: # SAT
			lattice.block_down(mss)
			mcs_lits = set(objective_atoms_ids_to_atoms).difference(mss)

			# sbagliato devo sistemare
			mcs = [objective_atoms_ids_to_atoms[i] for i in mcs_lits]

			found_mcses.append(mcs_lits)
			if mode == 'MCS':
				yield tuple(mcs)


	if mode != 'MCS':
        return
	
	mhs = HittingSet(list(objective_atoms_ids_to_atoms))
	for known_mcs in found_mcses:
		mhs.add(known_mcs)

	for mcs in mhs.mhs():
		if mode == 'MCS':
			yield tuple(objective_atoms_ids_to_atoms[i] for i in mcs)	