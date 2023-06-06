from pathlib import Path, PosixPath
from abc import ABC, abstractmethod
import xml.etree.cElementTree as ET


class SSPFile(ABC):

    @abstractmethod
    def __read__(self):
        pass

    @abstractmethod
    def __write__(self):
        pass

    @abstractmethod
    def __check_compliance__(self):
        pass

    @property
    def file_path(self):
        return self.__file_path

    def __init__(self, file_path, mode='r'):
        self.__mode = mode
        if type(file_path) is not PosixPath:
            file_path = Path(file_path)
        self.__file_path = file_path

        self.__tree = None
        self.__root = None

        if mode == 'r' or mode == 'a':
            self.__read__()
        elif mode == 'w':
            self.__write__()

    def __save__(self):
        tree = ET.ElementTree(self.__root)
        tree.write(self.__file_path, encoding='utf-8', xml_declaration=True)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.__mode in ['w', 'a']:
            self.__save__()


class SSPStandard:
    namespaces = {'ssc': 'http://ssp-standard.org/SSP1/SystemStructureCommon',
                  'ssv': 'http://ssp-standard.org/SSP1/SystemStructureParameterValues',
                  'ssb': 'http://ssp-standard.org/SSP1/SystemStructureSignalDictionary',
                  'ssm': 'http://ssp-standard.org/SSP1/SystemStructureParameterMapping',
                  'ssd': 'http://ssp-standard.org/SSP1/SystemStructureDescription'}

    __resource_path = Path('resources')
    schemas = {'ssc': __resource_path / 'SystemStructureCommon.xsd',
               'ssd': __resource_path / 'SystemStructureDescription.xsd',
               'ssd11': __resource_path / 'SystemStructureDescription11.xsd',
               'ssm': __resource_path / 'SystemStructureParameterMapping.xsd',
               'ssv': __resource_path / 'SystemStructureParameterValues.xsd',
               'ssb': __resource_path / 'SystemStructureSignalDictionary.xsd'}
