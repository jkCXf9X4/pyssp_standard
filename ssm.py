from transformation_types import Transformation
from utils import SSPStandard
import xml.etree.cElementTree as ET
from pathlib import Path, PosixPath
from typing import TypedDict, List


class Annotations:
    pass


class MappingEntry(TypedDict):
    source: str
    target: str
    suppress_unit_conversion: bool
    annotations: Annotations
    transformation: Transformation


class SSM(SSPStandard):

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.__mode in ['w', 'a']:
            self.__save__()

    def __init__(self, file_path, mode='r'):
        self.__mode = mode
        if type(file_path) is not PosixPath:
            file_path = Path(file_path)
        self.file_path = file_path

        self.__tree = None
        self.__root = None

        self.__mappings: List[MappingEntry] = []
        self.__annotations = []

        if mode == 'r' or mode == 'a':
            self.__read__()
        elif mode == 'w':
            self.__write__()

    def __read__(self):
        self.__tree = ET.parse(self.file_path)
        self.__root = self.__tree.getroot()

        mappings = self.__root.findall('ssm:MappingEntry', self.namespaces)
        for entry in mappings:
            self.__mappings.append(MappingEntry(source=entry.attrib.get('source'), target=entry.attrib.get('target'),
                                                suppress_unit_conversion=False, annotations=Annotations(),
                                                transformation=Transformation()))

    def __write__(self):
        pass

    def __save__(self):
        pass

    def __check_compliance__(self):
        pass
