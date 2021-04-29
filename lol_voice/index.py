# -*- coding: utf-8 -*-
# @Author  : Virace
# @Email   : Virace@aliyun.com
# @Site    : x-item.com
# @Software: PyCharm
# @Create  : 2021/2/27 18:28
# @Update  : 2021/4/30 2:21
# @Detail  : 

# References : http://wiki.xentax.com/index.php/Wwise_SoundBank_(*.bnk)#HIRC_section

import logging
import os
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional, Union

from lol_voice.base import WemFile
from lol_voice.formats.BIN import BIN, StringHash
from lol_voice.formats.BNK import BNK, HIRC
from lol_voice.formats.WPK import WPK
from lol_voice.tools.Binary import BinaryReader

log = logging.getLogger(__name__)


def get_audio_id_by_songs(event_str, event_id, songs):
    """
    根据ID在Sound列表(迭代器)生成资源ID列表
    :param event_str:
    :param event_id:
    :param songs:
    :return:
    """

    # return [StringHash(string=event_str, hash=sound.audio_id)
    #         for sound in songs.values() if event_id in [sound.object_id, sound.sound_object_id]]
    res = []
    for sound in songs.values():
        if event_id in [sound.object_id, sound.sound_object_id]:
            res.append(
                StringHash(
                    string=event_str,
                    hash=sound.audio_id
                )
            )
    return res


def get_audio_id_by_music_segments(event_str, event_id, music_segments, music_tracks):
    res = []
    for ms in music_segments.values():
        if ms.sound_object_id == event_id:
            for track in ms.music_track_ids:
                if music_track := music_tracks.get(track, None):
                    res.append(
                        StringHash(
                            string=event_str,
                            hash=music_track.file_id,
                            switch_id=ms.object_id
                        )
                    )
    return res


def get_audio_id_by_music_playlist_containers(event_str, event_id, music_playlist_containers, music_segments,
                                              music_tracks):
    res = []
    for mp in music_playlist_containers.values():
        if mp.sound_object_id == event_id:
            for mp_mt_id in mp.music_track_ids:

                if not (music_segment := music_segments.get(mp_mt_id, None)):
                    continue

                for ms_id in music_segment.music_track_ids:

                    if not (music_track := music_tracks.get(ms_id, None)):
                        continue

                    res.append(
                        StringHash(
                            string=event_str,
                            hash=music_track.file_id,
                            switch_id=music_segment.object_id
                        )
                    )
    return res


def get_audio_hash_by_rs_containers(event_str, event_id, rs_containers, sounds):
    res = []
    for rsc in rs_containers.values():
        if rsc.switch_container_id == event_id:
            for rsc_sid in rsc.sound_ids:
                for sid, sound in sounds.items():
                    if rsc_sid == sid or rsc_sid == sound.sound_object_id:
                        res.append(
                            StringHash(
                                string=event_str,
                                hash=sound.audio_id,
                                switch_id=rsc.object_id
                            )
                        )
    return res


def _get_event_hashtable(hirc: HIRC, action_hash: List[StringHash]) -> List[StringHash]:
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

        # 根据事件ID查找事件
        event = hirc.events.get(string.hash, None)
        if not event:
            continue

        # 循环事件动作
        for ea in event.event_actions:

            event_action = hirc.event_actions.get(ea, None)

            if event_action and event_action.action_type == 4:
                reference_id = event_action.reference_id

                res.extend(get_audio_id_by_songs(string.string, reference_id, hirc.sounds))
                # for sound in hirc.sounds.values():
                #     if reference_id in [sound.object_id, sound.sound_object_id]:
                #         res.append(
                #             StringHash(
                #                 string=string.string,
                #                 hash=sound.audio_id
                #             )
                #         )

                # ######################################################## #
                # ######################################################## #
                # ####################以下代码未测试###################### #
                # ######################################################## #
                # ######################################################## #
                res.extend(get_audio_id_by_music_segments(string.string, reference_id, hirc.music_segments,
                                                          hirc.music_tracks))
                # for ms in hirc.music_segments.values():
                #     if ms.sound_object_id == reference_id:
                #         for track in ms.music_track_ids:
                #             if music_track := hirc.music_tracks.get(track, None):
                #                 res.append(
                #                     StringHash(
                #                         string=string.string,
                #                         hash=music_track.file_id,
                #                         switch_id=ms.object_id
                #                     )
                #                 )
                res.extend(
                    get_audio_id_by_music_playlist_containers(string.string, reference_id,
                                                              hirc.music_playlist_containers,
                                                              hirc.music_segments,
                                                              hirc.music_tracks)
                )
                # for mp in hirc.music_playlist_containers.values():
                #     if mp.sound_object_id == reference_id:
                #         for mp_mt_id in mp.music_track_ids:
                #             # music_segment = obj_find_one(hirc.music_segments, 'object_id', mp_mt_id)
                #             music_segment = hirc.music_segments.get(mp_mt_id, None)
                #             if not music_segment:
                #                 continue
                #
                #             for ms_id in music_segment.music_track_ids:
                #                 # music_track = obj_find_one(hirc.music_tracks, 'object_id', ms_id)
                #                 music_track = hirc.music_tracks.get(ms_id, None)
                #                 if not music_track:
                #                     continue
                #
                #                 res.append(
                #                     StringHash(
                #                         string=string.string,
                #                         hash=music_track.file_id,
                #                         switch_id=music_segment.object_id
                #                     )
                #                 )

                # ######################################################## #
                # ######################################################## #
                # ####################以上代码未测试###################### #
                # ######################################################## #
                # ######################################################## #

                # switch_container = hirc.switch_containers.get(reference_id, None)
                # if not switch_container:
                #     continue
                res.extend(
                    get_audio_hash_by_rs_containers(string.string, reference_id, hirc.rs_containers, hirc.sounds)
                )

                # for rsc in hirc.rs_containers.values():
                #     if rsc.switch_container_id == reference_id:
                #         for rsc_sid in rsc.sound_ids:
                #             for sid, sound in hirc.sounds.items():
                #                 if rsc_sid == sid or rsc_sid == sound.sound_object_id:
                #                     res.append(
                #                         StringHash(
                #                             string=string.string,
                #                             hash=sound.audio_id,
                #                             switch_id=rsc.object_id
                #                         )
                #                     )

    return res


def get_audio_files(audio_file: Union[str, bytes], get_data=True, hash_table: Optional[List[int]] = None) \
        -> List[WemFile]:
    """
    提供音频文件, 返回文件列表
    :param audio_file: 音频文件(bnk、wpk)
    :param get_data: 是否获取音频文件数据
    :param hash_table: 哈希表
    :return:
    """

    if isinstance(audio_file, str):
        audio_ext = os.path.splitext(audio_file)[-1]
    elif isinstance(audio_file, bytes):
        br = BinaryReader(audio_file)
        head = br.customize('<4s')
        audio_ext = '.wpk' if head == b'r3d2' else '.bnk'
    else:
        return []

    if audio_ext == '.wpk':
        wpk = WPK(audio_file)

        if hash_table:
            for file in wpk.files:
                if file.id not in hash_table:
                    wpk.files.remove(file)

        audio_files, data_call = wpk.files, wpk.get_files_data
    else:
        bnk = BNK(audio_file)
        if data := bnk.get_data_files():

            if hash_table:
                for file in data.files:
                    if file.id not in hash_table:
                        data.files.remove(file)

            audio_files, data_call = data, lambda x: bnk.objects[b'DATA'].get_files(data)
        else:
            audio_files, data_call = [], lambda x: None

    if get_data:
        data_call()

    return audio_files


def get_event_hashtable(bin_file: Union[str, List[StringHash]], event_file):
    """
    根据皮肤bin文件以及音频事件, 提取事件哈希表
    :param bin_file:
    :param event_file:
    :return:
    """
    if isinstance(bin_file, str):
        b1 = BIN(bin_file)
        # 获取事件哈希表
        read_strings = b1.hash_tables.copy()
    else:
        read_strings = bin_file.copy()
    # 解析事件文件
    event = BNK(event_file)

    try:
        hirc = event.objects[b'HIRC']
    except KeyError:
        return

    # 获取音频ID于事件哈希表
    event_hash = _get_event_hashtable(hirc, read_strings)
    return event_hash


def get_audio_hashtable(event_hashtable, audio_file):
    """
    提供事件哈希表和音频文件, 返回事件对应音频文件ID哈希表
    :param event_hashtable: get_event_hashtable()
    :param audio_file:
    :return:
    """

    if not (audio_files := get_audio_files(audio_file, False)):
        return

    ret = defaultdict(list)
    for ht in event_hashtable:
        for file in audio_files:
            if ht.hash == file.id:
                ret[ht.string].append(file.id)
    return ret


def extract_not_classified(audio_file, out_dir, ext=None, wem=False, vgmstream_cli=None, worker=None):
    """
    无需分类直接提取文件
    :param audio_file: 音频文件, 可以是bnk和wpk文件
    :param out_dir: 输出文件夹
    :param ext: 转码所需后缀名
    :param wem: 转码后是否保留wem文件, 默认删除
    :param vgmstream_cli: 转码所需程序vgmstream
    :param worker: 线程数量
    :return:
    """
    if ext and ext != 'wem' and not vgmstream_cli:
        raise TypeError('如需转码需要提供 vgmstream_cli 参数.')

    audio_files = get_audio_files(audio_file)

    with ThreadPoolExecutor(max_workers=worker) as executor:
        future_to_path = {
            executor.submit(file.save_file, os.path.join(out_dir, file.filename or f'{file.id}.wem'), wem,
                            vgmstream_cli): file for file in audio_files}
        for future in as_completed(future_to_path):
            path = future_to_path[future]
            try:
                future.result()
            except Exception as exc:
                log.error(f'提取文件出错: {exc}, 出错文件: {path}')


def extract_audio(bin_file: Union[str, List[StringHash]], event_file, audio_file, out_dir, ext=None,
                  vgmstream_cli=None,
                  wem=True):
    """
    通过皮肤信息文件以及事件、资源文件, 提取音频文件, 支持转码
    :param bin_file: 皮肤信息bin文件或直接提供事件哈希表
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

    audio_hashtable = get_event_hashtable(bin_file, event_file)

    if not (audio_files := get_audio_files(audio_file)):
        return

    # 去重
    temp = {}
    for ht in audio_hashtable:
        for file in audio_files:
            if ht.hash == file.id:
                name = file.filename or f'{file.id}.wem'
                if ext:
                    name = f'{os.path.splitext(name)[0]}.{ext}'

                _dir = os.path.join(out_dir, ht.string)
                if not os.path.exists(_dir):
                    os.makedirs(_dir)

                if file.id not in temp:
                    temp.update({file.id: os.path.join(_dir, name)})
                    logging.debug(f'Event: {ht.string}, File: {name}')
                    file.save_file(os.path.join(_dir, name), wem, vgmstream_cli=vgmstream_cli)

                else:
                    # 创建链接
                    try:
                        os.symlink(temp[file.id], os.path.join(_dir, name))
                    except FileExistsError:
                        pass
