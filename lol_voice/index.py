# -*- coding: utf-8 -*-
# @Author  : Virace
# @Email   : Virace@aliyun.com
# @Site    : x-item.com
# @Software: PyCharm
# @Create  : 2021/2/27 18:28
# @Update  : 2021/3/12 14:5
# @Detail  : 

# References : http://wiki.xentax.com/index.php/Wwise_SoundBank_(*.bnk)#HIRC_section

import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Union
from lol_voice.base import WemFile
from lol_voice.formats.BIN import BIN, StringHash
from lol_voice.formats.BNK import BNK, HIRC
from lol_voice.formats.WPK import WPK

log = logging.getLogger(__name__)


def obj_find_one(obj, key, value):
    """
    查询对象数组中key属性等于value的对象
    :param obj: 对象数组
    :param key: 对象属性名
    :param value: 要查找的属性值
    :return:
    """
    for item in obj:
        if getattr(item, key) == value:
            return item


def _get_audio_hashtable(hirc: HIRC, action_hash: List[StringHash]) -> List[StringHash]:
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


def get_audio_files(audio_file) -> List[WemFile]:
    # 解析音频文件
    audio_ext = os.path.splitext(audio_file)[-1]
    if audio_ext == '.wpk':
        audio_files = WPK(audio_file).files
    else:
        audio_files = BNK(audio_file).get_data_files()
        if not audio_files:
            # 这说明bnk中没有音频数据, 直接返回
            return []
    return audio_files


def get_audio_hashtable(bin_file: Union[str, List[StringHash]], event_file):
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
        read_strings = bin_file
    # 解析事件文件
    event = BNK(event_file)

    hirc = event.objects[b'HIRC']

    # 获取音频ID于事件哈希表
    audio_hashtable = _get_audio_hashtable(hirc, read_strings)
    return audio_hashtable


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


def extract_audio(bin_file: Union[str, List[StringHash]], event_file, audio_file, out_dir=None, ext=None,
                  vgmstream_cli=None,
                  wem=True,
                  data=False):
    """
    通过皮肤信息文件以及事件、资源文件, 提取音频文件, 支持转码
    :param bin_file: 皮肤信息bin文件或直接提供事件哈希表
    :param event_file: 皮肤事件bnk文件
    :param audio_file: 音频文件wpk或bnk文件
    :param out_dir: 解包输出文件夹
    :param ext: 输出文件后缀名, 如果不为wem则自动转码, 见下
    :param vgmstream_cli: vgmstream_cli程序, 用来解码
    :param wem: 如果转码是否保留wem文件
    :param data: 数据模式, 不提取文件只返回对应表
    :return:
    """
    if ext and ext != 'wem' and not vgmstream_cli:
        raise TypeError('如需转码需要提供 vgmstream_cli 参数.')

    if not data and not out_dir:
        raise TypeError('缺少关键性参数 out_dir 输出目录')

    audio_hashtable = get_audio_hashtable(bin_file, event_file)

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
                    # executor.submit(file.static_save_file, file.data, os.path.join(_dir, name), wem,
                    #                 vgmstream_cli=vgmstream_cli)
                else:
                    # 创建链接
                    try:
                        os.symlink(temp[file.id], os.path.join(_dir, name))
                    except FileExistsError:
                        pass
                    # executor.submit(os.link, temp[file.id], os.path.join(_dir, name))
                # file.save_file(os.path.join(_dir, name), wem, vgmstream_cli=vgmstream_cli)

