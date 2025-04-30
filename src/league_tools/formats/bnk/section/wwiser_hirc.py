# -*- coding: utf-8 -*-
# @Author  : Virace
# @Email   : Virace@aliyun.com
# @Site    : x-item.com
# @Software: PyCharm
# @Create  : 2025/5/10 12:00
# @Update  : 2025/5/1 5:37
# @Detail  : 基于wwiser XML的HIRC兼容对象

from pathlib import Path
from typing import Dict, List, Optional, Any, Union

from loguru import logger
from lxml import etree

from src.league_tools.formats.bnk.section.HIRC import HIRCType, Sound, Action, Event, RanSeqCntr, SwitchCntr
from src.league_tools.utils.xml import MultiRootXmlParser


class WwiserBank:
    """
    单个Wwise资源文件的数据容器
    
    存储来自单个.bnk文件的所有HIRC相关对象
    """

    __slots__ = [
        'filename',  # 资源文件名
        'path',  # 资源文件路径
        'version',  # 资源文件版本
        'events',  # 事件对象字典，id -> 事件对象
        'event_actions',  # 动作对象字典，id -> 动作对象
        'sounds',  # 声音对象字典，id -> 声音对象
        'random_containers',  # 随机容器对象字典，id -> 随机容器对象
        'switch_containers',  # 切换容器对象字典，id -> 切换容器对象
    ]

    def __init__(self, filename: str, path: Optional[str] = None, version: Optional[str] = None):
        """
        初始化Wwise资源对象
        
        :param filename: 资源文件名
        :param path: 资源文件路径
        :param version: 资源文件版本
        """
        self.filename = filename
        self.path = path
        self.version = version

        # 初始化对象集合
        self.events = {}
        self.event_actions = {}
        self.sounds = {}
        self.random_containers = {}
        self.switch_containers = {}

    def __repr__(self) -> str:
        """字符串表示"""
        return f"<WwiserBank '{self.filename}' v{self.version}>"

    def stats(self) -> Dict[str, int]:
        """
        获取资源文件中各类对象的统计信息
        
        :return: 对象类型 -> 数量的字典
        """
        return {
            'events': len(self.events),
            'actions': len(self.event_actions),
            'sounds': len(self.sounds),
            'random_containers': len(self.random_containers),
            'switch_containers': len(self.switch_containers),
        }


class WwiserHIRC:
    """
    基于wwiser XML的HIRC兼容对象
    
    通过解析wwiser生成的XML文件，提取所有HIRC相关信息。
    支持多根节点XML文件，可处理多个.bnk资源文件。
    """

    __slots__ = [
        'banks',  # 资源文件字典，文件名 -> WwiserBank对象
        '_xml_file',  # XML文件路径
        '_xml_parser',  # XML解析器
    ]

    def __init__(self, xml_file: Optional[Union[str, Path]] = None):
        """
        初始化WwiserHIRC对象
        
        :param xml_file: wwiser生成的XML文件路径
        """
        self._xml_file = xml_file
        self._xml_parser = MultiRootXmlParser()
        self.banks = {}  # 文件名 -> WwiserBank对象

        if xml_file:
            self.load_xml(xml_file)

    def __getitem__(self, bank_name: str) -> Optional[WwiserBank]:
        """通过资源文件名访问Bank对象"""
        return self.banks.get(bank_name)

    def __contains__(self, bank_name: str) -> bool:
        """检查是否包含指定文件名的资源"""
        return bank_name in self.banks

    def __len__(self) -> int:
        """获取资源数量"""
        return len(self.banks)

    def add_bank(self, bank: WwiserBank) -> None:
        """
        添加资源对象
        
        :param bank: 要添加的Bank对象
        """
        self.banks[bank.filename] = bank

    def load_xml(self, xml_file: Union[str, Path]) -> bool:
        """
        加载并解析XML文件
        
        :param xml_file: XML文件路径
        :return: 解析是否成功
        """
        self._xml_file = xml_file
        return self._parse_xml()

    def _parse_xml(self) -> bool:
        """
        解析XML文件并填充对象
        
        :return: 解析是否成功
        """
        if not self._xml_file:
            logger.error("未指定XML文件路径")
            return False

        xml_path = Path(self._xml_file)
        if not xml_path.exists():
            logger.error(f"XML文件不存在: {xml_path}")
            return False

        try:
            logger.info(f"开始解析XML文件: {xml_path}")

            # 处理所有节点，创建Bank对象
            self._parse_banks(xml_path)

            bank_count = len(self.banks)
            logger.info(f"成功解析XML文件: {xml_path}，共 {bank_count} 个资源文件")

            # 记录每个资源的详细信息
            for bank_name, bank in self.banks.items():
                logger.debug(f"资源: {bank_name}, 统计: {bank.stats()}")

            return True

        except Exception as e:
            logger.error(f"解析XML文件失败: {e}")
            logger.exception(e)
            return False

    def _parse_banks(self, xml_path: Path) -> None:
        """
        从XML文件中解析所有资源文件
        
        :param xml_path: XML文件路径
        """
        # HIRC对象的XPath表达式
        hirc_xpath = ".//object[@name='HircChunk']/list[@name='listLoadedItem']/object"
        bank_count = 0

        # 迭代所有根节点
        for root in self._xml_parser.iter_roots(xml_path):
            filename = root.get('filename')
            if not filename:
                logger.warning(f"发现无文件名的根节点，跳过")
                continue

            # 创建资源对象
            bank = WwiserBank(
                filename=filename,
                path=root.get('path'),
                version=root.get('version')
            )

            logger.debug(f"处理资源: {filename}")

            # 查找所有HIRC对象
            obj_count = 0
            type_counts = {}

            for obj_elem in root.xpath(hirc_xpath):
                # 获取对象类型和ID
                obj_type = self._get_enum_value(obj_elem, "./field[@name='eHircType']", HIRCType)
                obj_id = self._get_int_value(obj_elem, "./field[@name='ulID']")

                if obj_type is None or obj_id is None:
                    continue

                # 处理对象，添加到正确的字典中
                self._process_object(bank, obj_type, obj_id, obj_elem)

                # 更新计数器
                obj_count += 1
                type_counts[obj_type.name] = type_counts.get(obj_type.name, 0) + 1

            # 添加到资源集合
            self.add_bank(bank)
            bank_count += 1

            logger.debug(f"资源 {filename} 共处理 {obj_count} 个对象")
            for type_name, count in type_counts.items():
                logger.debug(f"  {type_name}: {count}")

    def _process_object(self, bank: WwiserBank, obj_type: HIRCType, obj_id: int, obj_elem: etree._Element) -> None:
        """
        根据类型处理对象
        
        :param bank: 目标资源对象
        :param obj_type: 对象类型
        :param obj_id: 对象ID
        :param obj_elem: 对象元素
        """
        try:
            # 根据类型分发到不同的处理方法
            if obj_type == HIRCType.EVENT:
                bank.events[obj_id] = self._parse_event(obj_id, obj_elem)

            elif obj_type == HIRCType.ACTION:
                bank.event_actions[obj_id] = self._parse_action(obj_id, obj_elem)

            elif obj_type == HIRCType.SOUND:
                bank.sounds[obj_id] = self._parse_sound(obj_id, obj_elem)

            elif obj_type == HIRCType.RANDOM_CONTAINER:
                bank.random_containers[obj_id] = self._parse_random_container(obj_id, obj_elem)

            elif obj_type == HIRCType.SWITCH_CONTAINER:
                bank.switch_containers[obj_id] = self._parse_switch_container(obj_id, obj_elem)

            # 其他类型暂不处理
            elif obj_type in (
                    HIRCType.MUSIC_SEGMENT_CONTAINER,
                    HIRCType.MUSIC_TRACK,
                    HIRCType.MUSIC_SWITCH_CONTAINER,
                    HIRCType.MUSIC_RANDOM_CONTAINER
            ):
                logger.debug(f"暂不支持的音乐对象类型: {obj_type.name}, ID: {obj_id}")

        except Exception as e:
            logger.error(f"处理对象时出错 (类型={obj_type.name}, ID={obj_id}): {e}")

    def get_bank_names(self) -> List[str]:
        """获取所有资源文件名列表"""
        return list(self.banks.keys())

    def clear(self) -> None:
        """清空所有资源数据"""
        self.banks.clear()

    def get_event(self, event_id: int, bank_name: Optional[str] = None) -> Optional[Event]:
        """
        获取指定ID的事件对象
        
        :param event_id: 事件ID
        :param bank_name: 指定查找的资源名称，None表示搜索所有资源
        :return: 事件对象或None
        """
        if bank_name:
            bank = self.banks.get(bank_name)
            return bank.events.get(event_id) if bank else None

        # 搜索所有资源
        for bank in self.banks.values():
            if event_id in bank.events:
                return bank.events[event_id]

        return None

    def get_sound(self, sound_id: int, bank_name: Optional[str] = None) -> Optional[Sound]:
        """
        获取指定ID的声音对象
        
        :param sound_id: 声音ID
        :param bank_name: 指定查找的资源名称，None表示搜索所有资源
        :return: 声音对象或None
        """
        if bank_name:
            bank = self.banks.get(bank_name)
            return bank.sounds.get(sound_id) if bank else None

        # 搜索所有资源
        for bank in self.banks.values():
            if sound_id in bank.sounds:
                return bank.sounds[sound_id]

        return None

    # ========================= 统一的XML查询API =========================

    def _query(self, elem: etree._Element, xpath: str) -> List[etree._Element]:
        """
        执行XPath查询并返回匹配的元素列表
        
        :param elem: 起始元素
        :param xpath: XPath表达式
        :return: 匹配元素列表
        """
        return elem.xpath(xpath)

    def _get_element(self, elem: etree._Element, xpath: str) -> Optional[etree._Element]:
        """
        获取单个元素
        
        :param elem: 起始元素
        :param xpath: XPath表达式
        :return: 匹配的元素或None
        """
        results = self._query(elem, xpath)
        return results[0] if results else None

    def _get_elements(self, elem: etree._Element, xpath: str) -> List[etree._Element]:
        """
        获取多个元素
        
        :param elem: 起始元素
        :param xpath: XPath表达式
        :return: 匹配的元素列表
        """
        return self._query(elem, xpath)

    def _get_value(self, elem: etree._Element, xpath: str, default: Any = None) -> Any:
        """
        获取元素的value属性
        
        :param elem: 起始元素
        :param xpath: XPath表达式
        :param default: 默认值
        :return: 元素value属性值或默认值
        """
        element = self._get_element(elem, xpath)
        if element is not None:
            return element.get('value', default)
        return default

    def _get_int_value(self, elem: etree._Element, xpath: str, default: Optional[int] = None) -> Optional[int]:
        """
        获取整数值
        
        :param elem: 起始元素
        :param xpath: XPath表达式
        :param default: 默认值
        :return: 整数值或默认值
        """
        value = self._get_value(elem, xpath, default)
        if value is not None:
            try:
                return int(value)
            except (ValueError, TypeError):
                pass
        return default

    def _get_float_value(self, elem: etree._Element, xpath: str, default: Optional[float] = None) -> Optional[float]:
        """
        获取浮点数值
        
        :param elem: 起始元素
        :param xpath: XPath表达式
        :param default: 默认值
        :return: 浮点数值或默认值
        """
        value = self._get_value(elem, xpath, default)
        if value is not None:
            try:
                return float(value)
            except (ValueError, TypeError):
                pass
        return default

    def _get_enum_value(self, elem: etree._Element, xpath: str, enum_class: Any, default: Any = None) -> Any:
        """
        获取枚举值
        
        :param elem: 起始元素
        :param xpath: XPath表达式
        :param enum_class: 枚举类
        :param default: 默认值
        :return: 枚举值或默认值
        """
        int_value = self._get_int_value(elem, xpath)
        if int_value is not None:
            for enum_val in enum_class:
                if enum_val.value == int_value:
                    return enum_val
        return default

    def _get_int_list(self, elem: etree._Element, xpath: str) -> List[int]:
        """
        获取整数列表
        
        :param elem: 起始元素
        :param xpath: XPath表达式，应匹配具有value属性的元素
        :return: 整数列表
        """
        elements = self._get_elements(elem, xpath)
        result = []

        for element in elements:
            value = element.get('value')
            if value is not None:
                try:
                    result.append(int(value))
                except (ValueError, TypeError):
                    pass

        return result

    # ========================= 对象解析方法 =========================

    def _parse_event(self, obj_id: int, obj_elem: etree._Element) -> Event:
        """
        解析事件对象
        
        :param obj_id: 对象ID
        :param obj_elem: 对象元素
        :return: Event对象
        """
        # 获取所有动作ID
        action_ids = self._get_int_list(obj_elem,
                                        ".//list[@name='actions']/object[@name='Action']/field[@name='ulActionID']")

        return Event(
            object_id=obj_id,
            event_ids=action_ids
        )

    def _parse_action(self, obj_id: int, obj_elem: etree._Element) -> Action:
        """
        解析动作对象
        
        :param obj_id: 对象ID
        :param obj_elem: 对象元素
        :return: Action对象
        """
        # 获取动作类型
        action_type = self._get_int_value(obj_elem, "./field[@name='ulActionType']", 0)

        # 初始化参数
        id_ext = None
        switch_group_id = None
        switch_state_id = None
        state_group_id = None
        target_state_id = None

        # 根据动作类型获取特定参数
        if action_type == 0x1901:  # Switch Action
            id_ext = self._get_int_value(obj_elem, ".//object[@name='ActionInitialValues']/field[@name='idExt']")
            switch_group_id = self._get_int_value(
                obj_elem,
                ".//object[@name='ActionInitialValues']/object[@name='SwitchActionParams']/field[@name='ulSwitchGroupID']"
            )
            switch_state_id = self._get_int_value(
                obj_elem,
                ".//object[@name='ActionInitialValues']/object[@name='SwitchActionParams']/field[@name='ulSwitchStateID']"
            )
        elif action_type == 0x1204:  # State Action
            id_ext = self._get_int_value(obj_elem, ".//object[@name='ActionInitialValues']/field[@name='idExt']")
            state_group_id = self._get_int_value(
                obj_elem,
                ".//object[@name='ActionInitialValues']/object[@name='StateActionParams']/field[@name='ulStateGroupID']"
            )
            target_state_id = self._get_int_value(
                obj_elem,
                ".//object[@name='ActionInitialValues']/object[@name='StateActionParams']/field[@name='ulTargetStateID']"
            )
        else:
            # 其他动作类型
            id_ext = self._get_int_value(obj_elem, "./field[@name='idExt']")

        return Action(
            object_id=obj_id,
            action_type=action_type,
            id_ext=id_ext,
            switch_group_id=switch_group_id,
            switch_state_id=switch_state_id,
            state_group_id=state_group_id,
            target_state_id=target_state_id
        )

    def _parse_sound(self, obj_id: int, obj_elem: etree._Element) -> Sound:
        """
        解析声音对象
        
        :param obj_id: 对象ID
        :param obj_elem: 对象元素
        :return: Sound对象
        """
        # 获取媒体信息
        source_id = self._get_int_value(
            obj_elem,
            ".//object[@name='AkMediaInformation']/field[@name='sourceID']",
            0
        )

        # 获取流类型
        stream_type = self._get_int_value(
            obj_elem,
            ".//object[@name='AkBankSourceData']/field[@name='StreamType']",
            0
        )

        return Sound(
            object_id=obj_id,
            source_id=source_id,
            stream_type=stream_type
        )

    def _parse_random_container(self, obj_id: int, obj_elem: etree._Element) -> RanSeqCntr:
        """
        解析随机容器对象
        
        :param obj_id: 对象ID
        :param obj_elem: 对象元素
        :return: RanSeqCntr对象
        """
        # 获取父ID
        parent_id = self._get_int_value(
            obj_elem,
            ".//object[@name='NodeBaseParams']/field[@name='DirectParentID']",
            0
        )

        # 获取子ID列表
        child_ids = self._get_int_list(
            obj_elem,
            ".//object[@name='RanSeqCntrInitialValues']/object[@name='Children']/field[@name='ulChildID']"
        )

        return RanSeqCntr(
            object_id=obj_id,
            direct_parent_id=parent_id,
            child_ids=child_ids
        )

    def _parse_switch_container(self, obj_id: int, obj_elem: etree._Element) -> SwitchCntr:
        """
        解析切换容器对象
        
        :param obj_id: 对象ID
        :param obj_elem: 对象元素
        :return: SwitchCntr对象
        """
        # 获取父ID
        parent_id = self._get_int_value(
            obj_elem,
            ".//object[@name='NodeBaseParams']/field[@name='DirectParentID']",
            0
        )

        # 获取子ID列表
        child_ids = self._get_int_list(
            obj_elem,
            ".//object[@name='SwitchCntrInitialValues']/object[@name='Children']/field[@name='ulChildID']"
        )

        return SwitchCntr(
            object_id=obj_id,
            direct_parent_id=parent_id,
            child_ids=child_ids
        )


if __name__ == '__main__':
    # 测试代码
    hirc = WwiserHIRC(r"H:\Programming\Python\league-tools\data\banks.xml")
    print(f"已加载 {len(hirc)} 个资源文件")
    for bank_name in hirc.get_bank_names():
        bank = hirc[bank_name]
        print(f"资源: {bank.filename}, 事件数: {len(bank.events)}, 声音数: {len(bank.sounds)}")
