#!/usr/bin/python3

# This script will read data from serial connected to the digital meter P1 port

# Created by Jens Depuydt
# https://www.jensd.be
# https://github.com/jensdepuydt
import json
import logging
import serial
import sys
import crcmod.predefined
import re
from tabulate import tabulate

# Change your serial port here:
SERIALPORT = '/dev/ttyUSB0'

# Enable DEBUG if needed:
DEBUG = False

class P1Reader():

    def __init__(self, logger=None):
        if not logger:
            logger = self.add_logger()
        self.logger = logger
        self.obiscodes = self.read_obis()

    def add_logger(self):
        logger = logging.getLogger(__name__)
        logger.setLevel(logging.DEBUG)

        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        return logger

    def read_obis(self):
        with open('obiscodes.json', 'r') as fh:
            return json.load(fh)

    def checkcrc(self, p1telegram):
        # check CRC16 checksum of telegram and return False if not matching
        # split telegram in contents and CRC16 checksum (format:contents!crc)
        for match in re.compile(b'\r\n(?=!)').finditer(p1telegram):
            p1contents = p1telegram[:match.end() + 1]
            # CRC is in hex, so we need to make sure the format is correct
            givencrc = hex(int(p1telegram[match.end() + 1:].decode('ascii').strip(), 16))
        # calculate checksum of the contents
        calccrc = hex(crcmod.predefined.mkPredefinedCrcFun('crc16')(p1contents))
        # check if given and calculated match
        if DEBUG:
            self.logger.debug(f"Given checksum: {givencrc}, Calculated checksum: {calccrc}")
        if givencrc != calccrc:
            if DEBUG:
                self.logger.debug("Checksum incorrect, skipping...")
            return False
        return True


    def parsetelegramline(self, p1line):
        # parse a single line of the telegram and try to get relevant data from it
        unit = None
        timestamp = ""
        if DEBUG:
            self.logger.debug(f"Parsing:{p1line}")
        # get OBIS code from line (format:OBIS(value)
        obis = p1line.split("(")[0]
        if DEBUG:
            self.logger.debug(f"OBIS:{obis}")
        # check if OBIS code is something we know and parse it
        if obis in self.obiscodes:
            description, device_class = self.obiscodes[obis].values()
            # get values from line.
            # format:OBIS(value), gas: OBIS(timestamp)(value)
            values = re.findall(r'\(.*?\)', p1line)
            value = values[0][1:-1]
            # timestamp requires removal of last char
            if obis == "0-0:1.0.0" or len(values) > 1:
                value = value[:-1]
            # report of connected gas-meter...
            if len(values) > 1:
                timestamp = value
                value = values[1][1:-1]
            # serial numbers need different parsing: (hex to ascii)
            if "96.1.1" in obis:
                value = bytearray.fromhex(value).decode()
            else:
                # separate value and unit (format:value*unit)
                lvalue = value.split("*")
                value = float(lvalue[0])
                if len(lvalue) > 1:
                    unit = lvalue[1]
            # return result in tuple: description,value,unit,timestamp
            if DEBUG:
                self.logger.debug (f"description:{description}, \
                        value:{value}, \
                        unit:{unit}")
            return (description, value, unit, device_class)
        else:
            return ()


    def run(self):
        ser = serial.Serial(SERIALPORT, 115200, xonxoff=1)
        p1telegram = bytearray()
        readings = {}
        while True:
            try:
                # read input from serial port
                p1line = ser.readline()
                if DEBUG:
                    self.logger.debug("Reading: %s", p1line.strip())
                # P1 telegram starts with /
                # We need to create a new empty telegram
                if "/" in p1line.decode('ascii'):
                    if DEBUG:
                        self.logger.debug("Found beginning of P1 telegram")
                    p1telegram = bytearray()
                    self.logger.info('*' * 60 + "\n")
                # add line to complete telegram
                p1telegram.extend(p1line)
                # P1 telegram ends with ! + CRC16 checksum
                if "!" in p1line.decode('ascii'):
                    if DEBUG:
                        self.logger.debug("Found end, self.logger.debuging full telegram")
                        self.logger.debug('*' * 40)
                        self.logger.debug(p1telegram.decode('ascii').strip())
                        self.logger.debug('*' * 40)
                    if self.checkcrc(p1telegram):
                        # parse telegram contents, line by line
                        output = []
                        for line in p1telegram.split(b'\r\n'):
                            r = self.parsetelegramline(line.decode('ascii'))
                            if r:
                                name, value, unit, device_class = r
                                key = name.replace(' ', '_').lower()

                                readings[key] = dict(value=value, unit=unit, device_class=device_class, state_class="total_increasing", name=name)
                                output.append(r)
                                if DEBUG:
                                    self.logger.debug(f"desc:{r[0]}, val:{r[1]}, u:{r[2]}")
                        if DEBUG:
                            self.logger.info(tabulate(output, headers=['Description', 'Value', 'Unit'], tablefmt='github'))
                        break

            except:
                # self.logger.info(traceback.format_exc())
                self.logger.exception("Something went wrong...")
                ser.close()
                break

        # flush the buffer
        ser.flush()
        self.logger.info(readings)
        return readings

if __name__ == '__main__':
    p1 = P1Reader()
    p1.run()
