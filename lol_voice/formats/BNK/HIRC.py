# -*- coding: utf-8 -*-
# @Author  : Virace
# @Email   : Virace@aliyun.com
# @Site    : x-item.com
# @Software: PyCharm
# @Create  : 2021/2/27 19:32
# @Update  : 2021/3/9 0:58
# @Detail  : Wwise bnk文件, HIRC块

import logging
from typing import List
from ...base import Section, SectionNoId

log = logging.getLogger(__name__)


class Sound(Section):
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
        self.is_streamed, self.audio_id, self.source_id, self.sound_type = self._data.customize('<4xBLLL', False)
        self._data.seek(4)
        self.sound_object_id = self._data.customize('<L')

        assert self.is_streamed in [0, 1, 2], 'is_streamed(资源类型)范围错误'
        assert self.source_id, 'source_id(资源ID)不能为空'
        assert self.sound_type in [0, 1], 'sound_type(声音类型)范围错误'
        # 其余信息为Sound_structure, http://wiki.xentax.com/index.php/Wwise_SoundBank_(*.bnk)#Sound_structure
        # 因为用不到, 这部分不进行解析

    def __repr__(self):
        return f'{super().__repr__()}, ' \
               f'Location: {self.is_streamed}, ' \
               f'Audio_Id: {self.audio_id}, ' \
               f'Source_Id: {self.source_id}, ' \
               f'Sound_Type: {self.sound_type}'


class EventAction(Section):
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


class Event(Section):
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
        count = self._data.customize('B')
        if count:
            self.event_actions = list(self._data.customize(f'<{count}L', False))

    def __repr__(self):
        return f'{super().__repr__()}, ' \
               f'Event_Acionts: {self.event_actions}'


class RSContainer(Section):
    """
    https://github.com/Morilli/bnk-extract/blob/5b1fd19e41b36addba351491c477765ad8a2ae09/sound.c#L235
        struct random_container {
            uint32_t self_id;
            uint32_t switch_container_id;
            uint32_t sound_id_amount;
            uint32_t* sound_ids;
        };
    """
    __slots__ = [
        'switch_container_id',
        'sound_id_amount',
        'sound_ids',
    ]

    def _read(self):
        self.sound_id_amount = 1
        self._data.seek(1)

        unk = self._data.customize('<B')

        self._data.seek(5 + (1 if unk else 0) + (unk * 7))
        self.switch_container_id = self._data.customize('<L')

        self._data.seek(1)

        unk2 = self._data.customize('<B')

        to_seek = 25

        if unk2 != 0:
            self._data.seek(5 * unk2)

        unk3 = self._data.customize('<B')
        self._data.seek(9 * unk3)
        self._data.seek(9 + (1 if self._data.customize('<B') else 0))

        unk4 = self._data.customize('<B')
        if unk4 > 1:
            # https://github.com/Morilli/bnk-extract/blob/5b1fd19e41b36addba351491c477765ad8a2ae09/sound.c#L143
            return
        if unk4 and unk2:
            self._data.seek(13)
            unk5 = self._data.customize('<B')
            to_seek += 12 * unk5

        self._data.seek(to_seek)

        self.sound_id_amount = self._data.customize('<L')

        if self.sound_id_amount > 100:
            return

        self.sound_ids = self._data.customize(f'<{self.sound_id_amount}L', False)

    def __repr__(self):
        return f'{super().__repr__()}, ' \
               f'Switch_Container_Id: {self.switch_container_id}, ' \
               f'Sound_Id_Amount: {self.sound_id_amount}, ' \
               f'Sound_Ids: {self.sound_ids}'


class SwitchContainer(Section):
    pass


class MusicSegment(Section):
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
        'music_track_id_amount',
        'music_track_ids',
    ]

    def _read(self):
        self._data.seek(4)
        self.music_switch_id, self.sound_object_id = self._data.customize('<LL', False)
        self._data.seek(3)
        self._data.seek(11 + (1 if self._data.customize('<B') != 0 else 0))

        self.music_track_id_amount = self._data.customize('<L')

        self.music_track_ids = self._data.customize(f'<{self.music_track_id_amount}L', False)

    def __repr__(self):
        return f'{super().__repr__()}, ' \
               f'Music_Switch_Id: {self.music_switch_id}, ' \
               f'Sound_Object_Id: {self.sound_object_id}, ' \
               f'Music_Track_Id_Amount: {self.music_track_id_amount}, ' \
               f'Music_Track_Ids: {self.music_track_ids}'


class MusicTrack(Section):
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
        self.file_id, self.music_container_id = self._data.customize('<10xL64xL')
        # 未测试

    def __repr__(self):
        return f'{super().__repr__()}, ' \
               f'File Id: {self.file_id}, ' \
               f'Music Container Id: {self.music_container_id}'


class MusicPlaylistContainer(MusicSegment):
    pass


class ActorMixer(Section):
    pass


class Attenuation(Section):
    pass


class HIRC(SectionNoId):
    """
    uint32: number of objects
    FOR EACH (object) {
        byte: single byte identifying type of object
        uint32: length of object section (= 4-byte id field and additional bytes)
        uint32: id of this object
        byte[]: additional bytes, depending on type of object and section length
    } END FOR
    """

    sounds: List[Sound] = list()
    event_actions: List[EventAction] = list()
    events: List[Event] = list()
    rs_containers: List[RSContainer] = list()
    switch_containers: List[SwitchContainer] = list()
    actor_mixer: List[ActorMixer] = list()
    music_segments: List[MusicSegment] = list()
    music_tracks: List[MusicTrack] = list()
    music_playlist_containers: List[MusicPlaylistContainer] = list()
    attenuations: List[Attenuation] = list()

    def __init__(self, data):
        self._parse = {
            2: (Sound, self._set_sounds),
            3: (EventAction, self._set_event_actions),
            4: (Event, self._set_events),
            5: (RSContainer, self._set_rs_containers),
            6: (SwitchContainer, self._set_switch_containers),
            7: (ActorMixer, self._set_actor_mixer),
            10: (MusicSegment, self._set_music_segments),
            11: (MusicTrack, self._set_music_tracks),
            13: (MusicPlaylistContainer, self._set_music_playlist_containers),
            14: (Attenuation, self._set_attenuations)
        }
        super(HIRC, self).__init__(data)

    def _read(self):
        self.number_of_objects = 0
        number = self._data.customize('L')

        for i in range(number):
            section_type, section_length = self._data.customize('<BL', False)

            # print(f'Type: {t}, Length: {l}')
            data = self._data.binary(section_length)
            _call, _set = self._parse.get(section_type, (None, None))
            if _call:
                _set(_call(data))
                self.number_of_objects += 1
            else:
                log.debug(f'Type: {section_type}, Length: {section_length}')

    def _set_actor_mixer(self, data):
        self.actor_mixer.append(data)

    def _set_attenuations(self, data):
        self.attenuations.append(data)

    def _set_event_actions(self, data):
        self.event_actions.append(data)

    def _set_events(self, data):
        self.events.append(data)

    def _set_music_playlist_containers(self, data):
        self.music_playlist_containers.append(data)

    def _set_music_segments(self, data):
        self.music_segments.append(data)

    def _set_music_tracks(self, data):
        self.music_tracks.append(data)

    def _set_rs_containers(self, data):
        self.rs_containers.append(data)

    def _set_sounds(self, data):
        self.sounds.append(data)

    def _set_switch_containers(self, data):
        self.switch_containers.append(data)

    def __repr__(self):
        return f'Number_Of_Objects: {self.number_of_objects}'

