from enum import Enum

class ProgramQuantifier(str, Enum):
    EXISTS = "exists"
    FORALL = "forall"
    CONSTRAINTS = "constraint"
    GLOBAL_WEAK = "global"

class QuantifiedProgram:
    rules : str
    program_type : ProgramQuantifier

    def __init__(self, rules, program_type):
        self.rules = rules
        self.program_type = program_type
        
    def exists(self):
        return self.program_type == ProgramQuantifier.EXISTS
    
    def forall(self):
        return self.program_type == ProgramQuantifier.FORALL
    
    def constraint(self):
        return self.program_type == ProgramQuantifier.CONSTRAINTS

    def quantifier(self):
        return self.program_type
    
    def global_weak(self):
        return self.program_type == ProgramQuantifier.GLOBAL_WEAK

    def __str__(self):
        quantifier = ""
        if self.program_type == ProgramQuantifier.EXISTS:
            quantifier = "%@exists"
        elif self.program_type == ProgramQuantifier.FORALL:
            quantifier = "%@forall"
        elif self.program_type == ProgramQuantifier.CONSTRAINTS:
            quantifier = "%@constraint"
        elif self.program_type == ProgramQuantifier.GLOBAL_WEAK:
            quantifier = "%@global"
        else:
            raise Exception("Unexpected quantifier")
        return f"{quantifier}\n{self.rules}\n"