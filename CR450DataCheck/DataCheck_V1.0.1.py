import json
import struct
from datetime import datetime


def save_print_to_txt(file_path, *messages):
    """将打印信息保存到指定的文本文件中。
    参数:
    file_path (str): 要保存信息的文件路径。
    *messages: 可变参数，表示要保存的打印信息。
    """
    try:
        # 打开文件并写入内容
        with open(file_path, 'a') as f:  # 'a' 模式表示追加写入
            for message in messages:
                f.write(str(message) + '\n')  # 将每条信息写入文件并换行
    except Exception as e:
        print(f"保存信息到文件时出错: {e}")


def extract_frame_time(frame, time_offset):
    """将二进制帧数据转换为UNIX时间戳
    Args: frame: 二进制数据帧
    Returns: int: UNIX时间戳（秒级）
    Raises: ValueError: 当遇到无效日期或字段越界时
    """
    # 检查帧数据长度
    if len(frame) < 255:
        raise ValueError("帧数据长度不足255字节")

    # 提取时间字段（索引23-28）
    try:
        year_byte = frame[time_offset]
        month_byte = frame[time_offset + 1]
        day_byte = frame[time_offset + 2]
        hour_byte = frame[time_offset + 3]
        minute_byte = frame[time_offset + 4]
        second_byte = frame[time_offset + 5]

    except IndexError:
        raise ValueError("时间字段索引越界")

    # 转换为日期组件
    year = 2000 + year_byte  # C代码中的 tm_year = year_byte + 100（1900基准）
    month = month_byte  # 注意：C代码中会减1，Python直接使用原值
    day = day_byte
    hour = hour_byte
    minute = minute_byte
    second = second_byte
    dt = datetime(year, month, day, hour, minute, second)

    # 转换为UNIX时间戳
    return int(dt.timestamp())


import os
import glob
import zipfile


def merge_dat_files(directory, data_type):
    # 检查目录是否存在
    if not os.path.exists(directory):
        save_print_to_txt('./log.txt', '数据文件路径不存在')
        return None

    # 删除所有已存在的 *_mergedata.dat 文件
    for merged_file in glob.glob(os.path.join(directory, '*_mergedata.dat')):
        if os.path.exists(merged_file):
            os.remove(merged_file)
            print(f"已删除文件: {merged_file}")

    # 获取指定目录及其子目录下包含 data_type 的 .dat 和 .dat.zip 文件
    data_files = []
    for root, dirs, files in os.walk(directory):
        for file in files:
            if data_type in file and (file.endswith('.dat') or file.endswith('.dat.zip')):
                data_files.append(os.path.join(root, file))

    if not data_files:
        save_print_to_txt('./log.txt', f"{directory}文件夹下没有 .dat 或 .dat.zip 数据。")
        print(f"{directory}文件夹下没有 .dat 或 .dat.zip 数据。")
        return None

    # 创建一个字典来按车厢号分组文件
    car_files = {}

    for file in data_files:
        # 如果是 .dat.zip 文件，解压并获取解压后的 .dat 文件
        if file.endswith('.dat.zip'):
            with zipfile.ZipFile(file, 'r') as zip_ref:
                # 解压到当前目录
                zip_ref.extractall(os.path.dirname(file))
                # 获取解压后的 .dat 文件
                extracted_files = [os.path.join(os.path.dirname(file), f) for f in zip_ref.namelist() if
                                   f.endswith('.dat')]
                for extracted_file in extracted_files:
                    # 解析文件名，获取车厢号
                    parts = os.path.basename(extracted_file).split('_')
                    car_number = parts[1]
                    # 按车厢号分组文件
                    if car_number not in car_files:
                        car_files[car_number] = []
                    car_files[car_number].append(extracted_file)
        else:
            # 解析文件名，获取车厢号
            parts = os.path.basename(file).split('_')
            car_number = parts[1]
            # 按车厢号分组文件
            if car_number not in car_files:
                car_files[car_number] = []
            car_files[car_number].append(file)

    # 处理每个车厢号的文件
    for car_number, files in car_files.items():
        # 按时间排序文件
        files.sort(key=lambda x: x.split('_')[2])

        # 合并文件
        merged_data = b''
        for i, file in enumerate(files):
            with open(file, 'rb') as f:
                data = f.read()
                if i == 0:
                    # 保留第一个文件的前16个字节
                    merged_data += data
                else:
                    # 去掉其他文件的前16个字节
                    merged_data += data[16:]

        # 保存合并后的文件
        output_file = os.path.join(directory, f"{car_number}_mergedata.dat")
        with open(output_file, 'wb') as f:
            f.write(merged_data)

        print(f"已生成文件: {output_file}")

    # 返回生成的合并文件路径
    merged_files = [os.path.join(directory, f"{car_number}_mergedata.dat") for car_number in car_files.keys()]
    return merged_files


def read_binary_file(file_path, frame_offset, time_offset, start_time, end_time, frame_size):
    """
    从.dat二进制文件中读取指定时间段的数据帧
    :param file_path: 文件路径
    :param start_time: 起始时间字符串，格式为'YYYY-MM-DD HH:MM:SS'
    :param end_time: 结束时间字符串，格式为'YYYY-MM-DD HH:MM:SS'
    :param frame_size: 每帧的大小（字节数）
    :return: 包含时间戳和数据的列表
    """
    # 将时间字符串转换为datetime对象
    start_timestamp = int(datetime.strptime(start_time, '%Y-%m-%d %H:%M:%S').timestamp())
    end_timestamp = int(datetime.strptime(end_time, '%Y-%m-%d %H:%M:%S').timestamp())

    results = []
    error_log = []

    with open(file_path, 'rb') as f:
        # 跳过文件信息的前16个字节
        f.seek(frame_offset)

        frame_count = 0
        while True:
            # 记录当前帧起始位置
            frame_start = f.tell()

            try:
                frame_data = f.read(frame_size)
                if not frame_data:
                    break

                # 帧长度校验
                if len(frame_data) != frame_size:
                    raise ValueError(f"帧长度异常 ({len(frame_data)}/{frame_size} 字节)")

                # 提取时间戳（增加异常捕获）
                try:
                    timestamp = extract_frame_time(frame_data, time_offset)
                except Exception as e:
                    raise ValueError(f"时间解析失败: {str(e)}") from e

                # 时间有效性验证
                local_time = datetime.fromtimestamp(timestamp)
                if timestamp < 0:
                    raise ValueError(f"时间戳为负值: {timestamp}")
                if local_time.year < 2000 or local_time.year > 2100:
                    raise ValueError(f"时间超出合理范围: {local_time}")

                # 时间范围过滤
                if start_timestamp <= timestamp <= end_timestamp:
                    results.append(frame_data)

                frame_count += 1

            except Exception as e:
                # 计算错误位置（字节偏移量）
                error_offset = frame_start - 16  # 扣除文件头
                error_msg = f"第 {frame_count} 帧错误 @ 0x{error_offset:X} (原因: {str(e)})"
                error_log.append(error_msg)

                # 尝试恢复指针到下一帧起始位置
                f.seek(frame_start + frame_size)

                # 跳过损坏帧继续读取
                continue

    # 输出错误汇总
    if error_log:
        # save_print_to_txt('./log.txt', f"\n错误汇总（共 {len(error_log)} 处）:")
        print(f"\n错误汇总（共 {len(error_log)} 处）:")
        for log in error_log:
            # save_print_to_txt('./log.txt', f"  - {log}")
            print(f"  - {log}")

    return results


def save_variables_to_file(variables, timestr, file_name, file_path='./data/WNDS/'):
    """
    将变量保存到文件中，文件名为 {file_name}YmdHMS.txt，其中 YmdHMS 为当前时间。
    如果文件存在，则先删除文件内容，再保存变量。
    :param variables: 要保存的变量元组
    :param timestr: 时间字符串，格式为 %Y-%m-%d %H:%M:%S
    :param file_name: 文件名前缀
    :param file_path: 文件保存的目录路径，默认为 './data/WNDS/'
    """
    # 将时间字符串转换为 datetime 对象
    time_obj = datetime.strptime(timestr, '%Y-%m-%d %H:%M:%S')
    # 格式化时间为 YmdHMS 格式
    time_str = time_obj.strftime('%Y%m%d%H%M%S')

    # 生成文件名
    filename = f"{file_name}{time_str}.txt"
    full_file_path = os.path.join(file_path, filename)

    # 确保目录存在
    os.makedirs(file_path, exist_ok=True)

    # 打开文件，采用写入模式（如果文件存在，会覆盖内容）
    with open(full_file_path, 'w') as file:
        # 写入每个变量，每个变量占一行
        for var in variables:
            file.write(f"{var}\n")

        # 添加空行以便区分不同运行记录
        file.write("\n")
    save_print_to_txt('./log.txt', f"结果已保存在：{filename}")


def WNDS_data_judge(framelist, time_offset):
    """
    得到每一帧数据内容
    :param framelist: 数据帧列表
    :return:
    """
    # 定义 0-7 位的掩码变量
    BIT0_MASK = 0b00000001  # 第 0 位掩码
    BIT1_MASK = 0b00000010  # 第 1 位掩码
    BIT2_MASK = 0b00000100  # 第 2 位掩码
    BIT3_MASK = 0b00001000  # 第 3 位掩码
    BIT4_MASK = 0b00010000  # 第 4 位掩码
    BIT5_MASK = 0b00100000  # 第 5 位掩码
    BIT6_MASK = 0b01000000  # 第 6 位掩码
    BIT7_MASK = 0b10000000  # 第 7 位掩码

    speed_max = 0
    sharedata_comm = 0
    sensor_check = 0
    sensor_realtime = 0
    stable_HX_warn = 0
    stable_HX_alarm = 0
    stable_CX_warn = 0
    stable_CX_alarm = 0
    douche_warn = 0
    douche_alarm = 0
    shake_warn = 0
    shake_alarm = 0
    stable_1HX_max = 0
    stable_1HX_speed = 0
    stable_2HX_max = 0
    stable_2HX_speed = 0
    stable_1CX_max = 0
    stable_1CX_speed = 0
    stable_2CX_max = 0
    stable_2CX_speed = 0
    peak_0p2_3_1HX_max = 0
    peak_0p2_3_1HX_speed = 0
    peak_0p2_3_2HX_max = 0
    peak_0p2_3_2HX_speed = 0
    rms_5_13_1HX_max = 0  # 横向加速度5-13Hz均方根值
    rms_5_13_1HX_speed = 0
    rms_5_13_2HX_max = 0
    rms_5_13_2HX_speed = 0
    rms_5_13_1CX_max = 0
    rms_5_13_1CX_speed = 0
    rms_5_13_2CX_max = 0
    rms_5_13_2CX_speed = 0
    main_fre_amp_1CX_max = 0
    main_fre_1CX = 0
    main_fre_amp_1CX_speed = 0
    main_fre_amp_2CX_max = 0
    main_fre_2CX = 0
    main_fre_amp_2CX_speed = 0
    acc_max_1HX_max = 0
    acc_max_1HX_speed = 0
    acc_max_2HX_max = 0
    acc_max_2HX_speed = 0
    acc_valid_1HX_max = 0
    acc_valid_1HX_speed = 0
    acc_valid_2HX_max = 0
    acc_valid_2HX_speed = 0
    acc_max_1CX_max = 0
    acc_max_1CX_speed = 0
    acc_max_2CX_max = 0
    acc_max_2CX_speed = 0
    acc_valid_1CX_max = 0
    acc_valid_1CX_speed = 0
    acc_valid_2CX_max = 0
    acc_valid_2CX_speed = 0

    for frame in framelist:
        # 创建 datetime 对象
        datetime_obj = extract_frame_time(frame, time_offset)
        dt = datetime.fromtimestamp(datetime_obj)
        # 格式化时间为 %Y-%m-%d %H:%M:%S
        formatted_time = dt.strftime("%Y-%m-%d %H:%M:%S")

        speed = struct.unpack('>H', frame[78:80])[0] * 0.01  # 速度 1=0.01km/h
        if (speed > speed_max):
            speed_max = speed
        if (frame[87] & BIT4_MASK) or (frame[87] & BIT5_MASK):
            sharedata_comm = formatted_time
        if (frame[90] & BIT0_MASK) or (frame[90] & BIT1_MASK):
            sensor_check = formatted_time
        if (frame[90] & BIT2_MASK) or (frame[90] & BIT3_MASK):
            sensor_realtime = formatted_time
        if (frame[88] & BIT0_MASK):
            stable_HX_warn = formatted_time
        if (frame[88] & BIT4_MASK):
            stable_HX_alarm = formatted_time
        if (frame[88] & BIT1_MASK):
            stable_CX_warn = formatted_time
        if (frame[88] & BIT5_MASK):
            stable_CX_alarm = formatted_time
        if (frame[89] & BIT1_MASK):
            douche_warn = formatted_time
        if (frame[89] & BIT5_MASK):
            douche_alarm = formatted_time
        if (frame[89] & BIT0_MASK):
            shake_warn = formatted_time
        if (frame[89] & BIT4_MASK):
            shake_alarm = formatted_time

        stable_1HX = struct.unpack('>H', frame[105:107])[0] * 0.01
        if (stable_1HX > stable_1HX_max):
            stable_1HX_max = stable_1HX
            stable_1HX_speed = speed
        elif stable_1HX == stable_1HX_max:
            if speed > stable_1HX_speed:
                stable_1HX_speed = speed
        stable_2HX = struct.unpack('>H', frame[107:109])[0] * 0.01
        if (stable_2HX > stable_2HX_max):
            stable_2HX_max = stable_2HX
            stable_2HX_speed = speed
        elif stable_2HX == stable_2HX_max:
            if speed > stable_2HX_speed:
                stable_2HX_speed = speed
        stable_1CX = struct.unpack('>H', frame[109:111])[0] * 0.01
        if (stable_1CX > stable_1CX_max):
            stable_1CX_max = stable_1CX
            stable_1CX_speed = speed
        elif stable_1CX == stable_1CX_max:
            if speed > stable_1CX_speed:
                stable_1CX_speed = speed
        stable_2CX = struct.unpack('>H', frame[111:113])[0] * 0.01
        if (stable_2CX > stable_2CX_max):
            stable_2CX_max = stable_2CX
            stable_2CX_speed = speed
        elif stable_2CX == stable_2CX_max:
            if speed > stable_2CX_speed:
                stable_2CX_speed = speed
        peak_0p2_3_1HX = frame[93] * 0.001
        if (peak_0p2_3_1HX > peak_0p2_3_1HX_max):
            peak_0p2_3_1HX_max = peak_0p2_3_1HX
            peak_0p2_3_1HX_speed = speed
        elif peak_0p2_3_1HX == peak_0p2_3_1HX_max:
            if speed > peak_0p2_3_1HX_speed:
                peak_0p2_3_1HX_speed = speed
        peak_0p2_3_2HX = frame[94] * 0.001
        if (peak_0p2_3_2HX > peak_0p2_3_2HX_max):
            peak_0p2_3_2HX_max = peak_0p2_3_2HX
            peak_0p2_3_2HX_speed = speed
        elif peak_0p2_3_2HX == peak_0p2_3_2HX_max:
            if speed > peak_0p2_3_2HX_speed:
                peak_0p2_3_2HX_speed = speed
        rms_5_13_1HX = frame[95] * 0.001
        if (rms_5_13_1HX > rms_5_13_1HX_max):
            rms_5_13_1HX_max = rms_5_13_1HX
            rms_5_13_1HX_speed = speed
        elif rms_5_13_1HX == rms_5_13_1HX_max:
            if speed > rms_5_13_1HX_speed:
                rms_5_13_1HX_speed = speed
        rms_5_13_2HX = frame[96] * 0.001
        if (rms_5_13_2HX > rms_5_13_2HX_max):
            rms_5_13_2HX_max = rms_5_13_2HX
            rms_5_13_2HX_speed = speed
        elif rms_5_13_2HX == rms_5_13_2HX_max:
            if speed > rms_5_13_2HX_speed:
                rms_5_13_2HX_speed = speed
        rms_5_13_1CX = frame[97] * 0.001
        if (rms_5_13_1CX > rms_5_13_1CX_max):
            rms_5_13_1CX_max = rms_5_13_1CX
            rms_5_13_1CX_speed = speed
        elif rms_5_13_1CX == rms_5_13_1CX_max:
            if speed > rms_5_13_1CX_speed:
                rms_5_13_1CX_speed = speed
        rms_5_13_2CX = frame[98] * 0.001
        if (rms_5_13_2CX > rms_5_13_2CX_max):
            rms_5_13_2CX_max = rms_5_13_2CX
            rms_5_13_2CX_speed = speed
        elif rms_5_13_2CX == rms_5_13_2CX_max:
            if speed > rms_5_13_2CX_speed:
                rms_5_13_2CX_speed = speed
        main_fre_amp_1CX = frame[99] * 0.001
        main_fre = struct.unpack('>H', frame[101:103])[0] * 0.1
        if (main_fre_amp_1CX > main_fre_amp_1CX_max):
            main_fre_amp_1CX_max = main_fre_amp_1CX
            main_fre_1CX = main_fre
            main_fre_amp_1CX_speed = speed
        elif main_fre_amp_1CX == main_fre_amp_1CX_max:
            if main_fre > main_fre_1CX:
                main_fre_1CX = main_fre
                main_fre_amp_1CX_speed = speed
            elif main_fre == main_fre_1CX:
                if speed > main_fre_amp_1CX_speed:
                    main_fre_amp_1CX_speed = speed
        main_fre_amp_2CX = frame[100] * 0.001
        main_fre = struct.unpack('>H', frame[103:105])[0] * 0.1
        if (main_fre_amp_2CX > main_fre_amp_2CX_max):
            main_fre_amp_2CX_max = main_fre_amp_2CX
            main_fre_2CX = main_fre
            main_fre_amp_2CX_speed = speed
        elif main_fre_amp_2CX == main_fre_amp_2CX_max:
            if main_fre > main_fre_2CX:
                main_fre_2CX = main_fre
                main_fre_amp_2CX_speed = speed
            elif main_fre == main_fre_2CX:
                if speed > main_fre_amp_2CX_speed:
                    main_fre_amp_2CX_speed = speed
        acc_max_1HX = struct.unpack('>H', frame[117:119])[0] * 0.001
        if (acc_max_1HX > acc_max_1HX_max):
            acc_max_1HX_max = acc_max_1HX
            acc_max_1HX_speed = speed
        elif acc_max_1HX == acc_max_1HX_max:
            if speed > acc_max_1HX_speed:
                acc_max_1HX_speed = speed
        acc_max_2HX = struct.unpack('>H', frame[119:121])[0] * 0.001
        if (acc_max_2HX > acc_max_2HX_max):
            acc_max_2HX_max = acc_max_2HX
            acc_max_2HX_speed = speed
        elif acc_max_2HX == acc_max_2HX_max:
            if speed > acc_max_2HX_speed:
                acc_max_2HX_speed = speed
        acc_valid_1HX = struct.unpack('>H', frame[129:131])[0] * 0.001
        if (acc_valid_1HX > acc_valid_1HX_max):
            acc_valid_1HX_max = acc_valid_1HX
            acc_valid_1HX_speed = speed
        elif acc_valid_1HX == acc_valid_1HX_max:
            if speed > acc_valid_1HX_speed:
                acc_valid_1HX_speed = speed
        acc_valid_2HX = struct.unpack('>H', frame[131:133])[0] * 0.001
        if (acc_valid_2HX > acc_valid_2HX_max):
            acc_valid_2HX_max = acc_valid_2HX
            acc_valid_2HX_speed = speed
        elif acc_valid_2HX == acc_valid_2HX_max:
            if speed > acc_valid_2HX_speed:
                acc_valid_2HX_speed = speed
        acc_max_1CX = struct.unpack('>H', frame[121:123])[0] * 0.001
        if (acc_max_1CX > acc_max_1CX_max):
            acc_max_1CX_max = acc_max_1CX
            acc_max_1CX_speed = speed
        elif acc_max_1CX == acc_max_1CX_max:
            if speed > acc_max_1CX_speed:
                acc_max_1CX_speed = speed
        acc_max_2CX = struct.unpack('>H', frame[123:125])[0] * 0.001
        if (acc_max_2CX > acc_max_2CX_max):
            acc_max_2CX_max = acc_max_2CX
            acc_max_2CX_speed = speed
        elif acc_max_2CX == acc_max_2CX_max:
            if speed > acc_max_2CX_speed:
                acc_max_2CX_speed = speed
        acc_valid_1CX = struct.unpack('>H', frame[133:135])[0] * 0.001
        if (acc_valid_1CX > acc_valid_1CX_max):
            acc_valid_1CX_max = acc_valid_1CX
            acc_valid_1CX_speed = speed
        elif acc_valid_1CX == acc_valid_1CX_max:
            if speed > acc_valid_1CX_speed:
                acc_valid_1CX_speed = speed
        acc_valid_2CX = struct.unpack('>H', frame[135:137])[0] * 0.001
        if (acc_valid_2CX > acc_valid_2CX_max):
            acc_valid_2CX_max = acc_valid_2CX
            acc_valid_2CX_speed = speed
        elif acc_valid_2CX == acc_valid_2CX_max:
            if speed > acc_valid_2CX_speed:
                acc_valid_2CX_speed = speed

    variables = [speed_max,
                 sharedata_comm,
                 sensor_check,
                 sensor_realtime,
                 stable_HX_warn,
                 stable_HX_alarm,
                 stable_CX_warn,
                 stable_CX_alarm,
                 douche_warn,
                 douche_alarm,
                 shake_warn,
                 shake_alarm,
                 stable_1HX_max,
                 stable_1HX_speed,
                 stable_2HX_max,
                 stable_2HX_speed,
                 stable_1CX_max,
                 stable_1CX_speed,
                 stable_2CX_max,
                 stable_2CX_speed,
                 peak_0p2_3_1HX_max,
                 peak_0p2_3_1HX_speed,
                 peak_0p2_3_2HX_max,
                 peak_0p2_3_2HX_speed,
                 rms_5_13_1HX_max,
                 rms_5_13_1HX_speed,
                 rms_5_13_2HX_max,
                 rms_5_13_2HX_speed,
                 rms_5_13_1CX_max,
                 rms_5_13_1CX_speed,
                 rms_5_13_2CX_max,
                 rms_5_13_2CX_speed,
                 main_fre_amp_1CX_max,
                 main_fre_1CX,
                 main_fre_amp_1CX_speed,
                 main_fre_amp_2CX_max,
                 main_fre_2CX,
                 main_fre_amp_2CX_speed,
                 acc_max_1HX_max,
                 acc_max_1HX_speed,
                 acc_max_2HX_max,
                 acc_max_2HX_speed,
                 acc_valid_1HX_max,
                 acc_valid_1HX_speed,
                 acc_valid_2HX_max,
                 acc_valid_2HX_speed,
                 acc_max_1CX_max,
                 acc_max_1CX_speed,
                 acc_max_2CX_max,
                 acc_max_2CX_speed,
                 acc_valid_1CX_max,
                 acc_valid_1CX_speed,
                 acc_valid_2CX_max,
                 acc_valid_2CX_speed
                 ]
    return variables


def BIDS_data_judge(framelist, time_offset):
    """
    得到每一帧数据内容
    :param framelist: 数据帧列表
    :return:
    """
    # 定义 0-7 位的掩码变量
    BIT0_MASK = 0b00000001  # 第 0 位掩码
    BIT1_MASK = 0b00000010  # 第 1 位掩码
    BIT2_MASK = 0b00000100  # 第 2 位掩码
    BIT3_MASK = 0b00001000  # 第 3 位掩码
    BIT4_MASK = 0b00010000  # 第 4 位掩码
    BIT5_MASK = 0b00100000  # 第 5 位掩码
    BIT6_MASK = 0b01000000  # 第 6 位掩码
    BIT7_MASK = 0b10000000  # 第 7 位掩码

    speed_max = 0
    sharedata_comm = 0
    sensor_check = 0
    sensor_realtime = 0
    offset_fault = 0
    bogie_warn = 0
    bogie_alarm = 0
    min_1HX_max = 0
    min_1HX_speed = 0
    min_2HX_max = 0
    min_2HX_speed = 0
    min_3HX_max = 0
    min_3HX_speed = 0
    min_4HX_max = 0
    min_4HX_speed = 0
    mean_1HX_max = 0
    mean_1HX_speed = 0
    mean_2HX_max = 0
    mean_2HX_speed = 0
    mean_3HX_max = 0
    mean_3HX_speed = 0
    mean_4HX_max = 0
    mean_4HX_speed = 0
    max_1HX_max = 0
    max_1HX_speed = 0
    max_2HX_max = 0
    max_2HX_speed = 0
    max_3HX_max = 0
    max_3HX_speed = 0
    max_4HX_max = 0
    max_4HX_speed = 0
    rms_1HX_max = 0
    rms_1HX_speed = 0
    rms_2HX_max = 0
    rms_2HX_speed = 0
    rms_3HX_max = 0
    rms_3HX_speed = 0
    rms_4HX_max = 0
    rms_4HX_speed = 0
    max_1CX_max = 0
    max_1CX_speed = 0
    max_2CX_max = 0
    max_2CX_speed = 0
    max_3CX_max = 0
    max_3CX_speed = 0
    max_4CX_max = 0
    max_4CX_speed = 0
    rms_1CX_max = 0
    rms_1CX_speed = 0
    rms_2CX_max = 0
    rms_2CX_speed = 0
    rms_3CX_max = 0
    rms_3CX_speed = 0
    rms_4CX_max = 0
    rms_4CX_speed = 0

    for frame in framelist:
        # 创建 datetime 对象
        datetime_obj = extract_frame_time(frame, time_offset)
        dt = datetime.fromtimestamp(datetime_obj)
        # 格式化时间为 %Y-%m-%d %H:%M:%S
        formatted_time = dt.strftime("%Y-%m-%d %H:%M:%S")

        speed = struct.unpack('>H', frame[78:80])[0] * 0.01  # 速度 1=0.01km/h
        if (speed > speed_max):
            speed_max = speed
        if (frame[87] & BIT4_MASK) or (frame[87] & BIT5_MASK):
            sharedata_comm = formatted_time
        if (frame[89] & 0b00001111):
            sensor_check = formatted_time
        if (frame[89] & 0b11110000):
            sensor_realtime = formatted_time
        if (frame[90] & 0b00001111):
            offset_fault = formatted_time
        if (frame[91] & 0b00001111):
            bogie_warn = formatted_time
        if (frame[91] & 0b11110000):
            bogie_alarm = formatted_time
        min_1HX = struct.unpack('>H', frame[92:94])[0] * 0.001
        if (min_1HX > min_1HX_max):
            min_1HX_max = min_1HX
            min_1HX_speed = speed
        elif min_1HX == min_1HX_max:
            if speed > min_1HX_speed:
                min_1HX_speed = speed
        min_2HX = struct.unpack('>H', frame[94:96])[0] * 0.001
        if (min_2HX > min_2HX_max):
            min_2HX_max = min_2HX
            min_2HX_speed = speed
        elif min_2HX == min_2HX_max:
            if speed > min_2HX_speed:
                min_2HX_speed = speed
        min_3HX = struct.unpack('>H', frame[96:98])[0] * 0.001
        if (min_3HX > min_3HX_max):
            min_3HX_max = min_3HX
            min_3HX_speed = speed
        elif min_3HX == min_3HX_max:
            if speed > min_3HX_speed:
                min_3HX_speed = speed
        min_4HX = struct.unpack('>H', frame[98:100])[0] * 0.001
        if (min_4HX > min_4HX_max):
            min_4HX_max = min_4HX
            min_4HX_speed = speed
        elif min_4HX == min_4HX_max:
            if speed > min_4HX_speed:
                min_4HX_speed = speed
        mean_1HX = struct.unpack('>H', frame[100:102])[0] * 0.001
        if (mean_1HX > mean_1HX_max):
            mean_1HX_max = mean_1HX
            mean_1HX_speed = speed
        elif mean_1HX == mean_1HX_max:
            if speed > mean_1HX_speed:
                mean_1HX_speed = speed
        mean_2HX = struct.unpack('>H', frame[102:104])[0] * 0.001
        if (mean_2HX > mean_2HX_max):
            mean_2HX_max = mean_2HX
            mean_2HX_speed = speed
        elif mean_2HX == mean_2HX_max:
            if speed > mean_2HX_speed:
                mean_2HX_speed = speed
        mean_3HX = struct.unpack('>H', frame[104:106])[0] * 0.001
        if (mean_3HX > mean_3HX_max):
            mean_3HX_max = mean_3HX
            mean_3HX_speed = speed
        elif mean_3HX == mean_3HX_max:
            if speed > mean_3HX_speed:
                mean_3HX_speed = speed
        mean_4HX = struct.unpack('>H', frame[106:108])[0] * 0.001
        if (mean_4HX > mean_4HX_max):
            mean_4HX_max = mean_4HX
            mean_4HX_speed = speed
        elif mean_4HX == mean_4HX_max:
            if speed > mean_4HX_speed:
                mean_4HX_speed = speed
        max_1HX = struct.unpack('>H', frame[108:110])[0] * 0.001
        if (max_1HX > max_1HX_max):
            max_1HX_max = max_1HX
            max_1HX_speed = speed
        elif max_1HX == max_1HX_max:
            if speed > max_1HX_speed:
                max_1HX_speed = speed
        max_2HX = struct.unpack('>H', frame[110:112])[0] * 0.001
        if (max_2HX > max_2HX_max):
            max_2HX_max = max_2HX
            max_2HX_speed = speed
        elif max_2HX == max_2HX_max:
            if speed > max_2HX_speed:
                max_2HX_speed = speed
        max_3HX = struct.unpack('>H', frame[112:114])[0] * 0.001
        if (max_3HX > max_3HX_max):
            max_3HX_max = max_3HX
            max_3HX_speed = speed
        elif max_3HX == max_3HX_max:
            if speed > max_3HX_speed:
                max_3HX_speed = speed
        max_4HX = struct.unpack('>H', frame[114:116])[0] * 0.001
        if (max_4HX > max_4HX_max):
            max_4HX_max = max_4HX
            max_4HX_speed = speed
        elif max_4HX == max_4HX_max:
            if speed > max_4HX_speed:
                max_4HX_speed = speed
        rms_1HX = struct.unpack('>H', frame[116:118])[0] * 0.001
        if (rms_1HX > rms_1HX_max):
            rms_1HX_max = rms_1HX
            rms_1HX_speed = speed
        elif rms_1HX == rms_1HX_max:
            if speed > rms_1HX_speed:
                rms_1HX_speed = speed
        rms_2HX = struct.unpack('>H', frame[118:120])[0] * 0.001
        if (rms_2HX > rms_2HX_max):
            rms_2HX_max = rms_2HX
            rms_2HX_speed = speed
        elif rms_2HX == rms_2HX_max:
            if speed > rms_2HX_speed:
                rms_2HX_speed = speed
        rms_3HX = struct.unpack('>H', frame[120:122])[0] * 0.001
        if (rms_3HX > rms_3HX_max):
            rms_3HX_max = rms_3HX
            rms_3HX_speed = speed
        elif rms_3HX == rms_3HX_max:
            if speed > rms_3HX_speed:
                rms_3HX_speed = speed
        rms_4HX = struct.unpack('>H', frame[122:124])[0] * 0.001
        if (rms_4HX > rms_4HX_max):
            rms_4HX_max = rms_4HX
            rms_4HX_speed = speed
        elif rms_4HX == rms_4HX_max:
            if speed > rms_4HX_speed:
                rms_4HX_speed = speed
        max_1CX = struct.unpack('>H', frame[124:126])[0] * 0.001
        if (max_1CX > max_1CX_max):
            max_1CX_max = max_1CX
            max_1CX_speed = speed
        elif max_1CX == max_1CX_max:
            if speed > max_1CX_speed:
                max_1CX_speed = speed
        max_2CX = struct.unpack('>H', frame[126:128])[0] * 0.001
        if (max_2CX > max_2CX_max):
            max_2CX_max = max_2CX
            max_2CX_speed = speed
        elif max_2CX == max_2CX_max:
            if speed > max_2CX_speed:
                max_2CX_speed = speed
        max_3CX = struct.unpack('>H', frame[128:130])[0] * 0.001
        if (max_3CX > max_3CX_max):
            max_3CX_max = max_3CX
            max_3CX_speed = speed
        elif max_3CX == max_3CX_max:
            if speed > max_3CX_speed:
                max_3CX_speed = speed
        max_4CX = struct.unpack('>H', frame[130:132])[0] * 0.001
        if (max_4CX > max_4CX_max):
            max_4CX_max = max_4CX
            max_4CX_speed = speed
        elif max_4CX == max_4CX_max:
            if speed > max_4CX_speed:
                max_4CX_speed = speed
        rms_1CX = struct.unpack('>H', frame[132:134])[0] * 0.001
        if (rms_1CX > rms_1CX_max):
            rms_1CX_max = rms_1CX
            rms_1CX_speed = speed
        elif rms_1CX == rms_1CX_max:
            if speed > rms_1CX_speed:
                rms_1CX_speed = speed
        rms_2CX = struct.unpack('>H', frame[134:136])[0] * 0.001
        if (rms_2CX > rms_2CX_max):
            rms_2CX_max = rms_2CX
            rms_2CX_speed = speed
        elif rms_2CX == rms_2CX_max:
            if speed > rms_2CX_speed:
                rms_2CX_speed = speed
        rms_3CX = struct.unpack('>H', frame[136:138])[0] * 0.001
        if (rms_3CX > rms_3CX_max):
            rms_3CX_max = rms_3CX
            rms_3CX_speed = speed
        elif rms_3CX == rms_3CX_max:
            if speed > rms_3CX_speed:
                rms_3CX_speed = speed
        rms_4CX = struct.unpack('>H', frame[138:140])[0] * 0.001
        if (rms_4CX > rms_4CX_max):
            rms_4CX_max = rms_4CX
            rms_4CX_speed = speed
        elif rms_4CX == rms_4CX_max:
            if speed > rms_4CX_speed:
                rms_4CX_speed = speed

    variables = [speed_max,
                 sharedata_comm,
                 sensor_check,
                 sensor_realtime,
                 offset_fault,
                 bogie_warn,
                 bogie_alarm,
                 min_1HX_max,
                 min_1HX_speed,
                 min_2HX_max,
                 min_2HX_speed,
                 min_3HX_max,
                 min_3HX_speed,
                 min_4HX_max,
                 min_4HX_speed,
                 mean_1HX_max,
                 mean_1HX_speed,
                 mean_2HX_max,
                 mean_2HX_speed,
                 mean_3HX_max,
                 mean_3HX_speed,
                 mean_4HX_max,
                 mean_4HX_speed,
                 max_1HX_max,
                 max_1HX_speed,
                 max_2HX_max,
                 max_2HX_speed,
                 max_3HX_max,
                 max_3HX_speed,
                 max_4HX_max,
                 max_4HX_speed,
                 rms_1HX_max,
                 rms_1HX_speed,
                 rms_2HX_max,
                 rms_2HX_speed,
                 rms_3HX_max,
                 rms_3HX_speed,
                 rms_4HX_max,
                 rms_4HX_speed,
                 max_1CX_max,
                 max_1CX_speed,
                 max_2CX_max,
                 max_2CX_speed,
                 max_3CX_max,
                 max_3CX_speed,
                 max_4CX_max,
                 max_4CX_speed,
                 rms_1CX_max,
                 rms_1CX_speed,
                 rms_2CX_max,
                 rms_2CX_speed,
                 rms_3CX_max,
                 rms_3CX_speed,
                 rms_4CX_max,
                 rms_4CX_speed
                 ]
    return variables


def GVDS_data_judge(framelist, time_offset):
    """
    得到每一帧数据内容
    :param framelist: 数据帧列表
    :return:
    """
    res = [0] * 199  # 按照点检表顺序，第一个字节对应点检表中的速度 索引0对应点检表第8行

    for frame in framelist:
        # 创建 datetime 对象
        datetime_obj = extract_frame_time(frame, time_offset)
        dt = datetime.fromtimestamp(datetime_obj)
        # 格式化时间为 %Y-%m-%d %H:%M:%S
        formatted_time = dt.strftime("%Y-%m-%d %H:%M:%S")

        speed = struct.unpack('>H', frame[78:80])[0] * 0.01  # 速度 1=0.01km/h
        if (speed > res[0]):
            res[0] = speed
        if (frame[87] & 0b00110000):
            res[1] = formatted_time
        if (frame[88] or frame[89]):
            res[2] = formatted_time
        if (frame[218] or frame[221] or frame[232] or frame[233] or frame[234] or frame[235] or frame[238] or frame[
            247] or
                frame[248] or frame[249] or frame[250] or frame[253]):
            res[3] = formatted_time
        if (frame[219] or frame[222] or frame[224] or frame[225] or frame[226] or frame[227] or frame[236] or frame[
            239] or
                frame[240] or frame[241] or frame[242] or frame[251]):
            res[4] = formatted_time
        if (frame[220] or frame[223] or frame[228] or frame[229] or frame[230] or frame[231] or frame[237] or frame[
            243] or
                frame[244] or frame[245] or frame[246] or frame[252]):
            res[5] = formatted_time

        for i in range(16):
            if frame[286 + i] * 0.1 < 8 or frame[286 + i] * 0.1 > 14:
                res[6] = formatted_time
        for i in range(4):
            if (frame[92 + i] > res[7 + i * 2]):
                res[7 + i * 2] = frame[92 + i]
                res[7 + 1 + i * 2] = speed
            elif frame[92 + i] == res[7 + i * 2]:
                if (speed > res[7 + 1 + i * 2]):
                    res[7 + 1 + i * 2] = speed
        for i in range(4):
            if (frame[104 + i] > res[15 + i * 2]):
                res[15 + i * 2] = frame[104 + i]
                res[15 + 1 + i * 2] = speed
            elif frame[104 + i] == res[15 + i * 2]:
                if speed > res[15 + 1 + i * 2]:
                    res[15 + 1 + i * 2] = speed
        for i in range(4):
            if frame[116 + i] > res[23 + i * 2]:
                res[23 + i * 2] = frame[116 + i]
                res[23 + 1 + i * 2] = speed
            elif frame[116 + i] == res[23 + i * 2]:
                if speed > res[23 + 1 + i * 2]:
                    res[23 + 1 + i * 2] = speed
        for i in range(4):
            if frame[128 + i] > res[31 + i * 2]:
                res[31 + i * 2] = frame[128 + i]
                res[31 + 1 + i * 2] = speed
            elif frame[128 + i] == res[31 + i * 2]:
                if speed > res[31 + 1 + i * 2]:
                    res[31 + 1 + i * 2] = speed
        for i in range(4):
            if frame[140 + i] > res[39 + i * 2]:
                res[39 + i * 2] = frame[140 + i]
                res[39 + 1 + i * 2] = speed
            elif frame[140 + i] == res[39 + i * 2]:
                if speed > res[39 + 1 + i * 2]:
                    res[39 + 1 + i * 2] = speed
        for i in range(4):
            if frame[152 + i] > res[47 + i * 2]:
                res[47 + i * 2] = frame[152 + i]
                res[47 + 1 + i * 2] = speed
            elif frame[152 + i] == res[47 + i * 2]:
                if speed > res[47 + 1 + i * 2]:
                    res[47 + 1 + i * 2] = speed
        for i in range(4):
            if frame[164 + i] > res[55 + i * 2]:
                res[55 + i * 2] = frame[164 + i]
                res[55 + 1 + i * 2] = speed
            elif frame[164 + i] == res[55 + i * 2]:
                if speed > res[55 + 1 + i * 2]:
                    res[55 + 1 + i * 2] = speed
        for i in range(4):
            if frame[176 + i] > res[63 + i * 2]:
                res[63 + i * 2] = frame[176 + i * 2]
                res[63 + 1 + i * 2] = speed
            elif frame[176 + i] == res[63 + i * 2]:
                if speed > res[63 + 1 + i * 2]:
                    res[63 + 1 + i * 2] = speed
        for i in range(4):
            if frame[98 + i] > res[71 + i * 2]:
                res[71 + i * 2] = frame[98 + i]
                res[71 + 1 + i * 2] = speed
            elif frame[98 + i] == res[71 + i * 2]:
                if speed > res[71 + 1 + i * 2]:
                    res[71 + 1 + i * 2] = speed
        for i in range(4):
            if frame[110 + i] > res[79 + i * 2]:
                res[79 + i * 2] = frame[110 + i]
                res[79 + 1 + i * 2] = speed
            elif frame[110 + i] == res[79 + i * 2]:
                if speed > res[79 + 1 + i * 2]:
                    res[79 + 1 + i * 2] = speed
        for i in range(4):
            if frame[122 + i] > res[87 + i * 2]:
                res[87 + i * 2] = frame[122 + i]
                res[87 + 1 + i * 2] = speed
            elif frame[122 + i] == res[87 + i * 2]:
                if speed > res[87 + 1 + i * 2]:
                    res[87 + 1 + i * 2] = speed
        for i in range(4):
            if frame[134 + i] > res[95 + i * 2]:
                res[95 + i * 2] = frame[134 + i]
                res[95 + 1 + i * 2] = speed
            elif frame[134 + i] == res[95 + i * 2]:
                if speed > res[95 + 1 + i * 2]:
                    res[95 + 1 + i * 2] = speed
        for i in range(4):
            if frame[146 + i] > res[103 + i * 2]:
                res[103 + i * 2] = frame[146 + i * 2]
                res[103 + 1 + i * 2] = speed
            elif frame[146 + i] == res[103 + i * 2]:
                if speed > res[103 + 1 + i * 2]:
                    res[103 + 1 + i * 2] = speed
        for i in range(4):
            if frame[158 + i] > res[111 + i * 2]:
                res[111 + i * 2] = frame[158 + i]
                res[111 + 1 + i * 2] = speed
            elif frame[158 + i] == res[111 + i * 2]:
                if speed > res[111 + 1 + i * 2]:
                    res[111 + 1 + i * 2] = speed
        for i in range(4):
            if frame[170 + i] > res[119 + i * 2]:
                res[119 + i * 2] = frame[170 + i]
                res[119 + 1 + i * 2] = speed
            elif frame[170 + i] == res[119 + i * 2]:
                if speed > res[119 + 1 + i * 2]:
                    res[119 + 1 + i * 2] = speed
        for i in range(4):
            if frame[182 + i] > res[127 + i * 2]:
                res[127 + i * 2] = frame[182 + i]
                res[127 + 1 + i * 2] = speed
            elif frame[182 + i] == res[127 + i * 2]:
                if speed > res[127 + 1 + i * 2]:
                    res[127 + 1 + i * 2] = speed
        for i in range(4):
            val = struct.unpack('>H', frame[186 + i * 2:186 + i * 2 + 2])[0] * 0.1
            if (val > res[135 + i * 2]):
                res[135 + i * 2] = val
                res[135 + 1 + i * 2] = speed
            elif val == res[135 + i * 2]:
                if speed > res[135 + i * 2 + 1]:
                    res[135 + i * 2 + 1] = speed
        for i in range(4):
            byteoffset = 202
            djoffset = 143
            val = struct.unpack('>H', frame[byteoffset + i * 2: byteoffset + i * 2 + 2])[0] * 0.1
            if (val > res[djoffset + i * 2]):
                res[djoffset + i * 2] = val
                res[djoffset + i * 2 + 1] = speed
            elif val == res[djoffset + i * 2]:
                if speed > res[djoffset + i * 2 + 1]:
                    res[djoffset + i * 2 + 1] = speed
        for i in range(4):
            byteoffset = 194
            djoffset = 151
            val = struct.unpack('>H', frame[byteoffset + i * 2: byteoffset + i * 2 + 2])[0] * 0.1
            if (val > res[djoffset + i * 2]):
                res[djoffset + i * 2] = val
                res[djoffset + i * 2 + 1] = speed
            elif val == res[djoffset + i * 2]:
                if speed > res[djoffset + i * 2 + 1]:
                    res[djoffset + i * 2 + 1] = speed
        for i in range(4):
            byteoffset = 210
            djoffset = 159
            val = struct.unpack('>H', frame[byteoffset + i * 2: byteoffset + i * 2 + 2])[0] * 0.1
            if (val > res[djoffset + i * 2]):
                res[djoffset + i * 2] = val
                res[djoffset + i * 2 + 1] = speed
            elif val == res[djoffset + i * 2]:
                if speed > res[djoffset + i * 2 + 1]:
                    res[djoffset + i * 2 + 1] = speed
        for i in range(4):
            byteoffset = 254
            djoffset = 167
            val = struct.unpack('>H', frame[byteoffset + i * 2: byteoffset + i * 2 + 2])[0] * 0.1
            if (val > res[djoffset + i * 2]):
                res[djoffset + i * 2] = val
                res[djoffset + i * 2 + 1] = speed
            elif val == res[djoffset + i * 2]:
                if speed > res[djoffset + i * 2 + 1]:
                    res[djoffset + i * 2 + 1] = speed
        for i in range(4):
            byteoffset = 270
            djoffset = 175
            val = struct.unpack('>H', frame[byteoffset + i * 2: byteoffset + i * 2 + 2])[0] * 0.1
            if (val > res[djoffset + i * 2]):
                res[djoffset + i * 2] = val
                res[djoffset + i * 2 + 1] = speed
            elif val == res[djoffset + i * 2]:
                if speed > res[djoffset + i * 2 + 1]:
                    res[djoffset + i * 2 + 1] = speed
        for i in range(4):
            byteoffset = 262
            djoffset = 183
            val = struct.unpack('>H', frame[byteoffset + i * 2: byteoffset + i * 2 + 2])[0] * 0.1
            if (val > res[djoffset + i * 2]):
                res[djoffset + i * 2] = val
                res[djoffset + i * 2 + 1] = speed
            elif val == res[djoffset + i * 2]:
                if speed > res[djoffset + i * 2 + 1]:
                    res[djoffset + i * 2 + 1] = speed
        for i in range(4):
            byteoffset = 278
            djoffset = 191
            val = struct.unpack('>H', frame[byteoffset + i * 2: byteoffset + i * 2 + 2])[0] * 0.1
            if (val > res[djoffset + i * 2]):
                res[djoffset + i * 2] = val
                res[djoffset + i * 2 + 1] = speed
            elif val == res[djoffset + i * 2]:
                if speed > res[djoffset + i * 2 + 1]:
                    res[djoffset + i * 2 + 1] = speed

    return res


def MVDS_data_judge(framelist, time_offset):
    """
    得到每一帧数据内容
    :param framelist: 数据帧列表
    :return:
    """
    res = [0] * 119  # 按照点检表顺序，第一个字节对应点检表中的速度 索引0对应点检表第8行

    for frame in framelist:
        # 创建 datetime 对象
        datetime_obj = extract_frame_time(frame, time_offset)
        dt = datetime.fromtimestamp(datetime_obj)
        # 格式化时间为 %Y-%m-%d %H:%M:%S
        formatted_time = dt.strftime("%Y-%m-%d %H:%M:%S")

        speed = round(struct.unpack('>H', frame[78:80])[0] * 0.01, 3)  # 速度 1=0.01km/h
        if (speed > res[0]):
            res[0] = speed
        if (frame[87] & 0b00110000):
            res[1] = formatted_time
        if (frame[88] != 0):
            res[2] = formatted_time
        if (frame[137] or frame[148] or frame[149] or frame[150] or frame[151]):
            res[3] = formatted_time
        if (frame[138] or frame[140] or frame[141] or frame[142] or frame[143]):
            res[4] = formatted_time
        if (frame[139] or frame[144] or frame[145] or frame[146] or frame[147]):
            res[5] = formatted_time

        for i in range(8):
            mvds_byte = 184
            if frame[mvds_byte + i] * 0.1 < 8 or frame[mvds_byte + i] * 0.1 > 14:
                res[6] = formatted_time
        chuandong_cnt = 7
        nochuandong_cnt = 47
        for i in range(48):
            if i % 6 == 1:  # 每组第二次跳过
                continue
            zhibiao = frame[89 + i]
            if (i // 6) % 2 == 0:  # 偶数组
                if zhibiao > res[chuandong_cnt]:
                    res[chuandong_cnt] = zhibiao
                    res[chuandong_cnt + 1] = speed
                elif zhibiao == res[chuandong_cnt]:
                    if speed > res[chuandong_cnt + 1]:
                        res[chuandong_cnt + 1] = speed
                chuandong_cnt = chuandong_cnt + 2
            else:  # 奇数组
                if zhibiao > res[nochuandong_cnt]:
                    res[nochuandong_cnt] = zhibiao
                    res[nochuandong_cnt + 1] = speed
                elif zhibiao == res[nochuandong_cnt]:
                    if speed > res[nochuandong_cnt + 1]:
                        res[nochuandong_cnt + 1] = speed
                nochuandong_cnt = nochuandong_cnt + 2
        chuandong_cnt = 87
        nochuandong_cnt = 95
        for i in range(8):
            val = round(struct.unpack('>H', frame[152 + i * 2:152 + i * 2 + 2])[0] * 0.1, 3)
            if i % 2 == 0:
                if val > res[chuandong_cnt]:
                    res[chuandong_cnt] = val
                    res[chuandong_cnt + 1] = speed
                elif val == res[chuandong_cnt]:
                    if speed > res[chuandong_cnt + 1]:
                        res[chuandong_cnt + 1] = speed
                chuandong_cnt = chuandong_cnt + 2
            else:
                if val > res[nochuandong_cnt]:
                    res[nochuandong_cnt] = val
                    res[nochuandong_cnt + 1] = speed
                elif val == res[nochuandong_cnt]:
                    if speed > res[nochuandong_cnt + 1]:
                        res[nochuandong_cnt + 1] = speed
                nochuandong_cnt = nochuandong_cnt + 2

        chuandong_cnt = 103
        nochuandong_cnt = 111
        bype_cnt = 168
        for i in range(8):
            val = round(struct.unpack('>H', frame[bype_cnt:bype_cnt + 2])[0] * 0.1, 3)
            if i % 2 == 0:
                if val > res[chuandong_cnt]:
                    res[chuandong_cnt] = val
                    res[chuandong_cnt + 1] = speed
                elif val == res[chuandong_cnt]:
                    if speed > res[chuandong_cnt + 1]:
                        res[chuandong_cnt + 1] = speed
                chuandong_cnt = chuandong_cnt + 2
            else:
                if val > res[nochuandong_cnt]:
                    res[nochuandong_cnt] = val
                    res[nochuandong_cnt + 1] = speed
                elif val == res[nochuandong_cnt]:
                    if speed > res[nochuandong_cnt + 1]:
                        res[nochuandong_cnt + 1] = speed
                nochuandong_cnt = nochuandong_cnt + 2
            bype_cnt = bype_cnt + 2

    return res


class DataCheck():

    def read_json_file(self):
        config_path = "datacheck.json"
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                cfg_data = json.load(f)
                return cfg_data
        except FileNotFoundError:
            save_print_to_txt('./log.txt', f"错误：文件 {config_path} 不存在")
            print(f"错误：文件 {config_path} 不存在")
        except json.JSONDecodeError:
            save_print_to_txt('./log.txt', f"错误：文件 {config_path} 不是有效的 JSON 格式")
            print(f"错误：文件 {config_path} 不是有效的 JSON 格式")

    def data_process(self):
        log_file = 'log.txt'
        if os.path.exists(log_file):
            os.remove(log_file)
            print(f"文件已删除: {log_file}")

        cfg_data = self.read_json_file()
        filepath = cfg_data['filepath']
        for obj in cfg_data['obj']:
            save_print_to_txt("./log.txt", f"========{obj['obj1']}=========")
            folder = os.path.join(filepath, obj['obj1'])
            data_file = merge_dat_files(folder, f"{obj['obj1']}".lower())

            if data_file is None:
                continue
            frameoffset = obj['frameoffset']
            timeoffset = obj['timeoffset']
            starttime = obj['starttime']
            endtime = obj['endtime']
            framesize = obj['framesize']

            for data_path in data_file:
                frame_data = read_binary_file(data_path, frameoffset, timeoffset, starttime, endtime, framesize)
                if not frame_data:
                    # 如果 frame_data 为空，执行相应的操作
                    save_print_to_txt('./log.txt', '++++++++所给时间段的数据为空+++++++++', starttime, endtime)
                    print("帧列表为空")
                    continue
                if obj['obj1'] == "WNDS":
                    result = WNDS_data_judge(frame_data, timeoffset)
                elif obj['obj1'] == "BIDS":
                    result = BIDS_data_judge(frame_data, timeoffset)
                elif obj['obj1'] == "GVDS":
                    result = GVDS_data_judge(frame_data, timeoffset)
                elif obj['obj1'] == "MVDS":
                    result = MVDS_data_judge(frame_data, timeoffset)
                else:
                    continue
                # 获取文件名（带扩展名）
                filename_with_extension = os.path.basename(data_path)
                # 去掉扩展名
                filename_without_extension = os.path.splitext(filename_with_extension)[0]
                save_variables_to_file(result, starttime, filename_without_extension, file_path=folder)


# 示例用法
if __name__ == "__main__":
    dc = DataCheck()
    dc.data_process()
    print("exit(0)")
