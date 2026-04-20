from pyqasp.pyqaspsolver import PyQASPSolver
from asp_muses.lattice import AssumptionsLattice
from bidict import frozenbidict

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

def enumerate_muses(solver, objective_atoms_ids_to_atoms, verbose=False):
	# solver: pyqasp solver
	# objective_atoms: list[str] ~ atoms

	lattice = AssumptionsLattice(list(objective_atoms_ids_to_atoms))

	while mss := lattice.maximal_subset():
		assumptions = [
			(objective_atoms_ids_to_atoms[i], True)
			for i in mss
		]

		model, exit_code = solver.solve(assumptions)

		if exit_code == 10: # SAT
			lattice.block_down(mss)

		else: # UNSAT
			qasp_core = shrink_qasp_core(solver, assumptions)
			core_lits = [objective_atoms_ids_to_atoms.inv[i] for i, _ in qasp_core]
			lattice.block_up(core_lits)

			yield tuple(i for i, j in qasp_core)


def enumerate_mcses(solver, assumptions):
	raise NotImplementedError("Not yet!")