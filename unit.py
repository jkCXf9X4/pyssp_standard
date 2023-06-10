from dataclasses import dataclass, asdict
from xml.etree import cElementTree as ET
from utils import SSPElement


@dataclass
class BaseUnit:
    kg: int
    m: int
    s: int
    A: int
    K: int
    mol: int
    cd: int
    rad: int
    factor: float
    offset: float

    def __init__(self, base_unit: dict):
        for field_name, field_type in self.__annotations__.items():
            value = base_unit.get(field_name)
            if value is not None:
                if not isinstance(value, field_type):
                    try:
                        value = field_type(value)
                    except (TypeError, ValueError):
                        raise ValueError(f"Invalid value type for {field_name}. Expected {field_type}.")
                setattr(self, field_name, value)

    def to_dict(self):
        return {k: str(v) for k, v in asdict(self).items() if v is not None}


class Unit(SSPElement):

    def __init__(self, unit, base_unit: BaseUnit = None):

        self.__root = None
        self.__name = None
        self.__base_unit = None

        if type(unit) is ET.Element:
            self.from_element(unit)
        else:
            self.__name = unit
            self.__base_unit = base_unit

    def to_element(self):
        unit_entry = ET.Element('ssv:Unit', attrib={'name': self.__name})
        unit_entry.append(ET.Element('ssv:BaseUnit', attrib=self.__base_unit.to_dict()))
        return unit_entry

    def from_element(self, element):
        self.__name = element.attrib.get('name')
        base_unit = element.findall('BaseUnit')[0]
        self.__base_unit = BaseUnit(base_unit.attrib)
