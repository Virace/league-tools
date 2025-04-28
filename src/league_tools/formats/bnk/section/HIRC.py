# -*- coding: utf-8 -*-
# @Author  : Virace
# @Email   : Virace@aliyun.com
# @Site    : x-item.com
# @Software: PyCharm
# @Create  : 2023/5/15 19:21
# @Update  : 2025/4/28 8:59
# @Detail  : HIRC区块解析

from typing import Dict, Optional, List
from enum import IntEnum

from loguru import logger
from src.league_tools.core.section import SectionNoId, SectionBase


class HIRCBase(SectionBase):
    """
    HIRC文件专用的带ID区段基类
    
    结合了Section和SectionNoIdBNK的功能
    """
    __slots__ = ['object_id', '_data']

    def _read_object(self):
        """读取对象ID"""
        self.object_id = self._data.customize('<L')
        if self.object_id is None:
            raise ValueError("无法读取对象ID，文件可能已损坏或格式不正确")


class HIRCType(IntEnum):
    """HIRC对象类型枚举"""
    # STATE = 1
    SOUND = 2
    ACTION = 3
    EVENT = 4
    RANDOM_CONTAINER = 5
    SWITCH_CONTAINER = 6
    # ACTOR_MIXER = 7
    # BUS = 8
    # LAYER_CONTAINER = 9
    MUSIC_SEGMENT_CONTAINER = 10
    MUSIC_TRACK = 11
    MUSIC_SWITCH_CONTAINER = 12
    MUSIC_RANDOM_CONTAINER = 13


class Sound(HIRCBase):
    """
    声音对象类
    id: 对象ID
    stream_type: 流类型 来自 AkBankSourceData->StreamType
    source_id: 音频源ID 来自 AkMediaInformation->SourceID
    """
    __slots__ = ['stream_type', 'source_id']

    def _read(self):
        # 跳过 ulPluginID
        self._data.skip(4)

        # 读取AkBankSourceData->StreamType
        self.stream_type = self._data.customize('<B')

        # 读取AkMediaInformation->SourceID
        self.source_id = self._data.customize('<L')

        # 跳过剩余部分
        self._data.skip(55 - 4 - 4 - 1 - 4)

    def __repr__(self):
        return f"Sound对象: ID {self.object_id}, StreamType {self.stream_type}, SourceID {self.source_id}"


class Action(HIRCBase):
    """
    动作对象类 (ACTION)

            <object name="CAkActionSetSwitch" index="292">
				<field offset="00004433" type="u8" name="eHircType" value="3" valuefmt="0x03 [Action]"/>
				<field offset="00004434" type="u32" name="dwSectionSize" value="21" valuefmt="0x15"/>
				<field offset="00004438" type="sid" name="ulID" value="461635413"/>
				<field offset="0000443c" type="u16" name="ulActionType" value="6401" valuefmt="0x1901 [SetSwitch]"/>
				<object name="ActionInitialValues">
					<field offset="0000443e" type="tid" name="idExt" value="671930799"/>
					<field offset="00004442" type="u8" name="idExt_4" value="0" valuefmt="0x00">
						<field type="bit0" name="bIsBus" value="0"/>
					</field>
					<object name="AkPropBundle&lt;AkPropValue,unsigned char&gt;">
						<field offset="00004443" type="u8" name="cProps" value="0"/>
						<list name="pProps" count="0"/>
					</object>
					<object name="AkPropBundle&lt;RANGED_MODIFIERS&lt;AkPropValue&gt;&gt;">
						<field offset="00004444" type="u8" name="cProps" value="0"/>
						<list name="pProps" count="0"/>
					</object>
					<object name="SwitchActionParams">
						<field offset="00004445" type="tid" name="ulSwitchGroupID" value="3147968973"/>
						<field offset="00004449" type="tid" name="ulSwitchStateID" value="671930799"/>
					</object>
				</object>
			</object>


			<object name="CAkActionSetState" index="279">
				<field offset="00004465" type="u8" name="eHircType" value="3" valuefmt="0x03 [Action]"/>
				<field offset="00004466" type="u32" name="dwSectionSize" value="21" valuefmt="0x15"/>
				<field offset="0000446a" type="sid" name="ulID" value="229034033"/>
				<field offset="0000446e" type="u16" name="ulActionType" value="4612" valuefmt="0x1204 [SetState]"/>
				<object name="ActionInitialValues">
					<field offset="00004470" type="tid" name="idExt" value="476419625"/>
					<field offset="00004474" type="u8" name="idExt_4" value="0" valuefmt="0x00">
						<field type="bit0" name="bIsBus" value="0"/>
					</field>
					<object name="AkPropBundle&lt;AkPropValue,unsigned char&gt;">
						<field offset="00004475" type="u8" name="cProps" value="0"/>
						<list name="pProps" count="0"/>
					</object>
					<object name="AkPropBundle&lt;RANGED_MODIFIERS&lt;AkPropValue&gt;&gt;">
						<field offset="00004476" type="u8" name="cProps" value="0"/>
						<list name="pProps" count="0"/>
					</object>
					<object name="StateActionParams">
						<field offset="00004477" type="tid" name="ulStateGroupID" value="1016604436"/>
						<field offset="0000447b" type="tid" name="ulTargetStateID" value="476419625"/>
					</object>
				</object>
			</object>

            
    """
    __slots__ = ['object_id', '_data', 'action_type', 'id_ext', 'switch_group_id', 'switch_state_id', 'state_group_id', 'target_state_id']

    def _read(self):
        # logger.debug(f"Action对象: ID {self.object_id}")
        # 读取 ulActionType
        self.action_type = self._data.customize('<H')

        if self.action_type == 0x1901:
            # 0x1901 [SetSwitch]
            # 跳过数据 tid  + u8 + u8 + u8

            self._data.skip(4 + 1 + 1 + 1)

            # SwitchActionParams -> ulSwitchGroupID 和 ulSwitchStateID
            self.switch_group_id = self._data.customize('<L')
            self.switch_state_id = self._data.customize('<L')
        elif self.action_type == 0x1204:
            # 0x1204 [SetState]
            # 跳过数据 tid  + u8 + u8 + u8

            self._data.skip(4 + 1 + 1 + 1)
            # StateActionParams -> ulStateGroupID 和 ulTargetStateID
            self.state_group_id = self._data.customize('<L')
            self.target_state_id = self._data.customize('<L')

        else:
            # 读取 ActionInitialValues->idExt
            self.id_ext = self._data.customize('<L')



class Event(HIRCBase):
    """
    事件对象类 (EVENT)

    <object name="CAkEvent" index="297">
        <field offset="0000449f" type="u8" name="eHircType" value="4" valuefmt="0x04 [Event]"/>
        <field offset="000044a0" type="u32" name="dwSectionSize" value="9" valuefmt="0x09"/>
        <field offset="000044a4" type="sid" name="ulID" value="4212272965"/>
        <object name="EventInitialValues">
            <field offset="000044a8" type="var" name="ulActionListSize" value="1"/>
            <list name="actions" count="1">
                <object name="Action" index="0">
                    <field offset="000044a9" type="tid" name="ulActionID" value="440726586"/>
                </object>
            </list>
        </object>
    </object>
    """
    __slots__ = ['object_id', '_data', 'event_ids']

    def _read(self):
        # logger.debug(f"Event对象: ID {self.object_id}")

        self.event_ids = []
        # 读取ulActionListSize, 事件数组大小
        _size = self._data.customize('<B')

        # 读取ulActionListSize个Action对象
        for _ in range(_size):
            action_id = self._data.customize('<L')
            self.event_ids.append(action_id)


class RanSeqCntr(HIRCBase):
    """
    随机序列容器类 (RANDOM_CONTAINER)
    """
    __slots__ = ['object_id', '_data', 'direct_parent_id', 'child_ids']


    def _read(self):

        self.child_ids = []

        # NodeBaseParams
        
        #    跳过 NodeInitialFxParams
        self._data.skip(2)
        # bIsOverrideParentMetadata 、 uNumFx、 bOverrideAttachmentParams、 OverrideBusId
        self._data.skip(7)
        # 读取DirectParentID
        self.direct_parent_id = self._data.customize('<L')
        logger.debug(f"随机序列容器对象: ID {self.object_id}, DirectParentID {self.direct_parent_id}")

        # 跳过 byBitVector
        self._data.skip(1)
        
        #         				<object name="NodeInitialParams">
        # 							<object name="AkPropBundle&lt;AkPropValue,unsigned char&gt;">
        # 								<field offset="00000e53" type="u8" name="cProps" value="1"/>
        # 								<list name="pProps" count="1">
        # 									<object name="AkPropBundle" index="0">
        # 										<field offset="00000e54" type="u8" name="pID" value="6" valuefmt="0x06 [MakeUpGain]"/>
        # 										<field offset="00000e55" type="uni" name="pValue" value="-5.0"/>
        # 									</object>
        # 								</list>
        # 							</object>
        # 							<object name="AkPropBundle&lt;RANGED_MODIFIERS&lt;AkPropValue&gt;&gt;">
        # 								<field offset="00000e59" type="u8" name="cProps" value="0"/>
        # 								<list name="pProps" count="0"/>
        # 							</object>
        # 						</object>

        # 跳过 NodeInitialParams
        cProps = self._data.customize('<B')
        self._data.skip((1 + 4) * cProps)
        cProps = self._data.customize('<B')
        self._data.skip(9 * cProps)

        # 跳过 PositioningParams
        uBitsPositioning = self._data.customize('<B')
        has_positioning = bool(uBitsPositioning & 1)
        has_3d = False
        has_automation = False

        # 临时
        bnk_version = 130

        if has_positioning:
            if bnk_version <= 0x59:
                has_2d = bool(self._data.customize('<B'))  # 读取uint8作为布尔值
                has_3d = bool(self._data.customize('<B'))  # 读取uint8作为布尔值
                if has_2d:
                    self._data.customize('<B')  # 读取并丢弃一个字节
            else:
                has_3d = bool(uBitsPositioning & 0x2)

        if has_positioning and has_3d:
            if bnk_version <= 0x59:
                has_automation = (self._data.customize('<B') & 3) != 1  # 读取uint8
                self._data.seek(8, 1)  # 相对当前位置向前跳过8字节
            else:
                has_automation = bool((uBitsPositioning >> 5) & 3)
                self._data.customize('<B')  # 读取并丢弃一个字节

        if has_automation:
            self._data.seek((9 if bnk_version <= 0x59 else 5), 1)  # 相对当前位置向前跳过字节
            num_vertices = self._data.customize('<I')  # 读取uint32
            self._data.seek(16 * num_vertices, 1)  # 跳过顶点数据

            num_playlist_items = self._data.customize('<I')  # 读取uint32
            print(f"num vertices: {num_vertices}, num_playlist items: {num_playlist_items}, "
                  f"position: {self._data.buffer.tell()}")

            self._data.seek((16 if bnk_version <= 0x59 else 20) * num_playlist_items, 1)  # 跳过播放列表项
        elif bnk_version <= 0x59:
            self._data.seek(1)


        # AuxParams
        byBitVector = self._data.customize('<B')
        has_aux = (byBitVector >> 3) & 1

        # 如果has_aux为真，跳过4个uint32（16字节）
        if has_aux:
            self._data.seek(4 * 4, 1)  # 相对当前位置向前跳过16个字节

        # 如果BNK版本大于0x87，额外跳过4字节
        if bnk_version > 0x87:
            self._data.seek(4, 1)  # 相对当前位置向前跳过4个字节

        # AdvSettingsParams
        self._data.seek(6)


        # StateChunk
        # 读取状态属性数量
        state_props = self._data.customize('<B')  # 读取uint8
        # 跳过状态属性数据（每个属性3字节）
        self._data.seek(3 * state_props, 1)  # 相对当前位置向前跳过字节

        # 读取状态组数量
        state_groups = self._data.customize('<B')  # 读取uint8
        # 遍历每个状态组
        for _ in range(state_groups):
            # 跳过状态组头部数据（5字节）
            self._data.seek(5, 1)  # 相对当前位置向前跳过字节
            # 读取该组中的状态数量
            states = self._data.customize('<B')  # 读取uint8
            # 跳过所有状态数据（每个状态8字节）
            self._data.seek(8 * states, 1)  # 相对当前位置向前跳过字节


        # InitialRTPC
        # 读取RTPC数量（2字节无符号整数）
        num_rtpc = self._data.customize('<H')  # 读取uint16

        # 遍历每个RTPC
        for _ in range(num_rtpc):
            # 根据BNK版本跳过不同长度的数据
            self._data.seek(13 if bnk_version <= 0x59 else 12, 1)  # 相对当前位置向前跳过字节

            # 读取点数量（2字节无符号整数）
            point_count = self._data.customize('<H')  # 读取uint16

            # 跳过所有点数据（每个点12字节）
            self._data.seek(12 * point_count, 1)  # 相对当前位置向前跳过字节

        self._data.seek(24 + 4)

        size = self._data.customize('<I')
        self.child_ids = self._data.customize(f'<{size if size > 0 else ""}I')

class SwitchCntr(HIRCBase):
    """
    切换容器类 (SWITCH_CONTAINER)
    """
    __slots__ = ['object_id', '_data']

    def _read(self):
        # logger.debug(f"切换容器对象: ID {self.object_id}")
        pass


class MusicSegmentCntr(HIRCBase):
    """
    音乐段容器类 (MUSIC_SEGMENT_CONTAINER)
    """
    __slots__ = ['object_id', '_data']

    def _read(self):
        # logger.debug(f"音乐段容器对象: ID {self.object_id}")
        pass


class MusicTrack(HIRCBase):
    """
    音乐轨道类 (MUSIC_TRACK)
    """
    __slots__ = ['object_id', '_data']

    def _read(self):
        # logger.debug(f"音乐轨道对象: ID {self.object_id}")
        pass


class MusicSwitchCntr(HIRCBase):
    """
    音乐切换容器类 (MUSIC_SWITCH_CONTAINER)
    """
    __slots__ = ['object_id', '_data']

    def _read(self):
        # logger.debug(f"音乐切换容器对象: ID {self.object_id}")
        pass


class MusicRandomCntr(HIRCBase):
    """
    音乐随机容器类 (MUSIC_RANDOM_CONTAINER)
    """
    __slots__ = ['object_id', '_data']

    def _read(self):
        # logger.debug(f"音乐随机容器对象: ID {self.object_id}")
        pass


class HIRC(SectionNoId):
    """
    HIRC区块解析类
    
    该类负责解析BNK文件中的HIRC区块，目前仅处理Sound对象，其余类型全部跳过
    """
    __slots__ = ['objects']
    
    def _create_object(self, object_type: int, section_data) -> Optional[HIRCBase]:
        """
        根据对象类型创建相应的HIRC对象
        
        :param object_type: 对象类型ID
        :param section_data: 对象数据
        :return: 创建的HIRC对象，如果类型不支持则返回None
        """
        type_class_map = {
            HIRCType.SOUND: Sound,
            HIRCType.ACTION: Action,
            HIRCType.EVENT: Event,
            HIRCType.RANDOM_CONTAINER: RanSeqCntr,
            HIRCType.SWITCH_CONTAINER: SwitchCntr,
            HIRCType.MUSIC_SEGMENT_CONTAINER: MusicSegmentCntr,
            HIRCType.MUSIC_TRACK: MusicTrack,
            HIRCType.MUSIC_SWITCH_CONTAINER: MusicSwitchCntr,
            HIRCType.MUSIC_RANDOM_CONTAINER: MusicRandomCntr
        }
        
        if object_type in type_class_map:
            return type_class_map[object_type](section_data)
        return None

    def _read(self):
        """解析HIRC区块"""
        # 读取对象数量
        self.objects = []
        self.num_objects = self._data.customize('<L')
        # logger.debug(f"HIRC区块: 对象数量 {self.num_objects}")

        for _ in range(self.num_objects):
            # 读取对象类型
            object_type = self._data.customize('<B')
            section_size = self._data.customize('<L')

            # 计算下一个对象的偏移量
            next_offset = self._data.buffer.tell() + section_size

            # 如果HIRCType里面没有则直接跳过
            try:
                HIRCType(object_type)
            except ValueError:
                self._data.skip(section_size)
                continue

            # 读取对象数据
            section_data = self._data.binary(section_size)
            
            # 创建对象
            obj = self._create_object(object_type, section_data)
            if obj:
                self.objects.append(obj)

            # 如果当前指针偏移量不等于正确偏移量则跳转到正确位置
            if self._data.buffer.tell() != next_offset:
                self._data.seek(next_offset)

    

    def __repr__(self):
        return f"HIRC区块: 对象数量 {self.num_objects}, 已解析对象数量 {len(self.objects)}"
