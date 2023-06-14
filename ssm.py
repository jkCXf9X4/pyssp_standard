import xmlschema
from transformation_types import Transformation
from common_content_ssc import Annotations, Annotation
from utils import SSPStandard, SSPFile
import xml.etree.cElementTree as ET
from typing import TypedDict


class MappingEntry(TypedDict):
    source: str
    target: str
    suppress_unit_conversion: bool
    annotations: Annotations
    transformation: Transformation


class MappingList(list):

    def __repr__(self):
        print_out = """"""
        for item in self:
            print_out += f"""
        ___________________________________________________________________________________________
        Source: {item['source']}
        Target: {item['target']}
            """
        return print_out


class SSM(SSPStandard, SSPFile):

    def __init__(self, *args):
        self.__mappings: MappingList[MappingEntry] = MappingList()
        self.__annotations: Annotations

        super().__init__(*args)

    def __repr__(self):
        return f"""
        Parameter Mapping:
            Filepath: {self.file_path}
            Mappings: {len(self.mappings)}
        """

    def __read__(self):
        self.__tree = ET.parse(self.file_path)
        self.__root = self.__tree.getroot()

        mappings = self.__root.findall('ssm:MappingEntry', self.namespaces)
        for entry in mappings:
            transformation = entry.findall('ssc:Transformation', self.namespaces)
            trans = None
            if len(transformation) > 0:
                trans_type = transformation[0].tag.split('}')[-1]
                trans = Transformation(trans_type, transformation[0].attrib)
            annotations = entry.findall('ssc:Annotations', self.namespaces)
            if len(annotations) > 0:
                annotations_list = annotations[0].findall('ssc:Annotation', self.namespaces)
                anno_list = Annotations()
                for anno in annotations_list:
                    anno_item = Annotation(type_declaration=anno.get('type'))
                    anno_item.add_element(anno)
                    anno_list.add_annotation(anno_item)

            self.__mappings.append(MappingEntry(source=entry.attrib.get('source'), target=entry.attrib.get('target'),
                                                suppress_unit_conversion=False, annotations=Annotations(),
                                                transformation=trans if trans is not None else Transformation()))

    def __write__(self):
        self.__root = ET.Element('ssm:ParameterMapping', attrib={'version': '1.0',
                                                                 'xlmns:ssm': self.namespaces['ssm'],
                                                                 'xlmns:ssc': self.namespaces['ssc']})
        for mapping in self.__mappings:
            mapping_entry = ET.SubElement(self.__root, 'ssm:MappingEntry', attrib={'target': mapping.get('target'),
                                                                                   'source': mapping.get('source')})
            if mapping['transformation'] is not Transformation():
                mapping_entry.append(mapping['transformation'].element())
            if not mapping['annotations'].is_empty():
                mapping_entry.append(mapping['annotations'].root)

    def __check_compliance__(self):
        xmlschema.validate(self.file_path, self.schemas['ssm'])

    @property
    def mappings(self):
        return self.__mappings

    def add_mapping(self, source, target, suppress_unit_conversion=False, transformation=None, annotations=None):
        self.__mappings.append(MappingEntry(source=source, target=target,
                                            suppress_unit_conversion=suppress_unit_conversion,
                                            annotations=Transformation() if transformation is None else transformation,
                                            transformation=Annotations() if annotations is None else annotations))

    def edit_mapping(self, edit_target=True, *, target=None, source=None,
                     transformation: Transformation = None, suppress_unit_conversion=None,
                     annotations: Annotations = None):
        found = False
        idx = 0
        for idx, entry in enumerate(self.__mappings):
            if edit_target and entry.get('target') == target:
                found = True
                break
            elif not edit_target and entry.get('source') == source:
                found = True
                break

        if found:
            mapping_found = self.__mappings[idx]
            if target is not None:
                mapping_found['target'] = target
            if target is not None:
                mapping_found['source'] = source
            if transformation is not None:
                mapping_found['transformation'] = transformation
            if suppress_unit_conversion is not None:
                mapping_found['suppress_unit_conversion'] = suppress_unit_conversion
            if annotations is not None:
                mapping_found['annotations'] = annotations

        else:
            raise Exception("The target or source was not found, there is nothing to edit")
