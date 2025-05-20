from dotenv import dotenv_values
from aip import AipSpeech
from pymodbus.client import ModbusSerialClient
from pymodbus import ModbusException

config = dotenv_values()

# 读取modbus连接环境变量
PORT: str = config["PORT"]
BAUDRATE: int = int(config["BAUDRATE"])
BYTESIZE: int = int(config["BYTESIZE"])
PARITY: str = config["PARITY"]
STOPBITS: int = int(config["STOPBITS"])
SLAVE: int = int(config["SLAVE"])

# 读取百度语音识别环境变量
APP_ID: str = config["APP_ID"]
API_KEY: str = config["API_KEY"]
SEC_KEY: str = config["SEC_KEY"]

modbusClient: ModbusSerialClient
speechClient: AipSpeech


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
        speechClient.setConnectionTimeoutInMillis(5)

    except ModbusException as e:
        print("模块连接失败,请尝试重新连接模块!")
        raise e
    except Exception as e:
        print("初始化失败,请重新尝试!")
        raise e
    else:
        print("初始化成功!!!")


def read_coil() -> bool:
    try:
        return bool(modbusClient.read_coils(0, count=1, slave=SLAVE).bits[0])
    except ModbusException as e:
        print("模块连接错误,请重新尝试!")
        raise e


def write_coil(status: bool) -> bool:
    try:
        cur = read_coil()
        if cur == status:
            return False
        modbusClient.write_coil(0, status, slave=SLAVE)
        return True
    except ModbusException as e:
        print("模块连接错误,请重新尝试!")
        raise e


def main():
    init()


if __name__ == "__main__":
    main()
