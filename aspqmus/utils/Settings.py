import logging

class Settings:
    OBJECTIVE_ATOM_O_NAME = "o"
    OBJECTIVE_ATOM_U_NAME = "u"
    UNSAT_ATOM_NAME = "unsatC"
    PYQASP_OPTIONS = "-g gringo -s quabs --no-wf"


class Logger:
    logger : logging.Logger
    
    def __init__(self, debug: bool):
        logging.basicConfig()
        self.logger = logging.getLogger("aspqmus")
        level = logging.DEBUG if debug else logging.INFO
        self.logger.setLevel(level)

    def print(self, str):
        self.logger.debug(str)