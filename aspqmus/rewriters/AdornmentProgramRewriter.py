import re
from enum import StrEnum
import clingo
from clingo.ast import parse_string

from aspqmus.language import QuantifiedProgram, ProgramQuantifier


class AdornmentType(StrEnum):
    MUS = "mus"
    MCS = "mcs"

class AdornmentOption(StrEnum):
    CONSTRAINT_PROGRAM_ONLY = "constraint_program"     # adorn only rules from constrant program - no matter if facts or not
    FACTS_ONLY = "facts"                               # adorn all facts in all programs - leave rules not adorned
    RULES_ONLY = "rules"                               # adorn rules in all programs and not facts
    ALL = "all"                                        # adorn everything

class AdornmentProgramRewriter(clingo.ast.Transformer):

    programs: list[QuantifiedProgram]
    global_weak : QuantifiedProgram
    cur_program_rules : list[str]
    cur_program_quantifier : ProgramQuantifier
    program_is_open : bool
    encoding_program : str
    adornment_type : AdornmentType
    adornment_option : AdornmentOption
    objective_o_predicate_name : str
    objective_atoms_to_rules : dict
    objective_u_predicate_name : str
    overall_rule_id : int
    current_program_id : int
    current_program_rule_id : int
    objective_atoms_o : list
    objective_atoms_u : list
    compute_dual : bool
    unsat_predicate_name : str
    non_adorned_rules : list

    def __init__(self, encoding_program, objective_o_predicate_name, objective_u_predicate_name, unsat_predicate_name, adornment_type, adornment_option) -> None:
        super().__init__()
        self.programs = []
        self.global_weak = None
        self.cur_program_rules = []
        self.cur_program_quantifier = ProgramQuantifier.CONSTRAINTS
        self.program_is_open = False
        self.constraint_program = None
        self.encoding_program = encoding_program
        self.adornment_type = adornment_type
        self.adornment_option = adornment_option
        self.objective_o_predicate_name = objective_o_predicate_name
        self.objective_atoms_to_rules = dict()
        self.objective_u_predicate_name = objective_u_predicate_name
        self.current_program_id = -1
        self.overall_rule_id = 0
        self.current_program_rule_id = 0
        self.objective_atoms_o = []
        self.objective_atoms_u = []
        self.compute_dual = adornment_type == AdornmentType.MUS
        self.unsat_predicate_name = unsat_predicate_name
        self.non_adorned_rules = []
        parse_string(encoding_program, lambda stm: (self(stm)))
        self.closed_program()

        #add exists program over objective atoms - of the form o if doing MCS, of the form u otherwise
        if self.adornment_type == AdornmentType.MCS:
            obj_atom_choice = "{" + ";".join(self.objective_atoms_o) +"}.\n"
        else:
            obj_atom_choice = "{" + ";".join(self.objective_atoms_u) +"}.\n"

        self.programs = [QuantifiedProgram(obj_atom_choice, ProgramQuantifier.EXISTS)] + self.programs
        
        #input program does not contain constraint
        #if adorning for MCS create empty constraint program, otherwise add incoherent constraint program
        if self.programs[len(self.programs)-1].program_type != ProgramQuantifier.CONSTRAINTS:
            constraint_program = None
            if self.adornment_type == AdornmentType.MCS:
                constraint_program = QuantifiedProgram("", ProgramQuantifier.CONSTRAINTS)
            else:
                unsat_constraint = f":- not {self.unsat_predicate_name}."
                constraint_program = QuantifiedProgram(unsat_constraint, ProgramQuantifier.CONSTRAINTS)
            self.programs.append(constraint_program)
            
        #add forall program after choice which enforces atoms from choice program and leaves the remaining free
        if self.adornment_type == AdornmentType.MUS:
            obj_atom_choice = "{" + ";".join(self.objective_atoms_o) +"}.\n"
            obj_atom_o_if_u = f"{self.objective_o_predicate_name}(X,Y):-{self.objective_u_predicate_name}(X,Y)."
            force_u_program = QuantifiedProgram(f"{obj_atom_choice}{obj_atom_o_if_u}", ProgramQuantifier.FORALL)
            self.programs = [self.programs[0]] + [force_u_program] + self.programs[1:]

        #construct global weak program
        weight = "-1" if self.adornment_type == AdornmentType.MCS else "1"       
        self.global_weak = QuantifiedProgram(f":~ {self.objective_o_predicate_name if self.adornment_type == AdornmentType.MCS else self.objective_u_predicate_name}(X,Y). [{weight}@1,X,Y]", ProgramQuantifier.GLOBAL_WEAK)

    def visit_Comment(self, value):
        value_str = str(value)
        is_exist_directive = not re.match("%@exists", value_str) is None
        is_forall_directive = not re.match("%@forall", value_str) is None
        is_constraint_directive = not re.match("%@constraint", value_str) is None
        is_global_weak_directive = not re.match("%@global", value_str) is None

        if is_exist_directive or is_forall_directive or is_constraint_directive or is_global_weak_directive:
            self.closed_program()
    
        if is_exist_directive:
            if not self.constraint_program is None:
                raise Exception("Constraint program must appear as last program")
            self.program_is_open = True
            self.cur_program_quantifier = ProgramQuantifier.EXISTS
            self.open_program()
        elif is_forall_directive:
            if not self.constraint_program is None:
                raise Exception("Constraint program must appear as last program")
            self.program_is_open = True
            self.cur_program_quantifier = ProgramQuantifier.FORALL
            self.open_program()

        elif is_constraint_directive:
            self.program_is_open = True
            self.cur_program_quantifier = ProgramQuantifier.CONSTRAINTS
            self.open_program()
        elif is_global_weak_directive:
            raise Exception("The program that is being debugged cannot include global weak constraints")
        # else:
            #print("Spurious comment subprogram start")
    
    def open_program(self):
        self.current_program_rule_id = 0
        self.current_program_id += 1

    def visit_Rule(self, node):
        rewritten_rule_str = None
        # adorn only rules from constraint program - no matter if facts or not
        if self.adornment_option == AdornmentOption.FACTS_ONLY:
            if len(node.body) > 0 or node.head.ast_type == clingo.ast.ASTType.Aggregate or node.head.ast_type == clingo.ast.ASTType.Disjunction:
                rewritten_rule_str = self.asp_rule_to_string(node.head, node.body)
                self.non_adorned_rules.append(f"\"{rewritten_rule_str}\"")
            else:
                obj_atom = self.construct_objective_atom(node)
                rewritten_body = [b for b in node.body] + [obj_atom]
                rewritten_rule_str = self.asp_rule_to_string(node.head, rewritten_body)
        # adorn all facts in all programs - leave rules not adorned
        elif self.adornment_option == AdornmentOption.CONSTRAINT_PROGRAM_ONLY:
            if self.cur_program_quantifier == ProgramQuantifier.CONSTRAINTS:
                obj_atom = self.construct_objective_atom(node)
                rewritten_body = [b for b in node.body] + [obj_atom]
                rewritten_rule_str = self.asp_rule_to_string(node.head, rewritten_body)
            else:
                rewritten_rule_str = self.asp_rule_to_string(node.head, node.body)
                self.non_adorned_rules.append(f"\"{rewritten_rule_str}\"")
        # adorn rules in all programs and not facts
        elif self.adornment_option == AdornmentOption.RULES_ONLY:
            if len(node.body) == 0 and not node.head.ast_type == clingo.ast.ASTType.Aggregate and not node.head.ast_type == clingo.ast.ASTType.Disjunction:
                rewritten_rule_str = self.asp_rule_to_string(node.head, node.body)
                self.non_adorned_rules.append(f"\"{rewritten_rule_str}\"")
            else:
                obj_atom = self.construct_objective_atom(node)
                rewritten_body = [b for b in node.body] + [obj_atom]
                rewritten_rule_str = self.asp_rule_to_string(node.head, rewritten_body)
        elif self.adornment_option == AdornmentOption.ALL:
                obj_atom = self.construct_objective_atom(node)
                rewritten_body = [b for b in node.body] + [obj_atom]
                rewritten_rule_str = self.asp_rule_to_string(node.head, rewritten_body)
        #flip constraints in constraint program when adornig for MUS
        if self.compute_dual and self.cur_program_quantifier == ProgramQuantifier.CONSTRAINTS and node.head.ast_type == clingo.ast.ASTType.Literal and node.head.atom.ast_type == clingo.ast.ASTType.BooleanConstant:
            rewritten_rule_str = f"{self.unsat_predicate_name}{rewritten_rule_str}"

        self.cur_program_rules.append(rewritten_rule_str)
        return node.update(**self.visit_children(node))
    
    def closed_program(self):
        if self.program_is_open:
            program_quantifier = self.cur_program_quantifier
            if self.compute_dual:
                if program_quantifier != ProgramQuantifier.CONSTRAINTS:
                    program_quantifier = ProgramQuantifier.EXISTS if self.cur_program_quantifier == ProgramQuantifier.FORALL else ProgramQuantifier.FORALL
                elif program_quantifier == ProgramQuantifier.CONSTRAINTS:
                    self.cur_program_rules.append(f":- not {self.unsat_predicate_name}.")
            program_str = "\n".join(self.cur_program_rules)
            program = QuantifiedProgram(program_str, program_quantifier)
            self.programs.append(program)
            self.program_is_open = False
        self.cur_program_rules = []
    
    #no weak constraints allowed in programs
    def visit_Minimize(self, node):
        raise Exception("Unexpected local constraint")
    
    def construct_objective_atom(self, node):
        self.current_program_rule_id += 1
        self.overall_rule_id += 1
        obj_atom_o = clingo.ast.Function(
            node.location,
            self.objective_o_predicate_name,
            [
                clingo.ast.SymbolicTerm(node.location, clingo.Number(self.current_program_id)),
                clingo.ast.SymbolicTerm(node.location, clingo.Number(self.current_program_rule_id)),
            ],
            False
        )
        obj_atom_u = clingo.ast.Function(
            node.location,
            self.objective_u_predicate_name,
            [
                clingo.ast.SymbolicTerm(node.location, clingo.Number(self.current_program_id)),
                clingo.ast.SymbolicTerm(node.location, clingo.Number(self.current_program_rule_id)),
            ],
            False
        )
        self.objective_atoms_o.append(str(obj_atom_o))
        if self.adornment_type == AdornmentType.MCS:
            self.objective_atoms_to_rules[str(obj_atom_o)] = self.asp_rule_to_string(node.head, node.body)
        else:
            self.objective_atoms_to_rules[str(obj_atom_u)] = self.asp_rule_to_string(node.head, node.body)
        self.objective_atoms_u.append(str(obj_atom_u))
        return obj_atom_o
    
    def asp_rule_to_string(self, rule_head, rule_body):
        head_str = ""
        if rule_head.ast_type == clingo.ast.ASTType.Literal:
            if not rule_head.atom.ast_type == clingo.ast.ASTType.BooleanConstant:
                head_str = str(rule_head.atom)
        body_str = ",".join(str(elem) for elem in rule_body)
        
        return f"{head_str}." if body_str == "" else f"{head_str}:-{body_str}."