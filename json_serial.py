import serial
import json
import time
from typing import Union, List, Dict, Any


def dicttobyte(the_dict):
    """
    converts json bytecodes
    :param the_dict:
    :return:
    """
    return (json.dumps(the_dict) + '\r\n').encode('utf-8')


class JsonSerialPort:

    def __init__(self, port_id: str = "/dev/ttyS0", baudrate: int = 115200, timeout: float = 0.5):
        self.ser = None
        self.buf = ""
        self.error = ""
        self.port_id = port_id
        self.timeout = timeout
        self.baudrate = baudrate

    def open(self):
        """
        opens serial port if possible
        :return:
        """
        self.error = ""
        try:
            self.ser.close()
        except (serial.SerialException, AttributeError):
            pass
        try:
            self.ser = serial.Serial(self.port_id, baudrate=self.baudrate, timeout=self.timeout,
                                     write_timeout=self.timeout)
        except (serial.SerialException, AttributeError):
            self.error = "Serial port open error"

    def write(self, data: Union[bytes, str], encode: bool = True, eol: bool = True):
        """
        writes data to serial port, encoding if necessary and adding end of line if necessary
        :param eol: add '\r\n' or not
        :param encode: encode data or not
        :param data: bytes to write
        :return:
        """
        self.error = ""
        if self.ser.is_open:
            try:
                self.ser.reset_input_buffer()
                self.ser.reset_output_buffer()
                data = data + '\r\n' if eol else data
                bytes_to_send: bytes = data.encode('utf-8') if encode else data
                res = self.ser.write(bytes_to_send)
                if res != len(data):
                    self.error = "write function failed\n"
            except serial.SerialTimeoutException:
                self.error = 'Cannot write data\n'

    def read_str(self) -> str:
        """
        reads all data in input buffer and converts to str
        :return: response converted to str
        """
        self.error = ""
        response: bytes = self.ser.readall()
        try:
            responsestr: str = response.decode(encoding='utf-8')
        except UnicodeDecodeError:
            responsestr = ""
            # todo check ord and chr
            for b in response:
                if b < 127:
                    responsestr += chr(b)
                elif not self.error:
                    self.error = "Decoding error\n"
        return responsestr

    def readall(self) -> bytes:
        """
        just ser readall
        :return:
        """
        return self.ser.readall()

    def get_next_json(self, timeout: float = 1):
        """
        trys to get valid json during timeout
        :param timeout:
        :return:
        """
        self.error = ""
        current_time = 0
        time_delta = 0.1
        while current_time < timeout:
            chunk = self.read_str()
            self.buf += chunk
            if '{' in self.buf:
                start = self.buf.index('{')
                # todo it must be last check
                if '}' in self.buf:
                    end = self.buf.rindex('}')
                    try:
                        json_try = self.buf[start: end + 1]
                        json.loads(json_try, encoding='utf-8')
                        self.buf = self.buf[end + 1:]
                        return json_try
                    except json.decoder.JSONDecodeError:
                        pass
            time.sleep(time_delta)
            current_time += time_delta
        self.error = "no json found"
        return ""

    def close(self):
        """
        closes serial port
        :return:
        """
        self.error = ""
        try:
            self.ser.close()
        except serial.SerialException:
            self.error = "Error closing serial port"

    def flush_input(self):
        """
        flushes seial port input
        :return:
        """
        self.ser.reset_input_buffer()
        self.buf = ""

    def several_cycles(self, data: Dict[str, Any], count: int = 1, timeout: int = 1) -> List[str]:
        """
        opens port, writes data, gets count numvber of json correct strings and returns List of them
        :param timeout: time for json waiting
        :param data: data to send (in bytes with eol)
        :param count: number of jsons to get
        :return:
        """
        self.open()
        if self.error:
            print(self.error)
        data_bytes = dicttobyte(data)
        self.write(data_bytes, False, False)
        if self.error:
            print(self.error)
        res = list()
        for i in range(count):
            temp = self.get_next_json(timeout)
            print(temp)
            res.append(temp)
            if self.error:
                print(self.error)
        self.close()
        return res

    def full_one_cycle(self, data: Dict[str, Any], timeout: int = 1) -> str:
        """
        opens port, writes data, gets json correct strings and returns it
        :param timeout: time for json waiting
        :param data: data to send (in bytes with eol)
        :return:
        """
        self.open()
        if self.error:
            print(self.error)
        data_bytes = dicttobyte(data)
        self.write(data_bytes, False, False)
        if self.error:
            print(self.error)
        temp = self.get_next_json(timeout)
        if self.error:
            print(self.error)
        self.close()
        return temp

    def full_one_cycle_with_key(self, data: Dict[str, Any], key='result', timeout: int = 1):
        """
        opens serial port, gets data and gets data for given key
        :param data: data dict
        :param timeout:timeout in s
        :param key: key to get in response
        :return: responce data fo key
        """
        json_str = self.full_one_cycle(data, timeout)
        if json_str:
            data = json.loads(json_str.lower(), encoding='utf')
            if key.lower() in data.keys():
                return data[key]
        self.error = "No result for %s key" % key
        print(self.error)
        return ""


# simple test
if __name__ == "__main__":
    port = JsonSerialPort('COM7')
    print(port.full_one_cycle_with_key({"Test": 1}, 'test'))
