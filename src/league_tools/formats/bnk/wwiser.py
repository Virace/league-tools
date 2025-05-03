# -*- coding: utf-8 -*-
# @Author  : Virace
# @Email   : Virace@aliyun.com
# @Site    : x-item.com
# @Software: PyCharm
# @Create  : 2025/5/10 12:00
# @Update  : 2025/5/4 2:31
# @Detail  : 基于wwiser XML的HIRC兼容对象，events.bnk

import os
import pickle
import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
import time

from loguru import logger
from lxml import etree

from src.league_tools.formats.bnk.section.HIRC import HIRCType, Sound, Action, Event, RanSeqCntr, SwitchCntr
from src.league_tools.utils.xml import MultiRootXmlParser


class WwiserError(Exception):
    """Wwiser解析错误的基类"""
    pass


class WwiserXmlError(WwiserError):
    """XML文件解析错误"""
    pass


class WwiserCacheError(WwiserError):
    """缓存操作错误"""
    pass


class WwiserObjectError(WwiserError):
    """对象解析错误"""
    pass


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
    支持缓存解析结果到本地，提高大文件处理性能。
    """

    __slots__ = [
        'banks',  # 资源文件字典，文件名 -> WwiserBank对象
        '_xml_file',  # XML文件路径
        '_xml_parser',  # XML解析器
        '_cache_dir',  # 缓存目录
        '_use_cache',  # 是否使用缓存
    ]

    def __init__(self, xml_file: Optional[Union[str, Path]] = None, 
                cache_dir: Optional[Union[str, Path]] = None,
                use_cache: bool = True):
        """
        初始化WwiserHIRC对象
        
        :param xml_file: wwiser生成的XML文件路径
        :param cache_dir: 缓存目录路径，None时使用默认路径
        :param use_cache: 是否使用缓存
        """
        self._xml_file = xml_file
        self._xml_parser = MultiRootXmlParser()
        self.banks = {}  # 文件名 -> WwiserBank对象
        self._use_cache = use_cache
        
        try:
            self._cache_dir = self._init_cache_dir(cache_dir)
        except Exception as e:
            error_msg = f"初始化缓存目录失败: {str(e)}"
            logger.error(error_msg)
            raise WwiserCacheError(error_msg) from e
        
        if xml_file:
            self.load_xml(xml_file)

    def _init_cache_dir(self, cache_dir: Optional[Union[str, Path]]) -> Path:
        """
        初始化缓存目录
        
        :param cache_dir: 指定的缓存目录
        :return: 缓存目录路径
        :raises WwiserCacheError: 当缓存目录创建失败时
        """
        try:
            if cache_dir:
                # 使用用户指定的缓存目录
                path = Path(cache_dir)
            else:
                # 按优先级选择缓存目录
                # 1. 环境变量
                env_cache = os.environ.get('LEAGUE_TOOLS_CACHE')
                if env_cache:
                    path = Path(env_cache)
                else:
                    # 2. 用户主目录下的.league-tools目录
                    path = Path.home() / '.league-tools' / 'cache'
            
            # 确保目录存在
            path.mkdir(parents=True, exist_ok=True)
            logger.debug(f"使用缓存目录: {path}")
            return path
            
        except Exception as e:
            error_msg = f"创建缓存目录失败: {str(e)}"
            logger.error(error_msg)
            raise WwiserCacheError(error_msg) from e

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

    def load_xml(self, xml_file: Union[str, Path], use_cache: Optional[bool] = None) -> bool:
        """
        加载并解析XML文件
        
        :param xml_file: XML文件路径
        :param use_cache: 是否使用缓存，None时使用初始化设置的值
        :return: 解析是否成功
        :raises WwiserXmlError: 当XML文件解析失败时
        :raises WwiserCacheError: 当缓存操作失败时
        """
        self._xml_file = xml_file
        if use_cache is not None:
            self._use_cache = use_cache
            
        # 清空当前数据
        self.clear()
        
        try:
            # 尝试从缓存加载
            if self._use_cache and self._load_from_cache():
                return True
                
            # 缓存加载失败，执行解析
            return self._parse_xml()
            
        except WwiserError:
            # 重新抛出已封装的错误
            raise
        except Exception as e:
            error_msg = f"加载XML文件失败: {str(e)}"
            logger.error(error_msg)
            raise WwiserXmlError(error_msg) from e

    def _generate_cache_key(self, xml_path: Path) -> str:
        """
        生成缓存文件名
        
        :param xml_path: XML文件路径
        :return: 缓存文件名
        :raises WwiserCacheError: 当生成缓存键失败时
        """
        try:
            # 获取文件基本信息
            file_name = xml_path.name
            mod_time = int(os.path.getmtime(xml_path))
            
            # 对于大文件，仅使用文件名和修改时间创建缓存键
            # 避免全文件哈希计算带来的性能开销
            cache_key = f"{file_name}_{mod_time}"
            
            # 可选：对于小文件（如<10MB），可以计算部分内容的哈希值增强唯一性
            if xml_path.stat().st_size < 10 * 1024 * 1024:  # 小于10MB
                try:
                    # 仅读取文件前8KB内容计算哈希
                    with open(xml_path, 'rb') as f:
                        content_hash = hashlib.md5(f.read(8192)).hexdigest()[:8]
                    cache_key = f"{cache_key}_{content_hash}"
                except Exception as e:
                    logger.debug(f"计算文件哈希时出错: {e}")
            
            # 返回文件名安全的缓存键
            return cache_key
            
        except Exception as e:
            error_msg = f"生成缓存键失败: {str(e)}"
            logger.error(error_msg)
            raise WwiserCacheError(error_msg) from e

    def _get_cache_path(self, xml_path: Path) -> Path:
        """
        获取缓存文件路径
        
        :param xml_path: XML文件路径
        :return: 缓存文件路径
        """
        cache_key = self._generate_cache_key(xml_path)
        return self._cache_dir / f"{cache_key}.hirc.pkl"

    def _load_from_cache(self) -> bool:
        """
        从缓存加载数据
        
        :return: 是否成功加载
        :raises WwiserCacheError: 当缓存读取失败时
        """
        if not self._xml_file:
            return False
            
        try:
            xml_path = Path(self._xml_file)
            if not xml_path.exists():
                logger.debug(f"XML文件不存在: {xml_path}")
                return False
                
            cache_path = self._get_cache_path(xml_path)
            
            # 检查缓存文件是否存在且有效
            if not cache_path.exists():
                logger.debug(f"缓存文件不存在: {cache_path}")
                return False
                
            # 比较修改时间，确保缓存是最新的
            xml_mtime = os.path.getmtime(xml_path)
            cache_mtime = os.path.getmtime(cache_path)
            
            if cache_mtime < xml_mtime:
                logger.debug(f"缓存已过期: XML文件({xml_mtime}) 比缓存文件({cache_mtime})更新")
                return False
                
            # 尝试加载缓存
            start_time = time.time()
            with open(cache_path, 'rb') as f:
                cached_data = pickle.load(f)
                    
            # 更新当前对象
            self.banks = cached_data.banks
                
            load_time = time.time() - start_time
            logger.info(f"从缓存加载成功: {cache_path}, 耗时: {load_time:.2f}秒")
            logger.info(f"已加载 {len(self)} 个资源文件")
                
            return True
                
        except Exception as e:
            error_msg = f"从缓存加载失败: {str(e)}"
            logger.error(error_msg)
            logger.debug("将重新解析XML文件")
            # 不抛出异常，而是返回False，让调用者尝试解析XML
            return False

    def _save_to_cache(self) -> bool:
        """
        保存数据到缓存
        
        :return: 是否成功保存
        :raises WwiserCacheError: 当缓存保存失败时
        """
        if not self._xml_file or not self._use_cache or len(self.banks) == 0:
            return False
            
        try:
            xml_path = Path(self._xml_file)
            cache_path = self._get_cache_path(xml_path)
            
            start_time = time.time()
            with open(cache_path, 'wb') as f:
                pickle.dump(self, f)
                    
            save_time = time.time() - start_time
            logger.info(f"缓存保存成功: {cache_path}, 耗时: {save_time:.2f}秒")
            return True
                
        except Exception as e:
            error_msg = f"缓存保存失败: {str(e)}"
            logger.error(error_msg)
            # 保存失败不是致命错误，返回False而不抛出异常
            return False

    def _parse_xml(self) -> bool:
        """
        解析XML文件并填充对象
        
        :return: 解析是否成功
        :raises WwiserXmlError: 当XML文件解析失败时
        """
        if not self._xml_file:
            error_msg = "未指定XML文件路径"
            logger.error(error_msg)
            raise WwiserXmlError(error_msg)

        xml_path = Path(self._xml_file)
        if not xml_path.exists():
            error_msg = f"XML文件不存在: {xml_path}"
            logger.error(error_msg)
            raise WwiserXmlError(error_msg)

        try:
            logger.info(f"开始解析XML文件: {xml_path}")
            start_time = time.time()

            # 处理所有节点，创建Bank对象
            self._parse_banks(xml_path)

            parse_time = time.time() - start_time
            bank_count = len(self.banks)
            logger.info(f"成功解析XML文件: {xml_path}，共 {bank_count} 个资源文件，耗时: {parse_time:.2f}秒")

            # 记录每个资源的详细信息
            for bank_name, bank in self.banks.items():
                logger.debug(f"资源: {bank_name}, 统计: {bank.stats()}")
                
            # 解析成功后保存到缓存
            if self._use_cache:
                try:
                    self._save_to_cache()
                except Exception as e:
                    logger.warning(f"保存缓存失败，但不影响解析结果: {str(e)}")

            return True

        except WwiserError:
            # 重新抛出已封装的错误
            raise
        except Exception as e:
            error_msg = f"解析XML文件失败: {str(e)}"
            logger.error(error_msg)
            logger.exception(e)
            raise WwiserXmlError(error_msg) from e

    def _parse_banks(self, xml_path: Path) -> None:
        """
        从XML文件中解析所有资源文件
        
        :param xml_path: XML文件路径
        :raises WwiserXmlError: 当解析资源文件失败时
        """
        try:
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
                    
        except WwiserError:
            # 重新抛出已封装的错误
            raise
        except Exception as e:
            error_msg = f"解析资源文件失败: {str(e)}"
            logger.error(error_msg)
            raise WwiserXmlError(error_msg) from e

    def _process_object(self, bank: WwiserBank, obj_type: HIRCType, obj_id: int, obj_elem: etree._Element) -> None:
        """
        根据类型处理对象
        
        :param bank: 目标资源对象
        :param obj_type: 对象类型
        :param obj_id: 对象ID
        :param obj_elem: 对象元素
        :raises WwiserObjectError: 当对象处理失败时
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
            error_msg = f"处理对象时出错 (类型={obj_type.name}, ID={obj_id}): {str(e)}"
            logger.error(error_msg)
            raise WwiserObjectError(error_msg) from e

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

    def clear_cache(self, xml_file: Optional[Union[str, Path]] = None) -> int:
        """
        清除缓存文件
        
        :param xml_file: 指定要清除缓存的XML文件，None表示清除所有缓存
        :return: 清除的缓存文件数量
        :raises WwiserCacheError: 当清除缓存失败时
        """
        try:
            if xml_file:
                # 清除指定文件的缓存
                xml_path = Path(xml_file)
                cache_path = self._get_cache_path(xml_path)
                if cache_path.exists():
                    cache_path.unlink()
                    logger.info(f"已清除缓存: {cache_path}")
                    return 1
                return 0
            else:
                # 清除所有缓存
                count = 0
                for cache_file in self._cache_dir.glob("*.hirc.pkl"):
                    cache_file.unlink()
                    count += 1
                logger.info(f"已清除 {count} 个缓存文件")
                return count
                
        except Exception as e:
            error_msg = f"清除缓存文件失败: {str(e)}"
            logger.error(error_msg)
            raise WwiserCacheError(error_msg) from e

    def set_cache_dir(self, cache_dir: Union[str, Path]) -> None:
        """
        设置缓存目录
        
        :param cache_dir: 新的缓存目录
        :raises WwiserCacheError: 当设置缓存目录失败时
        """
        try:
            self._cache_dir = self._init_cache_dir(cache_dir)
            logger.info(f"已设置缓存目录: {self._cache_dir}")
        except Exception as e:
            error_msg = f"设置缓存目录失败: {str(e)}"
            logger.error(error_msg)
            raise WwiserCacheError(error_msg) from e

    def get_cache_size(self) -> int:
        """
        获取缓存目录总大小(字节)
        
        :return: 缓存大小(字节)
        :raises WwiserCacheError: 当获取缓存大小失败时
        """
        try:
            total_size = 0
            for cache_file in self._cache_dir.glob("*.hirc.pkl"):
                total_size += cache_file.stat().st_size
            return total_size
        except Exception as e:
            error_msg = f"获取缓存大小失败: {str(e)}"
            logger.error(error_msg)
            raise WwiserCacheError(error_msg) from e

    def get_cache_file_count(self) -> int:
        """
        获取缓存文件数量
        
        :return: 缓存文件数量
        :raises WwiserCacheError: 当获取缓存文件数量失败时
        """
        try:
            return len(list(self._cache_dir.glob("*.hirc.pkl")))
        except Exception as e:
            error_msg = f"获取缓存文件数量失败: {str(e)}"
            logger.error(error_msg)
            raise WwiserCacheError(error_msg) from e
