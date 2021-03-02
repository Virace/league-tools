# -*- coding: utf-8 -*-
# @Time    : 2021/2/27 18:28
# @Author  : Virace
# @Email   : Virace@aliyun.com
# @Site    : x-item.com
# @Software: PyCharm
# @Detail  :
# References : http://wiki.xentax.com/index.php/Wwise_SoundBank_(*.bnk)#HIRC_section

import os
import logging
from typing import List
from BNK import BNK, HIRC
from BIN import BIN, StringHash
from WPK import WPK

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)
logging.getLogger('Tools.Binary.reader').setLevel(logging.INFO)


def obj_find_one(obj, key, value):
    for item in obj:
        if getattr(item, key) == value:
            return item


def get_audio_hashtable(hirc: HIRC, action_hash: List[StringHash]) -> List[StringHash]:
    """
    根据bnk文件中hirc块以及bin文件中提取的事件哈希表, 返回事件于音频ID对应哈希表
    这部分代码, 逻辑未理清.
    以及 music_segments 和 music_playlist_containers 这两部分未能测试
    仅对源代码进行"复刻"
    https://github.com/Morilli/bnk-extract/blob/5b1fd19e41b36addba351491c477765ad8a2ae09/sound.c#L429
    当前可, 正常分析皮肤语音文件
    :param hirc:
    :param action_hash:
    :return:
    """

    res = []
    for string in action_hash:
        # 根据已知事件循环
        _hash = string.hash

        # 根据事件ID查找事件
        event = obj_find_one(hirc.events, 'object_id', _hash)
        if not event:
            continue

        # 循环事件动作
        for ea in event.event_actions:

            event_action = obj_find_one(hirc.event_actions, 'object_id', ea)

            if event_action and event_action.action_type == 4:

                reference_id = event_action.reference_id

                for sound in hirc.sounds:
                    if sound.sound_object_id == reference_id or sound.object_id == reference_id:
                        res.append(
                            StringHash(
                                string=string.string,
                                hash=sound.audio_id
                            )
                        )

                # ######################################################## #
                # ######################################################## #
                # ####################以下代码未测试###################### #
                # ######################################################## #
                # ######################################################## #

                for ms in hirc.music_segments:
                    if ms.sound_object_id == reference_id:
                        for track in ms.music_track_ids:
                            music_track = obj_find_one(hirc.music_tracks, 'object_id', track)
                            if not music_track:
                                continue

                            res.append(
                                StringHash(
                                    string=string.string,
                                    hash=music_track.file_id,
                                    switch_id=ms.object_id
                                )
                            )

                for mp in hirc.music_playlist_containers:
                    if mp.sound_object_id == reference_id:
                        for mp_mt_id in mp.music_track_ids:
                            music_segment = obj_find_one(hirc.music_segments, 'object_id', mp_mt_id)
                            if not music_segment:
                                continue

                            for ms_id in music_segment.music_track_ids:
                                music_track = obj_find_one(hirc.music_tracks, 'object_id', ms_id)
                                if not music_track:
                                    continue

                                res.append(
                                    StringHash(
                                        string=string.string,
                                        hash=music_track.file_id,
                                        switch_id=music_segment.object_id
                                    )
                                )

                # ######################################################## #
                # ######################################################## #
                # ####################以上代码未测试###################### #
                # ######################################################## #
                # ######################################################## #

                switch_container = obj_find_one(hirc.switch_containers, 'object_id', reference_id)
                if not switch_container:
                    continue

                for rsc in hirc.rs_containers:
                    if rsc.switch_container_id == reference_id:
                        for rsc_sid in rsc.sound_ids:
                            for sound in hirc.sounds:
                                if rsc_sid == sound.object_id or rsc_sid == sound.sound_object_id:
                                    res.append(
                                        StringHash(
                                            string=string.string,
                                            hash=sound.audio_id,
                                            switch_id=rsc.object_id
                                        )
                                    )

    return res


def extract_audio(bin_file, event_file, audio_file, out_dir, ext=None, vgmstream_cli=None, wem=True):
    """

    :param bin_file: 皮肤信息bin文件
    :param event_file: 皮肤事件bnk文件
    :param audio_file: 音频文件wpk或bnk文件
    :param out_dir: 解包输出文件夹
    :param ext: 输出文件后缀名, 如果不为wem则自动转码, 见下
    :param vgmstream_cli: vgmstream_cli程序, 用来解码
    :param wem: 如果转码是否保留wem文件
    :return:
    """
    if ext and ext != 'wem' and not vgmstream_cli:
        raise TypeError('如需转码需要提供 vgmstream_cli 参数.')

    b1 = BIN(bin_file)
    read_strings = b1.hash_tables.copy()
    event = BNK(event_file)
    audio_ext = os.path.splitext(audio_file)[-1]
    if audio_ext == '.wpk':
        audio = WPK(audio_file)
    else:
        audio = BNK(audio_file).objects[b'DATA']
    hirc = event.objects[b'HIRC']

    data = get_audio_hashtable(hirc, read_strings)

    for ss in data:
        for file in audio.files:
            if ss.hash == file.id:
                name = file.filename if file.filename else f'{file.id}.wem'
                if ext:
                    name = f'{os.path.splitext(name)[0]}.{ext}'

                _dir = os.path.join(out_dir, ss.string)
                if not os.path.exists(_dir):
                    os.makedirs(_dir)
                file.save_file(os.path.join(_dir, name), wem, vgmstream_cli=vgmstream_cli)
