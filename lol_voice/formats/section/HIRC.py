# -*- coding: utf-8 -*-
# @Author  : Virace
# @Email   : Virace@aliyun.com
# @Site    : x-item.com
# @Software: PyCharm
# @Create  : 2021/2/27 19:32
# @Update  : 2022/8/26 0:21
# @Detail  : Wwise bnk文件, HIRC块

from typing import Dict

from loguru import logger

from lol_voice.base import SectionBNK, SectionNoIdBNK


# 关于bnk版本
# https://github.com/Morilli/bnk-extract-GUI/blob/a49f29e6da79b6a8df4123b120a4791f3ee785c2/bnk-extract/sound.c#L272
# 这个地方不懂，之前也没有遇到错误


class Sound(SectionBNK):
    """
    Sound SFX/Sound Voice

    Format:
    -- BEGINNING OF SECTION --
        02 -- identifier for Sound SFX section
        uint32: length of this section
        uint32: id of this Sound SFX object
            byte[4]: four unknown bytes
            uint32: whether the sound is included in the SoundBank or streamed:
                00: embedded in the SoundBank, not streamed
                01: is streamed
                02: is streamed, with Zero Latency (that is, the sound data is prefetched)
            uint32: id of the audio file
            uint32: id of the source:
                If this file is embedded, this will contain the SoundBank id as given in the STID section.
                If the file is being streamed, this number will be identical to the audio file id and can be used to
                find the .wem file to stream.
                IF (file is embedded in a SoundBank) {
                    uint32: offset to the position where the .wem sound file can be found in the SoundBank
                    uint32: length in bytes of the .wem sound file in the SoundBank
                } END IF

            byte: type of Sound object:
                00: Sound SFX
                01: Sound Voice
            byte[]: see section Sound structure
    -- END OF SECTION --
    """

    __slots__ = [
        'is_streamed',
        'audio_id',
        'source_id',
        'sound_type',
        'sound_object_id'
    ]

    def _read(self):
        flag = self.bnk_version == 0x58

        self._data.seek(4)

        self.is_streamed = self._data.customize('<B')

        if flag:
            self._data.seek(3)

        self.audio_id, self.source_id, self.sound_type = self._data.customize('<LLL', False)
        # self.is_streamed, self.audio_id, self.source_id, self.sound_type = self._data.customize('<4xBLLL', False)

        self._data.seek(4 - flag)

        # self._data.seek(4)
        self.sound_object_id = self._data.customize('<L')

        # assert self.is_streamed in [0, 1, 2], 'is_streamed(资源类型)范围错误'
        # assert self.source_id, 'source_id(资源ID)不能为空'
        # 安妮10号皮肤效果音, 有source_id为0的, 废弃语音？？

        # assert self.sound_type in [0, 1], 'sound_type(声音类型)范围错误'
        # 阿卡丽有个皮肤sound_type为65792  而且sound_object_id为65536

        # 其余信息为Sound_structure, http://wiki.xentax.com/index.php/Wwise_SoundBank_(*.bnk)#Sound_structure
        # 因为用不到, 这部分不进行解析

    def __repr__(self):
        return f'{super().__repr__()}, ' \
               f'Location: {self.is_streamed}, ' \
               f'Audio_Id: {self.audio_id}, ' \
               f'Source_Id: {self.source_id}, ' \
               f'Sound_Type: {self.sound_type}'


class EventAction(SectionBNK):
    """
    Event Action
    Format:

    03 -- identifier for Event Action section
    uint32: length of this section
    uint32: id of this Event Action object
        byte: The Scope of this Event Action:
            01: Game object: Switch or Trigger
            02: Global
            03: Game object: see referenced object id
            04: Game object: State
            05: All
            09: All Except see referenced object id
        byte: Action Type:
            01: Stop
            02: Pause
            03: Resume
            04: Play
            05: Trigger
            06: Mute
            07: UnMute
            08: Set Voice Pitch
            09: Reset Voice Pitch
            0A: Set Voice Volume
            0B: Reset Voice Volume
            0C: Set Bus Volume
            0D: Reset Bus Volume
            0E: Set Voice Low-pass Filter
            0F: Reset Voice Low-pass Filter
            10: Enable State
            11: Disable State
            12: Set State
            13: Set Game Parameter
            14: Reset Game Parameter
            19: Set Switch
            1A: Enable Bypass or Disable Bypass
            1B: Reset Bypass Effect
            1C: Break
            1E: Seek
        uint32: id of the game object that is referenced by this Event Action, or zero if there is no game object
        byte: always 00
        byte: number of additional parameters
        FOR EACH (parameter) {
            byte: parameter type:
            0E: Delay, given as uint32 in milliseconds
            0F: Play: Fade in time, given as uint32 in milliseconds
            10: Probability, given as float
        } END FOR
        FOR EACH (parameter) {
            byte[]: parameter value, format depending on parameter type (see above)
        } END FOR
        byte: always 00
        IF (Action Type == "Set State", 0x12) {
            uint32: State Group id
            uint32: State id
        ELSE IF (Action Type == "Set Switch", 0x19) {
            uint32: Switch Group id
            uint32: Switch id
        } END IF
    -- END OF SECTION --

    More information will follow.
    """

    __slots__ = [
        # 该事件动作的范围
        'action_scope',
        # 事件类型
        'action_type',
        # 该事件引用的游戏资源ID
        'reference_id',
    ]

    def _read(self):
        self.action_scope, self.action_type = \
            self._data.customize('<BB', False)

        if self.action_type == 25:
            self._data.seek(7)
        self.reference_id = self._data.customize('<L')
        # self.reference_id = self._data.bytes()

    def __repr__(self):
        return f'{super().__repr__()}, ' \
               f'Action_Scope: {self.action_scope}, Action_Type:{self.action_type}, ' \
               f'Reference_Id: {self.reference_id}'


class Event(SectionBNK):
    """
    Event
    Format:

    -- BEGINNING OF SECTION --

    04 -- identifier for Event section
    uint32: length of this section
        uint32: id of this Event object
        uint32: the number of Event Actions this Event has
            FOR EACH (event action) {
                uint32: id of the Event Action
            } END FOR
    -- END OF SECTION --
    """
    __slots__ = [
        'event_actions'
    ]

    def _read(self):
        self.event_actions = []
        count = self._data.customize('<B')
        if self.bnk_version == 0x58:
            self._data.seek(3)
        if count:
            self.event_actions = list(self._data.customize(f'<{count}L', False))

    def __repr__(self):
        return f'{super().__repr__()}, ' \
               f'Event_Acionts: {self.event_actions}'


class RSContainer(SectionBNK):
    """
    https://github.com/Morilli/bnk-extract-GUI/blob/a49f29e6da79b6a8df4123b120a4791f3ee785c2/sound.c#L108
        struct random_container {
            uint32_t self_id;
            uint32_t switch_container_id;
            uint32_t sound_id_amount;
            uint32_t* sound_ids;
        };
    """
    __slots__ = [
        'switch_container_id',
        'sound_ids',
    ]

    def _read(self):
        flag = self.bnk_version == 0x58
        self._data.seek(1)

        unk = self._data.customize('<B')

        # self._data.seek(5 + (1 if unk else 0) + (unk * 7))
        self._data.seek(5 + (unk != 0) + (unk * 7) - flag)

        self.switch_container_id = self._data.customize('<L')

        if flag:
            while self._data.customize('<B') != '\x7a' or self._data.customize('<B') != '\x44':
                continue
            self._data.seek(18)
        else:

            self._data.seek(1)

            unk2 = self._data.customize('<B')

            if unk2 != 0:
                self._data.seek(5 * unk2)

            unk3 = self._data.customize('<B')
            self._data.seek(9 * unk3)
            self._data.seek(9 + (1 if self._data.customize('<B') else 0))

            unk4 = self._data.customize('<B')
            if unk4 > 1:
                # https://github.com/Morilli/bnk-extract/blob/5b1fd19e41b36addba351491c477765ad8a2ae09/sound.c#L143
                return
            to_seek = 25

            if unk4:
                self._data.seek(13)
                unk5 = self._data.customize('<B')
                to_seek += 12 * unk5

            # if unk4 and unk2:
            #     self._data.seek(13)
            #     unk5 = self._data.customize('<B')
            #     to_seek += 12 * unk5

            self._data.seek(to_seek)

        # else done

        count = self._data.customize('<L')

        self.sound_ids = self._data.customize(f'<{count}L', False)

    def __repr__(self):
        return f'{super().__repr__()}, ' \
               f'Switch_Container_Id: {self.switch_container_id}, ' \
               f'Sound_Id_Amount: {len(self.sound_ids)}' \
               f'Sound_Ids: {self.sound_ids}'


class SwitchContainer(SectionBNK):
    pass


class MusicSegment(SectionBNK):
    """
    A Music Segment is similar to a Music Track, it contains exactly one song. However, unlike the Music Tracks,
    a Music Segment can contain multiple audio files, for example one file for each instrument. In this case,
    all files are played simultaneously, but it is possible to for example mute a certain instrument in the middle of
    the song, or to otherwise control the volume of individual files. 0A -- identifier for Music Segment section
    uint32: length of this section uint32: id of this Music Segment object byte[]: see section Sound structure
    uint32: number of child objects
        FOR EACH (child object) {
            uint32: id of child object
        } END FOR
    byte[]: unknown
    bytes More information will follow.
    """
    __slots__ = [
        'music_switch_id',
        'sound_object_id',
        'music_track_ids',
    ]

    def _read(self):
        self._data.seek(4)
        self.music_switch_id, self.sound_object_id = self._data.customize('<LL', False)
        self._data.seek(3)
        self._data.seek(11 + (1 if self._data.customize('<B') != 0 else 0))

        count = self._data.customize('<L')

        self.music_track_ids = self._data.customize(f'<{count}L', False)

    def __repr__(self):
        return f'{super().__repr__()}, ' \
               f'Music_Switch_Id: {self.music_switch_id}, ' \
               f'Sound_Object_Id: {self.sound_object_id}, ' \
               f'Music_Track_Id_Amount: {len(self.music_track_ids)}, ' \
               f'Music_Track_Ids: {self.music_track_ids}'


class MusicTrack(SectionBNK):
    """
    struct music_track {
        uint32_t self_id;
        uint32_t file_id;
        uint32_t music_container_id;
    };
    """
    __slots__ = [
        'file_id',
        'music_container_id',
    ]

    def _read(self):
        self._data.seek(10)
        self.file_id = self._data.customize('<L')
        self._data.seek(64)
        self.music_container_id = self._data.customize('<L')

    def __repr__(self):
        return f'{super().__repr__()}, ' \
               f'File Id: {self.file_id}, ' \
               f'Music Container Id: {self.music_container_id}'


class MusicSwitch(SectionBNK):
    """
    struct music_switch {
        uint32_t self_id;
        uint32_t some_id;
    };
    """
    __slots__ = [
        'some_id',
    ]

    def _read(self):
        self._data.seek(4)
        self.some_id = self._data.customize('<L')


class MusicPlaylistContainer(MusicSegment):
    pass


class ActorMixer(SectionBNK):
    pass


class Attenuation(SectionBNK):
    pass


class HIRC(SectionNoIdBNK):
    """
    uint32: number of objects
    FOR EACH (object) {
        byte: single byte identifying type of object
        uint32: length of object section (= 4-byte id field and additional bytes)
        uint32: id of this object
        byte[]: additional bytes, depending on type of object and section length
    } END FOR
    """

    sounds: Dict[int, Sound] = dict()
    event_actions: Dict[int, EventAction] = dict()
    events: Dict[int, Event] = dict()
    rs_containers: Dict[int, RSContainer] = dict()
    switch_containers: Dict[int, SwitchContainer] = dict()
    actor_mixer: Dict[int, ActorMixer] = dict()
    music_segments: Dict[int, MusicSegment] = dict()
    music_tracks: Dict[int, MusicTrack] = dict()
    # music_switches: Dict[int, MusicSwitch] = dict()
    music_playlist_containers: Dict[int, MusicPlaylistContainer] = dict()
    attenuations: Dict[int, Attenuation] = dict()

    def __init__(self, data, version):

        self._parse = {
            2: (Sound, self._set_sounds),
            3: (EventAction, self._set_event_actions),
            4: (Event, self._set_events),
            5: (RSContainer, self._set_rs_containers),
            6: (SwitchContainer, self._set_switch_containers),
            7: (ActorMixer, self._set_actor_mixer),
            10: (MusicSegment, self._set_music_segments),
            11: (MusicTrack, self._set_music_tracks),
            # 12: (MusicSwitch, self._set_music_switches),
            13: (MusicPlaylistContainer, self._set_music_playlist_containers),
            14: (Attenuation, self._set_attenuations)
        }
        super().__init__(data, version)
        # super(HIRC, self).__init__(data)

    def _read(self):
        self.number_of_objects = 0
        number = self._data.customize('<L')

        for _ in range(number):
            section_type, section_length = self._data.customize('<BL', False)
            _call, _set = self._parse.get(section_type, (None, None))
            if _call:
                data = self._data.binary(section_length)
                item = _call(data, self.bnk_version)
                _set({
                    item.object_id: item
                })
                self.number_of_objects += 1
            else:
                self._data.skip(section_length)
            logger.trace(f'Type: {section_type}, Length: {section_length}')

    def _set_actor_mixer(self, data):
        self.actor_mixer.update(data)

    def _set_attenuations(self, data):
        self.attenuations.update(data)

    def _set_event_actions(self, data):
        self.event_actions.update(data)

    def _set_events(self, data):
        self.events.update(data)

    def _set_music_playlist_containers(self, data):
        self.music_playlist_containers.update(data)

    def _set_music_segments(self, data):
        self.music_segments.update(data)

    def _set_music_tracks(self, data):
        self.music_tracks.update(data)

    # def _set_music_switches(self, data):
    #     self.music_switches.update(data)

    def _set_rs_containers(self, data):
        self.rs_containers.update(data)

    def _set_sounds(self, data):
        self.sounds.update(data)

    def _set_switch_containers(self, data):
        self.switch_containers.update(data)

    def __repr__(self):
        return f'Number_Of_Objects: {self.number_of_objects}'
