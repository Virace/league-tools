# 🐍 In the face of ambiguity, refuse the temptation to guess.
# 🐼 面对不确定性，拒绝妄加猜测
# @Author  : Virace
# @Email   : Virace@aliyun.com
# @Site    : x-item.com
# @Software: PyCharm
# @Create  : 2025/5/8 15:10
# @Update  : 2025/7/26 0:45
# @Detail  : 音频哈希和事件映射处理(警告！警告！警告！ 以下均为AI生成且未作任何测试)


import os
from collections import OrderedDict, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Set, Union

from loguru import logger

from league_tools.core import BinaryReader
from league_tools.core.section import WemFile
from league_tools.formats.bin.models import StringHash
from league_tools.formats.bin.parser import BIN
from league_tools.formats.bnk.parser import BNK
from league_tools.formats.bnk.wwiser import WwiserBank, WwiserHIRC
from league_tools.formats.wad.parser import WAD
from league_tools.utils.type_hints import StrPath
from league_tools.utils.wwiser import WwiserManager


class BinAggregator:
    """BIN资源聚合器

    用于整合多个皮肤BIN文件资源，简化多BIN处理流程
    """

    def __init__(self):
        """初始化BIN聚合器"""
        self.theme_music = []  # 所有主题音乐单元
        self.bank_units_by_category = {}  # 按category聚合的bank_units

    @classmethod
    def from_bin_sources(
        cls, bin_sources: List[Union[StrPath, bytes, BIN]]
    ) -> "BinAggregator":
        """从多个来源创建聚合器

        :param bin_sources: bin文件路径、二进制数据或BIN对象列表
        :return: BinAggregator实例
        """
        aggregator = cls()

        # 转换bin_sources为BIN对象
        bin_objects = []
        for source in bin_sources:
            try:
                if isinstance(source, (str, Path)) or hasattr(source, "__fspath__"):
                    bin_objects.append(BIN(source))
                elif isinstance(source, bytes):
                    bin_objects.append(BIN(source))
                elif isinstance(source, BIN):
                    bin_objects.append(source)
                else:
                    logger.warning(f"不支持的BIN源类型: {type(source)}，已跳过")
            except Exception as e:
                logger.error(f"解析BIN源失败: {e}")

        if not bin_objects:
            logger.error("没有有效的BIN对象，无法创建聚合器")
            return aggregator

        # 过滤只保留皮肤BIN
        skin_bins = []
        for bin_obj in bin_objects:
            if hasattr(bin_obj, "is_skin_file") and bin_obj.is_skin_file:
                skin_bins.append(bin_obj)
            else:
                logger.warning("跳过非皮肤BIN文件")

        if not skin_bins:
            logger.error("没有有效的皮肤BIN文件，聚合器将为空")
            return aggregator

        # 处理所有有效BIN对象
        for bin_obj in skin_bins:
            aggregator.add_bin(bin_obj)

        return aggregator

    def add_bin(self, bin_obj: BIN) -> None:
        """添加一个BIN对象到聚合器

        :param bin_obj: BIN对象
        """
        for group in bin_obj.data:
            for unit in group.bank_units:
                category = unit.category

                # 特殊处理theme_music
                if "theme_music" in category.lower():
                    self.theme_music.append(unit)
                    continue

                # 合并同category的bank_units，保留事件数量最多的
                if category not in self.bank_units_by_category or len(
                    unit.events
                ) > len(self.bank_units_by_category[category].events):
                    self.bank_units_by_category[category] = unit

    def get_categories(self) -> List[str]:
        """获取所有category

        :return: category列表
        """
        return list(self.bank_units_by_category.keys())

    def iterate_units(
        self, sfx_filter: bool = False, vo_filter: bool = False
    ) -> Iterator[Any]:
        """迭代所有bank_units (包括theme_music)

        :param sfx_filter: 是否只返回SFX资源
        :param vo_filter: 是否只返回VO资源
        :yield: bank_unit对象
        """
        # 先输出普通单元
        for category, unit in self.bank_units_by_category.items():
            resource_type = determine_resource_type(category)

            # 根据过滤条件跳过
            if sfx_filter and resource_type != "SFX":
                continue
            if vo_filter and resource_type != "VO":
                continue

            yield unit

        # 再输出theme_music单元
        for unit in self.theme_music:
            resource_type = determine_resource_type(unit.category)
            category_suffix = (
                unit.category.split("_")[-1] if "_" in unit.category else ""
            )

            # 根据过滤条件和后缀跳过
            if sfx_filter and (resource_type != "MUS" or category_suffix != "SFX"):
                continue
            if vo_filter and (resource_type != "MUS" or category_suffix != "VO"):
                continue

            yield unit

    def is_empty(self) -> bool:
        """检查聚合器是否为空

        :return: 如果聚合器为空则返回True
        """
        return len(self.bank_units_by_category) == 0 and len(self.theme_music) == 0


class AudioFiles:
    """音频文件服务

    负责音频文件的加载和哈希表生成
    """

    @staticmethod
    def load_files(
        audio_file: Union[StrPath, bytes],
        get_data=True,
        hash_table: Optional[List[int]] = None,
    ) -> List[WemFile]:
        """从音频文件加载WEM文件列表

        :param audio_file: 音频文件(bnk、wpk)路径或二进制数据
        :param get_data: 是否获取音频文件数据
        :param hash_table: 哈希表，用于过滤只提取特定ID的文件
        :return: WemFile对象列表
        """
        # 确定文件类型
        if isinstance(audio_file, str) or hasattr(audio_file, "__fspath__"):
            audio_ext = Path(audio_file).suffix
        elif isinstance(audio_file, bytes):
            br = BinaryReader(audio_file)
            head = br.customize("<4s")
            audio_ext = ".wpk" if head == b"r3d2" else ".bnk"
        else:
            logger.error(f"不支持的音频文件类型: {type(audio_file)}")
            return []

        # 解析WPK文件
        if audio_ext == ".wpk":
            from league_tools.formats.wpk.parser import WPK

            wpk = WPK(audio_file)

            if hash_table:
                for file in wpk.files[:]:  # 使用切片创建副本以避免修改迭代中的列表
                    if file.id not in hash_table:
                        wpk.files.remove(file)

            audio_files, data_call = wpk.files, wpk.get_files_data
        # 解析BNK文件
        else:
            bnk = BNK(audio_file)
            data_section = bnk.get_data_files()

            if data_section:
                if hash_table:
                    for file in data_section.files[:]:  # 使用切片创建副本
                        if file.id not in hash_table:
                            data_section.files.remove(file)

                audio_files, data_call = (
                    data_section.files,
                    lambda: bnk.objects[b"DATA"].get_files(data_section),
                )
            else:
                audio_files, data_call = [], lambda: None

        # 获取音频数据
        if get_data and audio_files:
            data_call()

        return audio_files

    @staticmethod
    def map_events_to_audio(
        event_hashtable: List[StringHash], audio_file: Union[StrPath, bytes]
    ) -> Dict[str, List[int]]:
        """创建事件到音频ID的映射

        :param event_hashtable: 事件哈希表，通过EventMapper.collect_audio_ids()获取
        :param audio_file: 音频文件路径(bnk或wpk)或二进制数据
        :return: 事件名称到音频ID列表的有序字典
        """
        logger.info(f"构建音频哈希表, 事件数: {len(event_hashtable)}")

        # 1. 获取音频文件列表
        audio_files = AudioFiles.load_files(audio_file, False)
        if not audio_files:
            logger.warning("未从音频数据中找到任何音频文件")
            return OrderedDict()

        logger.info(f"从音频文件中找到 {len(audio_files)} 个音频文件")

        # 2. 创建映射
        ret = defaultdict(set)

        # 2.1 处理没有对应事件的音频文件
        event_ids = [ht.hash for ht in event_hashtable]
        file_ids = [file.id for file in audio_files]
        no_event = list(set(file_ids).difference(set(event_ids)))
        no_event_files = [file for file in audio_files if file.id in no_event]

        if no_event_files:
            logger.info(f"找到 {len(no_event_files)} 个无对应事件的音频文件")
            for file in no_event_files:
                ret["No_Event"].add(file.id)

        # 2.2 处理有对应事件的音频文件
        match_count = 0
        for ht in event_hashtable:
            for file in audio_files:
                if ht.hash == file.id:
                    ret[ht.string].add(file.id)
                    match_count += 1

        logger.info(f"找到 {match_count} 个事件-音频ID匹配")

        # 3. 排序结果
        sort_keys = sorted(ret.keys())
        order_ret = OrderedDict()
        for key in sort_keys:
            order_ret[key] = sorted(ret[key])

        return order_ret


class EventMapper:
    """事件映射器

    负责从事件到音频ID的映射逻辑
    """

    def __init__(self, bank: WwiserBank):
        """初始化映射器

        :param bank: WwiserBank对象
        """
        self.bank = bank

    def match_sounds(self, event_str: str, event_id: int) -> List[StringHash]:
        """匹配声音对象并返回结果

        :param event_str: 事件名称字符串
        :param event_id: 事件ID
        :return: StringHash对象列表
        """
        res = []
        for sound_id, sound in self.bank.sounds.items():
            if sound_id == event_id:
                logger.debug(
                    f"发现资源文件: {event_str}, {sound.source_id}, (Sound直接匹配)"
                )
                res.append(StringHash(string=event_str, hash=sound.source_id))
        return res

    def trace_container(
        self, event_str: str, event_id: int, visited: Set[int], container_type: str
    ) -> List[StringHash]:
        """追踪容器内容

        :param event_str: 事件名称字符串
        :param event_id: 事件ID
        :param visited: 已访问的对象ID集合（防止循环引用）
        :param container_type: 容器类型，"random"或"switch"
        :return: StringHash对象列表
        """
        # 防止循环引用
        if event_id in visited:
            return []

        visited.add(event_id)
        res = []

        # 获取正确的容器字典
        containers = (
            self.bank.random_containers
            if container_type == "random"
            else self.bank.switch_containers
        )

        for container_id, container in containers.items():
            if container_id == event_id:
                logger.debug(
                    f"处理{container_type}容器: ID={container_id}, 事件={event_str}"
                )

                # 处理容器中的每个子对象
                for child_id in container.child_ids:
                    # 1. 检查子对象是否为声音对象
                    sound_results = self.match_sounds(event_str, child_id)
                    if sound_results:
                        for result in sound_results:
                            result_with_container = StringHash(
                                string=result.string,
                                hash=result.hash,
                                container_id=container_id,
                            )
                            res.append(result_with_container)

                    # 2. 递归处理子容器
                    # 随机容器
                    random_results = self.trace_container(
                        event_str, child_id, visited.copy(), "random"
                    )
                    res.extend(random_results)

                    # 切换容器
                    switch_results = self.trace_container(
                        event_str, child_id, visited.copy(), "switch"
                    )
                    res.extend(switch_results)

        return res

    def extract_action_targets(self, event: Any, event_name: str) -> List[StringHash]:
        """从动作提取目标对象

        :param event: Event对象
        :param event_name: 事件名称
        :return: StringHash对象列表
        """
        res = []

        # 处理事件关联的动作
        for action_id in event.event_ids:
            action = self.bank.event_actions.get(action_id)
            if not action:
                continue

            # 动作类型1027是"播放"动作
            if action.action_type == 1027:
                logger.debug(
                    f"处理播放动作: ID={action_id}, 引用ID={action.id_ext}, 事件={event_name}"
                )

                # 1. 尝试直接匹配声音对象
                sound_results = self.match_sounds(event_name, action.id_ext)
                res.extend(sound_results)

                # 2. 处理可能的容器
                visited = set()
                # 随机容器
                random_results = self.trace_container(
                    event_name, action.id_ext, visited, "random"
                )
                res.extend(random_results)

                # 切换容器
                switch_results = self.trace_container(
                    event_name, action.id_ext, visited, "switch"
                )
                res.extend(switch_results)

        return res

    def collect_audio_ids(self, event_data: List[StringHash]) -> List[StringHash]:
        """收集事件关联的所有音频ID

        :param event_data: 事件数据列表
        :return: 事件名称到音频ID的映射列表
        """
        result = []

        # 处理每个BIN事件
        for string_hash in event_data:
            event_name = string_hash.string
            event_id = string_hash.hash

            # 跳过无效事件
            if not event_name:
                logger.warning(f"跳过无效事件: ID={event_id}, 名称为空")
                continue

            logger.debug(f"处理事件: {event_name} (ID={event_id})")

            # 查找事件
            event = self.bank.events.get(event_id)
            if not event:
                logger.debug(f"未找到事件: {event_name} (ID={event_id})")
                continue

            # 处理事件动作
            event_results = self.extract_action_targets(event, event_name)
            if event_results:
                result.extend(event_results)
            else:
                logger.warning(f"未找到事件 {event_name} 的相关音频ID")

        return result


def map_events_to_audio_ids(
    bank: WwiserBank, bin_events: List[StringHash]
) -> List[StringHash]:
    """从事件BNK中提取事件与音频ID的映射

    :param bank: WwiserBank对象
    :param bin_events: BIN文件中的事件列表
    :return: 事件名称到音频ID的映射列表
    """
    mapper = EventMapper(bank)
    return mapper.collect_audio_ids(bin_events)


class FileProcessor:
    """文件处理器

    负责音频文件的提取、解析和合并
    """

    @staticmethod
    def combine_files(audio_files_list: List[List[WemFile]]) -> List[WemFile]:
        """合并多个音频文件列表，确保ID不重复

        :param audio_files_list: 多个音频文件列表
        :return: 合并后的音频文件列表
        """
        if not audio_files_list:
            return []

        # 使用ID作为键进行去重
        result_dict = {}

        for files in audio_files_list:
            for file in files:
                # 如果ID不存在或现有的文件没有数据但新文件有数据，则更新
                if file.id not in result_dict or (
                    not result_dict[file.id].data and file.data
                ):
                    result_dict[file.id] = file

        # 转换回列表
        return list(result_dict.values())

    @staticmethod
    def load_from_paths(
        bank_paths: List[str],
        raw_files: List[bytes],
        cache_dir: StrPath,
        get_data: bool = False,
    ) -> List[WemFile]:
        """从多个bank_path中提取音频文件

        :param bank_paths: 文件路径列表
        :param raw_files: 二进制数据列表
        :param cache_dir: 缓存目录，用于保存临时文件
        :param get_data: 是否获取音频数据
        :return: 合并后的音频文件列表
        """
        audio_files_list = []

        for idx, path in enumerate(bank_paths):
            # 只处理音频相关文件
            if path.endswith("_audio.bnk") or path.endswith("_audio.wpk"):
                file_data = raw_files[idx]
                if not file_data:
                    logger.warning(f"音频文件数据为空: {path}")
                    continue

                # 保存临时文件
                temp_path = Path(cache_dir) / path
                temp_path.parent.mkdir(parents=True, exist_ok=True)

                with open(temp_path, "wb") as f:
                    f.write(file_data)

                logger.debug(f"临时音频文件已保存: {temp_path}")

                # 解析音频文件
                try:
                    audio_files = AudioFiles.load_files(temp_path, get_data)
                    if audio_files:
                        audio_files_list.append(audio_files)
                        logger.debug(f"从 {path} 提取了 {len(audio_files)} 个音频文件")
                    else:
                        logger.warning(f"未能从 {path} 提取音频文件")
                except Exception as e:
                    logger.error(f"解析音频文件失败: {path}, 错误: {str(e)}")

        # 合并多个音频文件列表
        combined_files = FileProcessor.combine_files(audio_files_list)
        logger.info(f"合并后共 {len(combined_files)} 个音频文件")

        return combined_files


class Extractor:
    """音频提取器

    负责根据音频哈希表提取和转换音频文件
    """

    def __init__(self, vgmstream_cli: Optional[StrPath] = None):
        """初始化音频提取器

        :param vgmstream_cli: vgmstream工具路径，用于音频转换
        """
        self.vgmstream_cli = vgmstream_cli

    def save_audio(
        self,
        audio_hashtable: Dict[str, List[int]],
        audio_file: Union[StrPath, bytes],
        output_dir: StrPath,
        output_format: str = "wem",
        keep_wem: bool = False,
    ) -> Dict[str, List[str]]:
        """保存音频文件到输出目录

        :param audio_hashtable: 通过AudioFiles.map_events_to_audio()获取的音频哈希表
        :param audio_file: 音频文件路径(bnk或wpk)或二进制数据
        :param output_dir: 输出目录路径
        :param output_format: 输出文件格式，默认"wem"(不转换)，可选"ogg"、"wav"等
        :param keep_wem: 转换后是否保留原始wem文件
        :return: 事件名称到输出文件路径的映射字典
        """
        # 1. 准备输出目录
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # 2. 收集所有需要提取的音频ID
        all_audio_ids = []
        for event_list in audio_hashtable.values():
            all_audio_ids.extend(event_list)

        # 去重
        unique_audio_ids = list(set(all_audio_ids))
        logger.info(f"需要提取 {len(unique_audio_ids)} 个独特音频文件")

        # 3. 提取音频文件
        try:
            audio_files = AudioFiles.load_files(audio_file, True, unique_audio_ids)
            if not audio_files:
                logger.warning(f"未从 {audio_file} 找到任何匹配的音频文件")
                return {}

            logger.info(f"成功从 {audio_file} 提取 {len(audio_files)} 个音频文件")
        except Exception as e:
            logger.error(f"提取音频文件失败: {str(e)}")
            return {}

        # 4. 创建ID到文件对象的映射
        id_to_file = {file.id: file for file in audio_files}

        # 5. 按事件保存文件
        result = {}
        convert_needed = output_format.lower() != "wem"

        # 检查是否需要vgmstream
        if convert_needed and not self.vgmstream_cli:
            logger.warning(
                f"未提供vgmstream_cli路径，无法转换为{output_format}格式，将使用原始wem格式"
            )
            convert_needed = False
            output_format = "wem"

        # 或者检查vgmstream是否存在
        if (
            convert_needed
            and self.vgmstream_cli
            and not os.path.exists(self.vgmstream_cli)
        ):
            logger.warning(
                f"vgmstream_cli路径无效: {self.vgmstream_cli}，无法转换音频格式"
            )
            convert_needed = False
            output_format = "wem"

        for event_name, audio_ids in audio_hashtable.items():
            # 创建事件目录
            event_dir = output_path / event_name
            event_dir.mkdir(parents=True, exist_ok=True)

            # 保存该事件的所有文件
            event_files = []
            for audio_id in audio_ids:
                if audio_id not in id_to_file:
                    logger.warning(f"未找到ID为 {audio_id} 的音频文件")
                    continue

                file_obj = id_to_file[audio_id]

                # 确定文件名
                base_name = f"{event_name}_{audio_id}"
                output_file = event_dir / f"{base_name}.{output_format}"

                try:
                    # 保存文件
                    if convert_needed:
                        # 先保存wem文件
                        wem_path = event_dir / f"{base_name}.wem"
                        file_obj.save_file(wem_path, True)

                        # 使用vgmstream转换
                        os.system(
                            f'"{self.vgmstream_cli}" -o "{output_file}" "{wem_path}"'
                        )

                        # 检查转换结果
                        if not output_file.exists():
                            logger.warning(f"转换失败: {wem_path} -> {output_file}")
                            output_file = wem_path  # 使用原始wem文件
                        elif not keep_wem:
                            # 删除原始wem文件
                            wem_path.unlink()
                    else:
                        # 直接保存wem文件
                        file_obj.save_file(output_file, True)

                    event_files.append(str(output_file))
                    logger.debug(f"已保存: {output_file}")

                except Exception as e:
                    logger.error(f"保存文件失败: {str(e)}, 文件ID: {audio_id}")

            # 添加到结果
            if event_files:
                result[event_name] = event_files

        logger.info(
            f"音频提取完成，共处理 {len(result)} 个事件，输出格式: {output_format}"
        )
        return result


class Context:
    """处理上下文

    提供处理环境和依赖
    """

    def __init__(
        self,
        bin_file_path: Optional[StrPath] = None,
        base_wad_path: Optional[StrPath] = None,
        region_wad_path: Optional[StrPath] = None,
        output_dir: Optional[StrPath] = None,
        cache_dir: Optional[StrPath] = None,
    ):
        """初始化上下文

        :param bin_file_path: BIN文件路径（可选）
        :param base_wad_path: 基础WAD文件路径，用于处理SFX等非语音资源
        :param region_wad_path: 区域编码WAD文件路径，用于处理VO语音资源
        :param output_dir: 输出目录
        :param cache_dir: 缓存目录
        """
        self.bin_file_path = bin_file_path
        self.base_wad_path = base_wad_path
        self.region_wad_path = region_wad_path
        self.output_dir = Path(output_dir) if output_dir else Path("output")
        self.cache_dir = Path(cache_dir) if cache_dir else Path("cache")

        # 确保目录存在
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # 初始化依赖
        self.wwiser = WwiserManager()
        if not self.wwiser.wwiser_path:
            logger.error("未找到wwiser工具，请确保正确安装")
            raise RuntimeError("未找到wwiser工具，请确保正确安装")

        # 加载WAD对象
        self.base_wad = WAD(base_wad_path) if base_wad_path else None
        self.region_wad = WAD(region_wad_path) if region_wad_path else None

        # 加载核心对象（如果提供了bin_file_path）
        if bin_file_path:
            self.bin_obj = BIN(bin_file_path)
        else:
            # 创建一个空的BIN对象结构
            self.bin_obj = None

        # 处理资源类型标志
        self.can_process_sfx = bool(self.base_wad)
        self.can_process_vo = bool(self.region_wad)


def determine_resource_type(category: str) -> str:
    """根据category名确定资源类型

    :param category: 资源类别名称
    :return: 资源类型("SFX", "VO", "MUS", "MISC"等)
    """
    if "_SFX" in category:
        return "SFX"
    elif "_VO" in category:
        return "VO"
    elif "_MUS" in category or "theme_music" in category.lower():
        return "MUS"
    elif "_MISC" in category:
        return "MISC"
    # 其他类型或默认类型
    return "SFX"  # 默认当作SFX处理


def process_multiple_bins(
    bin_sources: List[Union[StrPath, bytes, BIN]],
    base_wad_path: Optional[StrPath] = None,
    region_wad_path: Optional[StrPath] = None,
    output_dir: Optional[StrPath] = None,
    cache_dir: Optional[StrPath] = None,
) -> Dict[str, Dict[str, List[int]]]:
    """处理多个bin文件并收集映射关系

    :param bin_sources: bin文件路径、二进制数据或BIN对象列表
    :param base_wad_path: 基础WAD文件路径，用于处理SFX等非语音资源
    :param region_wad_path: 区域编码WAD文件路径，用于处理VO语音资源
    :param output_dir: 输出目录（可选）
    :param cache_dir: 缓存目录（可选）
    :return: 所有皮肤的音频映射表
    """
    # 1. 创建BIN聚合器
    aggregator = BinAggregator.from_bin_sources(bin_sources)

    if aggregator.is_empty():
        logger.error("BIN聚合器为空，无法处理")
        return {}

    # 2. 创建处理器
    processor = Processor(
        base_wad_path=base_wad_path,
        region_wad_path=region_wad_path,
        output_dir=output_dir,
        cache_dir=cache_dir,
    )

    # 3. 使用聚合器收集映射
    mappings = processor.collect_mappings_from_aggregator(aggregator)

    return mappings


class BankProcessor:
    """资源集合处理器

    处理资源集合单元中的音频事件
    """

    def __init__(self, context: Context):
        """初始化处理器

        :param context: 处理上下文
        """
        self.context = context

    def process_unit(self, bank_unit: Any, category: str) -> Dict[str, List[int]]:
        """处理单个资源集合单元

        :param bank_unit: 资源集合单元对象
        :param category: 类别名称
        :return: 音频哈希表，事件名称到音频ID列表的映射
        """
        # 跳过空事件
        if not bank_unit.events:
            logger.warning(f"跳过空事件类别: {category}")
            return {}

        # 检查资源集合路径
        if not bank_unit.bank_path:
            logger.warning(f"类别 {category} 没有资源集合路径")
            return {}

        # 确定资源类型和对应的WAD
        resource_type = determine_resource_type(category)

        # 选择正确的WAD来源
        wad = None
        if resource_type == "VO" and self.context.region_wad:
            wad = self.context.region_wad
            logger.info(f"使用区域WAD处理语音资源: {category}")
        elif resource_type != "VO" and self.context.base_wad:
            wad = self.context.base_wad
            logger.info(f"使用基础WAD处理非语音资源: {category}")
        else:
            logger.warning(f"未找到适合类别 {category} 的WAD文件，跳过处理")
            return {}

        logger.info(f"从WAD提取文件: {bank_unit.bank_path}")

        # 从WAD中提取文件
        try:
            raw_files = wad.extract(bank_unit.bank_path, "", True)
            if not any(raw_files):
                logger.warning(f"从WAD中提取失败: {bank_unit.bank_path}")
                return {}
            logger.info(f"成功提取 {len(raw_files)} 个文件")
        except Exception as e:
            logger.error(f"从WAD提取文件失败: {e}")
            return {}

        # 从bank_unit.bank_path确认事件文件和音频文件
        event_file_path = None
        audio_file_path = None

        for path in bank_unit.bank_path:
            if path.endswith("_events.bnk"):
                event_file_path = path
            elif path.endswith("_audio.bnk") or path.endswith(".wpk"):
                audio_file_path = path

        if not event_file_path:
            logger.warning(f"未找到事件文件，跳过: {category}")
            return {}

        # 保存事件文件
        event_index = bank_unit.bank_path.index(event_file_path)
        temp_event_path = self.context.cache_dir / event_file_path
        temp_event_path.parent.mkdir(parents=True, exist_ok=True)

        with open(temp_event_path, "wb") as f:
            f.write(raw_files[event_index])

        logger.debug(f"事件文件已保存: {temp_event_path}")

        # 处理事件文件，生成XML并解析
        try:
            xml_path = self.context.wwiser.process_single_file(temp_event_path)
            if not xml_path or not os.path.exists(xml_path):
                logger.error(f"生成XML文件失败: {temp_event_path}")
                return {}

            logger.debug(f"成功生成XML文件: {xml_path}")

            # 解析XML并提取事件-音频ID映射
            hirc = WwiserHIRC(xml_path)
            bank = hirc[os.path.basename(event_file_path)]

            if not bank:
                logger.warning(f"在XML中未找到事件文件数据: {event_file_path}")
                return {}

            # 提取事件音频映射
            event_audio_mapping = map_events_to_audio_ids(bank, bank_unit.events)

            if not event_audio_mapping:
                logger.warning(f"未找到事件音频映射: {category}")
                return {}

            logger.info(f"找到 {len(event_audio_mapping)} 个事件音频映射: {category}")

            # 如果有音频文件，处理音频文件
            if audio_file_path:
                audio_index = bank_unit.bank_path.index(audio_file_path)
                # 直接使用内存中的二进制数据
                audio_data = raw_files[audio_index]
                # 构建音频哈希表
                audio_hashtable = AudioFiles.map_events_to_audio(
                    event_audio_mapping, audio_data
                )

                if audio_hashtable:
                    logger.info(
                        f"成功构建音频哈希表: {category}, 事件数: {len(audio_hashtable)}"
                    )
                    return audio_hashtable

        except Exception as e:
            logger.error(f"处理事件文件失败: {e}")
            return {}

        return {}


class Processor:
    """音频处理器

    协调各组件处理音频提取流程
    """

    def __init__(
        self,
        bin_file_path: Optional[StrPath] = None,
        base_wad_path: Optional[StrPath] = None,
        region_wad_path: Optional[StrPath] = None,
        output_dir: Optional[StrPath] = None,
        cache_dir: Optional[StrPath] = None,
    ):
        """初始化处理器

        :param bin_file_path: BIN文件路径（可选）
        :param base_wad_path: 基础WAD文件路径，用于处理SFX等非语音资源
        :param region_wad_path: 区域编码WAD文件路径，用于处理VO语音资源
        :param output_dir: 输出目录
        :param cache_dir: 缓存目录
        """
        self.context = Context(
            bin_file_path=bin_file_path,
            base_wad_path=base_wad_path,
            region_wad_path=region_wad_path,
            output_dir=output_dir,
            cache_dir=cache_dir,
        )
        self.bank_processor = BankProcessor(self.context)
        self.extractor = Extractor()

    def collect_mappings_from_aggregator(
        self, aggregator: BinAggregator
    ) -> Dict[str, Dict[str, List[int]]]:
        """从BIN聚合器收集映射关系

        :param aggregator: BIN聚合器
        :return: 按类别组织的音频哈希表
        """
        # 初始化结果容器
        result = {}

        # 筛选只处理可处理的资源类型
        sfx_only = self.context.can_process_sfx and not self.context.can_process_vo
        vo_only = self.context.can_process_vo and not self.context.can_process_sfx

        # 处理所有bank_units
        total_units = len(aggregator.bank_units_by_category) + len(
            aggregator.theme_music
        )
        processed_count = 0

        for unit in aggregator.iterate_units(sfx_filter=sfx_only, vo_filter=vo_only):
            processed_count += 1
            category = unit.category
            logger.info(f"处理进度: {processed_count}/{total_units} - 类别: {category}")

            # 处理资源集合单元
            audio_hashtable = self.bank_processor.process_unit(unit, category)

            if audio_hashtable:
                result[category] = audio_hashtable

        return result

    def collect_mappings(self) -> Dict[str, Dict[str, List[int]]]:
        """收集所有映射关系

        :return: 按类别组织的音频哈希表
        """
        # 确保bin_obj存在
        if not self.context.bin_obj:
            logger.error("无法收集映射关系：未提供BIN对象")
            return {}

        # 初始化结果容器
        result = {}

        # 按类别处理
        processed_count = 0
        total_bank_units = sum(
            len(group.bank_units) for group in self.context.bin_obj.data
        )

        for audio_group in self.context.bin_obj.data:
            for bank_unit in audio_group.bank_units:
                processed_count += 1
                logger.info(
                    f"处理进度: {processed_count}/{total_bank_units} - 类别: {bank_unit.category}"
                )

                # 检查资源类型
                resource_type = determine_resource_type(bank_unit.category)

                # 根据资源类型判断是否跳过
                if resource_type == "VO" and not self.context.can_process_vo:
                    logger.info(f"跳过VO资源(未提供区域WAD): {bank_unit.category}")
                    continue

                if resource_type != "VO" and not self.context.can_process_sfx:
                    logger.info(f"跳过非VO资源(未提供基础WAD): {bank_unit.category}")
                    continue

                # 处理资源集合单元
                audio_hashtable = self.bank_processor.process_unit(
                    bank_unit, bank_unit.category
                )

                if audio_hashtable:
                    result[bank_unit.category] = audio_hashtable

        return result

    def extract_all(
        self,
        vgmstream_cli: Optional[StrPath] = None,
        output_format: str = "wem",
        keep_wem: bool = False,
    ) -> Dict[str, Dict[str, List[str]]]:
        """提取并处理所有音频文件

        :param vgmstream_cli: vgmstream工具路径，用于音频转换
        :param output_format: 输出格式，默认"wem"，可选"ogg"、"wav"等
        :param keep_wem: 转换后是否保留wem文件
        :return: 按类别和事件组织的输出文件路径字典
        """
        # 确保bin_obj存在
        if not self.context.bin_obj:
            logger.error("无法提取音频：未提供BIN对象")
            return {}

        # 1. 获取音频哈希表
        audio_mappings = self.collect_mappings()
        if not audio_mappings:
            logger.warning("未找到任何音频映射")
            return {}

        # 2. 按类别提取音频文件
        self.extractor.vgmstream_cli = vgmstream_cli
        result = {}

        for category, hashtable in audio_mappings.items():
            logger.info(f"处理类别: {category}")

            # 确定资源类型和对应的WAD
            resource_type = determine_resource_type(category)
            wad = (
                self.context.region_wad
                if resource_type == "VO"
                else self.context.base_wad
            )

            # 查找对应的音频文件
            audio_data = None
            for bank_unit in self.context.bin_obj.data:
                for bu in bank_unit.bank_units:
                    if bu.category == category:
                        for path in bu.bank_path:
                            if path.endswith("_audio.bnk") or path.endswith(".wpk"):
                                # 从WAD中提取音频文件
                                if wad:
                                    raw_files = wad.extract([path], "", True)
                                    if raw_files and raw_files[0]:
                                        # 直接使用内存中的二进制数据
                                        audio_data = raw_files[0]
                                        break

            if not audio_data:
                logger.warning(f"未找到类别 {category} 的音频文件")
                continue

            # 提取该类别的音频文件
            category_output_dir = self.context.output_dir / category
            extracted_files = self.extractor.save_audio(
                hashtable, audio_data, category_output_dir, output_format, keep_wem
            )

            if extracted_files:
                result[category] = extracted_files
                logger.info(
                    f"类别 {category} 提取完成，共 {len(extracted_files)} 个事件"
                )

        return result
