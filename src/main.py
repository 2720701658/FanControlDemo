from dotenv import dotenv_values
from aip import AipSpeech
from pymodbus.client import ModbusSerialClient
from pymodbus import ModbusException
from serial import SerialException
import threading
from time import sleep
import os
from pynput import keyboard
from pynput.keyboard import Key, KeyCode
import pyaudio
import wave
from urllib3.exceptions import HTTPError

config = dotenv_values()

# 读取485串口配置
PORT: str = config["PORT"]
BAUDRATE: int = int(config["BAUDRATE"])
BYTESIZE: int = int(config["BYTESIZE"])
PARITY: str = config["PARITY"]
STOPBITS: int = int(config["STOPBITS"])
SLAVE: int = int(config["SLAVE"])

# 读取百度语音识别配置
APP_ID: str = config["APP_ID"]
API_KEY: str = config["API_KEY"]
SEC_KEY: str = config["SEC_KEY"]

modbusClient: ModbusSerialClient = None
speechClient: AipSpeech = None


def init() -> None:
    """
    初始化Modbus和百度语音识别Client
    """
    try:
        global modbusClient
        global speechClient

        modbusClient = ModbusSerialClient(
            PORT,
            baudrate=BAUDRATE,
            bytesize=BYTESIZE,
            parity=PARITY,
            stopbits=STOPBITS,
            timeout=5,
        )
        modbusClient.connect()
        results = modbusClient.read_holding_registers(0, count=11, slave=SLAVE)
        print("模块名称:", hex(results.registers[0]))
        modbusClient.write_coil(0, False, slave=SLAVE)

        speechClient = AipSpeech(appId=APP_ID, apiKey=API_KEY, secretKey=SEC_KEY)
        speechClient.setConnectionTimeoutInMillis(5000)
        print("百度语音识别版本:", speechClient.getVersion())

    except Exception as e:
        print("初始化失败,正在退出,请重新连接模块并检查语音识别api配置!")
        raise e
    else:
        print("初始化成功!!!")


def read_coil() -> bool:
    """
    读线圈获取风扇状态
    :return: True:风扇接通 False:风扇关闭
    """
    try:
        global modbusClient

        return bool(modbusClient.read_coils(0, count=1, slave=SLAVE).bits[0])
    except (ModbusException, SerialException) as e:
        print("模块连接错误,请重新连接模块!")
        raise e


def write_coil(status: bool) -> bool:
    """
    写线圈改变风扇状态
    :param: status: 为True时要求接通,为False时要求关闭
    :return: True: 需要写线圈且成功 False 不需要写线圈
    """
    try:
        global modbusClient

        cur = read_coil()
        if cur == status:
            return False
        modbusClient.write_coil(0, status, slave=SLAVE)
        return True
    except (ModbusException, SerialException) as e:
        print("模块连接错误,请重新连接模块!")
        raise e


def monitor() -> None:
    """
    每5秒打印当前风扇状态
    """
    try:
        while True:
            status: bool = read_coil()
            print("当前风扇状态:", "接通" if status else "关闭")
            sleep(5)
    except (ModbusException, SerialException):
        os._exit(-1)


def record(duration: int) -> None:
    """
    录音并保存为output.wav文件
    :param duration: 录音持续的时间
    """
    try:
        with wave.open("output.wav", "wb") as w:
            p = pyaudio.PyAudio()
            # 设置帧数率为16000(固定值), 通道数为1, 精度为16位整型
            w.setframerate(16000)
            w.setnchannels(1)
            w.setsampwidth(p.get_sample_size(pyaudio.paInt32))
            stream = p.open(rate=16000, channels=1, format=pyaudio.paInt16, input=True)
            print("录音中...")
            for i in range(0, 16000 // 1024 * duration):
                w.writeframes(stream.read(1024))
            print("录音完成")
            stream.close()
            p.terminate()
    except Exception as e:
        print("录音错误!")
        raise e


def upload() -> str:
    try:
        with open("output.wav", "rb") as file:
            global speechClient

            res: dict[str, str] = speechClient.asr(file.read(), "wav", 16000)
            speech: str = res["result"][0]
            return speech
    except (urllib3.exceptions.HTTPError, KeyError) as e:
        print("语音解析错误!")
        raise e


def on_press(key: Key | KeyCode) -> None:
    """
    监听键盘按下事件,按下V键时进行语音输入,按下Esc键退出程序
    :param key: 检测到按下的键
    """
    try:
        if key.char == "v":
            record(5)
            speech = upload()
            print("输入语音为:", speech)
            if speech in ("打开风扇。", "关闭风扇。"):
                write_coil(True) if speech == "打开风扇。" else write_coil(False)
                print("风扇已接通") if speech == "打开风扇。" else print("风扇已关闭")
            else:
                print("语音指令错误!")
    except AttributeError:
        if key == keyboard.Key.esc:
            print("正在退出...")
            write_coil(False)
            modbusClient.close()
            os._exit(0)
    except (HTTPError, KeyError) as e:
        print(e)


def main() -> None:
    """
    主函数,调用初始化函数以及创建两个thread分别打印风扇状态和监听键盘事件
    """
    init()
    threading.Thread(target=monitor, daemon=True).start()
    with keyboard.Listener(on_press=on_press) as listener:
        listener.join()


if __name__ == "__main__":
    main()
