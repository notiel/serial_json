"""
OpenHTF-based tool to run tests
"""

import os
import argparse
import logging
import subprocess
import sys
import time
import webbrowser
import smbus
import re
import serial
import json_serial
from random import randint

import openhtf as htf
from openhtf.output.callbacks import json_factory
from openhtf.output.servers import station_server
from openhtf.output.web_gui import web_launcher
from openhtf.plugs import user_input
from openhtf.plugs.user_input import UserInput, PromptType, SecondaryOptionOccured
from openhtf.core.test_record import PhaseOutcome, Outcome
from openhtf.plugs import BasePlug

from spintop_openhtf import TestPlan, PhaseResult, conf
from spintop_openhtf.util.markdown import markdown

from enum import Enum
# Common test files
import UARTcmd
import json_serial
# SOM Board test files
import uBootLoadFile
# Chamber files
import Camera
# MIC board test files
import micstest


class TestTypes(Enum):
    LED_BOARD_TEST = 'LedBoardTest'
    LEDRING_BOARD_TEST = 'LedRingBoardTest'
    MIC_BOARD_TEST = 'MicBoardTest'
    SOM_BOARD_TEST = 'SomBoardTest'
    BACKPLANE_BOARD_TEST = 'BackplaneBoardTest'
    BT_CHAMBER_TEST = 'BTChamberTest'
    NONE = 'None'

    def __str__(self):
        return self.value


# ----------------MIC Board-------------------------------------------------
def mic_board_test():
    # Yellow LED init
    os.system('echo 25 > /sys/class/gpio/export')
    time.sleep(0.1)
    os.system('echo out > /sys/class/gpio/gpio25/direction')
    # Red LED init
    os.system('echo 24 > /sys/class/gpio/export')
    time.sleep(0.1)
    os.system('echo out > /sys/class/gpio/gpio24/direction')
    # Green LED init
    os.system('echo 22 > /sys/class/gpio/export')
    time.sleep(0.1)
    os.system('echo out > /sys/class/gpio/gpio22/direction')
    # Button init
    os.system('echo 27 > /sys/class/gpio/export')
    time.sleep(0.1)
    os.system('echo in > /sys/class/gpio/gpio27/direction')
    serial_port = json_serial.JsonSerialPort()
    jig_status = serial_port.full_one_cycle_with_key({"Cmd": "Ping"})
    if jig_status == 'ok':
        UARTcmd.GreenLED('ON')
        UARTcmd.RedLED('OFF')
    else:
        UARTcmd.GreenLED('OFF')
        UARTcmd.RedLED('ON')

    TestName = ' MicrophonesBoardTest'
    os.system('mkdir ' + os.getcwd() + '/' + TestName)
    mic_board = TestPlan(TestName, True)
    testresults = [
        'echo \"\e[1m  - 5V:      Not Start\e[0m"\n',
        'echo \"\e[1m  - 3.3V:    Not Start\e[0m"\n',
        'echo \"\e[1m  - 3.3Vmic: Not Start\e[0m"\n',
        'echo \"\e[1m- Encoder Test:        Not Start\e[0m"\n',
        'echo \"\e[1m- Light Sensor Test:   Not Start\e[0m"\n',
        'echo \"\e[1m- \"Mute\" Button Test:  Not Start\e[0m"\n',
        'echo \"\e[1m- \"Alice\" Button Test: Not Start\e[0m"\n',
        'echo \"\e[1m- Microphones Test:    Not Start\e[0m"\n'
    ]
    teststatus = "NOT STARTED"
    HERE = os.path.abspath(os.path.dirname(__file__))
    FORM_LAYOUT = {
        'schema': {
            'title': "DUT ID",
            'type': "object",
            'required': ["DUT ID"],
            'properties': {
                'DUT ID': {
                    'type': "string",
                    'title': "Enter DUT ID"
                },
            }
        },
        'layout': [
            {
                "type": "help",
                "helpvalue": markdown("""
#Microphones Board Testing

<img src="%s" width="300px" />

""" % mic_board.image_url(os.path.join(HERE, 'MIC.jpg')))
            },
            "DUT ID",
        ]
    }

    class GreetPlug(UserInput):
        def prompt_tester_information(self):
            self.__response = self.prompt_form(FORM_LAYOUT)
            return self.__response

        def greet_button(self):
            self.prompt("""
# Press button to start the test 

DUT id will be gererated automatically from income data

""".format())

    @mic_board.trigger('DUT ID')
    @mic_board.plug(greet=GreetPlug)
    # change ID pattern
    @htf.measures(htf.Measurement('DUT_ID').with_validator(lambda devidin: re.match(r"^YMAC200531{1}", devidin)))
    def DUTID(test, greet):
        """Press button to start the test
# Press button to start the test

DUT id will be gererated automatically from income data
       """
        # greet.greet_button()
        test.dut_id = 'YMAC200531' + str(randint(10000, 99999))
        UARTcmd.YellowLED('ON')
        pressbutton = 'none'
        while pressbutton != '0\n':
            command = ['cat', '/sys/class/gpio/gpio27/value']
            pipopen = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            pressbutton = pipopen.stdout.read()
            pressbutton = pressbutton.decode(encoding='utf-8')
        UARTcmd.YellowLED('OFF')
        devidin = test.dut_id
        test.measurements.DUT_ID = devidin

    @mic_board.testcase('Power On')
    @htf.measures(htf.Measurement('PowerOn').with_validator(lambda PwrOn: PwrOn == "ok"))
    def PowerOn(test):
        serial_port = json_serial.JsonSerialPort()
        PwrOn = serial_port.full_one_cycle_with_key({"Cmd": "PwrOn"})
        test.measurements.PowerOn = PwrOn

    # @mic_board.testcase('STM32 Status')
    # @mic_board.plug(greet=GreetPlug)
    # @htf.measures(htf.Measurement('STM32_Status').with_validator(lambda MICSTMPingMeas: MICSTMPingMeas==0))
    # def MICSTMPing(test, greet):
    # """Check STM32 status"""
    # MICSTMPingMeas = UARTcmd.cmdget("Ping")
    # test.measurements.STM32_Status = MICSTMPingMeas
    # #if MICSTMPingMeas!=0:
    # #    raise ValueError('No STM32 connection')

    @mic_board.testcase('Power circuit 5V')
    @mic_board.plug(greet=GreetPlug)
    @htf.measures(htf.Measurement('MIC5V_measurement').in_range(4800, 5200, type=int))
    def MIC5V(test, greet):
        """Voltage measurement in the 5V power circuit"""
        test.logger.info('Measure 5V')
        serial_port = json_serial.JsonSerialPort()
        MIC5Vmeas = serial_port.full_one_cycle_with_key({"Cmd": "Get", "Params": ["5vV"]}, "5vV")
        nonlocal testresults
        if isinstance(MIC5Vmeas, int) and 4800 < MIC5Vmeas < 5200:
            code = 32
        else:
            code = 31
        testresults[0] = 'echo \"\e[' + str(code) + ';1m  - 5V:      ' + str(MIC5Vmeas) + '\e[0m"\n'
        test.measurements.MIC5V_measurement = MIC5Vmeas

    @mic_board.testcase('Power circuit 3.3V')
    @mic_board.plug(greet=GreetPlug)
    @htf.measures(htf.Measurement('MIC3V3_measurement').in_range(3100, 3500, type=int))
    def MIC3V3(test, greet):
        """Voltage measurement in the 3.3V power circuit"""
        test.logger.info('Measure 3V3')
        serial_port = json_serial.JsonSerialPort()
        MIC3V3meas = serial_port.full_one_cycle_with_key({"Cmd": "Get", "Params": ["3v3V"]}, "3v3V")
        nonlocal testresults
        if isinstance(MIC3V3meas, int) and 3100 < MIC3V3meas > 3500:
            code = 32
        else:
            code = 31
        testresults[1] = ('echo \"\e[' + str(code) + ';1m  - 3.3V:    ' + str(MIC3V3meas) + '\e[0m"\n')
        test.measurements.MIC3V3_measurement = MIC3V3meas

    @mic_board.testcase('Power circuit 3.3V intrernal')
    @mic_board.plug(greet=GreetPlug)
    @htf.measures(htf.Measurement('MIC3V3mic_measurement').in_range(3100, 3500, type=int))
    def MIC3V3mic(test, greet):
        """Voltage measurement in the 3.3V internal power circuit"""
        test.logger.info('Measure 3V3mic')
        serial_port = json_serial.JsonSerialPort()
        MIC3V3micmeas = serial_port.full_one_cycle_with_key({"Cmd": "Get", "Params": ["3v3InV"]}, "3v3InV")
        nonlocal testresults
        if isinstance(MIC3V3micmeas, int) and 3100 < MIC3V3micmeas < 3500:
            code = 32
        else:
            code = 31
        testresults[2] = ('echo \"\e[' + str(code) + ';1m  - 3.3Vmic: ' + str(MIC3V3micmeas) + '\e[0m"\n')
        test.measurements.MIC3V3mic_measurement = MIC3V3micmeas

    @mic_board.testcase('Encoder Test')
    @htf.measures(htf.Measurement('Encoder_test').with_validator(lambda MICencoderTestmeas: MICencoderTestmeas == 'ok'))
    def MICencoderTest(test):
        serial_port = json_serial.JsonSerialPort()
        MICencoderTestmeas = serial_port.full_one_cycle_with_key({"Cmd": "TestEncoder"})
        nonlocal testresults
        if MICencoderTestmeas == 'ok':
            testresults[3] = ('echo \"\e[32;1m- Encoder Test:      Pass\e[0m"\n')
        else:
            testresults[3] = ('echo \"\e[31;1m- Encoder Test:      Fail\e[0m"\n')
        test.measurements.Encoder_test = MICencoderTestmeas

    @mic_board.testcase('Light Sensor Test')
    @htf.measures(htf.Measurement('LightSensorTest').with_validator(lambda MIClightSensorTestmeas:
                                                                    MIClightSensorTestmeas == 'ok'))
    def MIClightSensorTest(test):
        serial_port = json_serial.JsonSerialPort()
        MIClightSensorTestmeas = serial_port.full_one_cycle_with_key({"Cmd": "TestLightSns"})
        nonlocal testresults
        if MIClightSensorTestmeas == 'ok':
            testresults[4] = ('echo \"\e[32;1m- Light Sensor Test: Pass\e[0m"\n')
        else:
            testresults[4] = ('echo \"\e[31;1m- Light Sensor Test: Fail\e[0m"\n')
        test.measurements.LightSensorTest = MIClightSensorTestmeas

    @mic_board.testcase('\'Mute\' Button Test')
    @htf.measures(htf.Measurement('MuteButtonTest').with_validator(
        lambda MICMuteButtonTestmeas: MICMuteButtonTestmeas == 'Button \"Mute\" is OK'))
    def MICMuteButtonTest(test):
        # serial_port = json_serial.JsonSerialPort()
        MICMuteButtonTestmeas = UARTcmd.buttontest()
        nonlocal testresults
        index = MICMuteButtonTestmeas.find('{"Result": "Ok"}')
        if index != -1:
            Mutepush = re.findall('{"Buttons":"Changed","LedSense":1,"MicEn":0,"MicEnN":1}\r\n'
                                  '{"Buttons":"Changed","LedSense":0,"MicEn":1,"MicEnN":0}', MICMuteButtonTestmeas)
            if len(Mutepush) > 0:
                MICMuteButtonTestmeas = 'Button \"Mute\" is OK'
                testresults[5] = ('echo \"\e[32;1m- \"Mute\" Button Test:  Pass\e[0m"\n')
            elif len(Mutepush) == 0:
                MICMuteButtonTestmeas = 'Button \"Mute\" does not response correctly'
                testresults[5] = ('echo \"\e[31;1m- \"Mute\" Button Test:  Fail\e[0m"\n')
        else:
            MICMuteButtonTestmeas = "No STM response"
            testresults[5] = ('echo \"\e[31;1m- \"Mute\" Button Test:  Fail\e[0m"\n')

        test.measurements.MuteButtonTest = MICMuteButtonTestmeas

    @mic_board.testcase('\'Alice\' Button Test')
    @htf.measures(htf.Measurement('AliceButtonTest').with_validator(
        lambda MICAliceButtonTestmeas: MICAliceButtonTestmeas == 'Button \"Alice\" is OK'))
    def MICAliceButtonTest(test):
        MICAliceButtonTestmeas = UARTcmd.buttontest()
        nonlocal testresults
        Alicepush = re.findall('{"Buttons":"Changed","KeyFunc":0}\r\n{"Buttons":"Changed","KeyFunc":1}',
                               MICAliceButtonTestmeas)
        if len(Alicepush) > 0:
            MICAliceButtonTestmeas = 'Button \"Alice\" is OK'
            testresults[6] = ('echo \"\e[32;1m- \"Alice\" Button Test: Pass\e[0m"\n')
        else:
            MICAliceButtonTestmeas = 'Button \"Alice\" does not response correctly'
            testresults[6] = ('echo \"\e[31;1m- \"Alice\" Button Test: Fail\e[0m"\n')

        test.measurements.AliceButtonTest = MICAliceButtonTestmeas

    @mic_board.testcase('Sound Test')
    @mic_board.plug(greet=GreetPlug)
    @htf.TestPhase(timeout_s=60 * 60)
    @htf.measures(htf.Measurement('SoundTest').with_validator(lambda MICsoundTestmeas: MICsoundTestmeas[0] == 'OK'))
    def MICsoundTest(test, greet):
        """Microphone Recording Analysis"""
        test.logger.info('Start microphones test')
        teststorage = os.getcwd() + '/' + TestName + '/' + TestName + '.time' + \
                      str(test.test_record.start_time_millis) + '.id' + test.dut_id
        testwav = 'id' + test.dut_id + 'time' + str(test.test_record.start_time_millis) + '.wav'
        os.makedirs(teststorage)
        command = ['arecord', '-l']
        pipopen = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        bashstr = str(pipopen.stdout.read())
        index = bashstr.find('card')
        if index != -1:
            card = re.findall(r'(\d+)', bashstr)
            UARTcmd.cmdget({"Cmd": "TestMics", "a": 300}, responseFlag=False)
            recordstr = 'arecord -D hw:%s,0 -c 8 -f S16_LE -r 16000 -d 12 ' % card[0]
            recordstr = recordstr + teststorage + '/' + testwav
            os.system(recordstr)
        examplepath = '/home/yandex/elenchus/hwtest/Example.wav'
        micfilepath = teststorage + '/'
        filepath = micfilepath + testwav

        if os.path.isfile(filepath):
            if os.path.isfile(examplepath):
                MICsoundTestmeas = micstest.process_file(teststorage + '/', testwav)
                test.logger.info(MICsoundTestmeas[1])
            else:
                MICsoundTestmeas = ['No example file']
                test.logger.error(MICsoundTestmeas[0])
        else:
            MICsoundTestmeas = ['No test file']
            test.logger.error(MICsoundTestmeas[0])

        nonlocal testresults
        nonlocal teststatus
        teststatus = test.test_record.outcome
        if MICsoundTestmeas[0] == 'OK':
            testresults[7] = ('echo \"\e[32;1m- Microphones Test:  Pass\e[0m"\n')
        else:
            testresults[7] = ('echo \"\e[31;1m- Microphones Test:  Fail\e[0m"\n')
        test.measurements.SoundTest = MICsoundTestmeas

    # @htf.TestPhase(run_if=lambda: False)
    @mic_board.testcase('DUT Power Off')
    @htf.plugs.plug(prompts=UserInput)
    @htf.measures(htf.Measurement('PowerOFF').with_validator(lambda PowerOffresp: PowerOffresp == 'ok'))
    def DUTPowerOff(test, prompts):
        serial_port = json_serial.JsonSerialPort()
        PowerOffresp = serial_port.full_one_cycle_with_key({"Cmd": "PwrOff"})
        test.measurements.PowerOFF = PowerOffresp
        nonlocal testresults
        outcomes = [p.outcome for p in test.test_record.phases]
        # res=[r.measured_value for r in test.test_record]
        os.system('echo 25 > /sys/class/gpio/export')
        os.system('echo out > /sys/class/gpio/gpio25/direction')
        os.system('echo 0 > /sys/class/gpio/gpio25/value')
        if outcomes[2] == PhaseOutcome.PASS and outcomes[3] == PhaseOutcome.PASS and outcomes[4] == PhaseOutcome.PASS:
            powertest = 32
        else:
            powertest = 31
        test.logger.info("""DUT Power Off""")
        os.system('echo "\e[36;1mDUT Power Off\e[0m"')
        if PhaseOutcome.FAIL in outcomes:
            os.system('echo "\e[36;1mTest Status:\e[0m" "\e[31;1mFAIL\e[0m"')
            teststatus = 'DUT ID:' + test.dut_id + ' test status: <p><font color=red>FAIL'
        elif PhaseOutcome.PASS in outcomes:
            os.system('echo "\e[36;1mTest Status:\e[0m" "\e[32;1mPASS\e[0m"')
            teststatus = 'DUT ID:' + test.dut_id + ' test status: <p><font color=green>PASS'
        os.system('echo "\e[' + str(powertest) + ';1m- Power measurments:\e[0m"')
        os.system(testresults[0])
        os.system(testresults[1])
        os.system(testresults[2])
        os.system(testresults[3])
        os.system(testresults[4])
        os.system(testresults[5])
        os.system(testresults[6])
        os.system(testresults[7])
        # os.system('echo "\e[36;1m'+str(test.test_record.outcome)+'\e[0m"')

        # my_file=open("testphase.txt", "w")
        # resprint=''.join(map(str, test.test_record.phases))
        # resprint=''.join(map(str, res))
        # my_file.write(resprint)
        # my_file.close()
        if PhaseOutcome.ERROR in outcomes or PhaseOutcome.FAIL in outcomes:
            prompts.prompt("""## """ + teststatus, prompt_type=PromptType.OKAY)
        serial_port = json_serial.JsonSerialPort()
        jig_status = serial_port.full_one_cycle_with_key({"Cmd": "Ping"})
        print(jig_status)
        if jig_status == 'ok':
            UARTcmd.GreenLED('ON')
            UARTcmd.RedLED('OFF')
        else:
            UARTcmd.GreenLED('OFF')
            UARTcmd.RedLED('ON')

    mic_board.run()
    os.system('echo 25 > /sys/class/gpio/unexport')
    os.system('echo 24 > /sys/class/gpio/unexport')
    os.system('echo 22 > /sys/class/gpio/unexport')
    os.system('echo 27 > /sys/class/gpio/unexport')


# ----------------LED Screen Board-------------------------------------------------

def led_board_test():
    led_board = TestPlan('LED Screen Board Test')
    testresults = [
        'echo \"\e[1m- 20V: Not Start\e[0m"\n',
        'echo \"\e[1m- 5V:  Not Start\e[0m"\n',
        'echo \"\e[1m- STM32 Programming:   Not Start\e[0m"\n',
        'echo \"\e[1m- LEDs Off:            Not Start\e[0m"\n',
        'echo \"\e[1m- LEDs 50% intensity:  Not Start\e[0m"\n',
        'echo \"\e[1m- LEDs 100% intensity: Not Start\e[0m"\n',
    ]
    HERE = os.path.abspath(os.path.dirname(__file__))
    FORM_LAYOUT = {
        'schema': {
            'title': "DUT ID",
            'type': "object",
            'required': ["DUT ID"],
            'properties': {
                'DUT ID': {
                    'type': "string",
                    'title': "Enter DUT ID"
                },
            }
        },
        'layout': [
            {
                "type": "help",
                "helpvalue": markdown("""
#LED Screen Board Testing

<img src="%s" width="300px" />

""" % led_board.image_url(os.path.join(HERE, 'MIC.jpg'))
                                      )
            },
            "DUT ID",
        ]
    }

    class GreetPlug(UserInput):
        def prompt_tester_information(self):
            self.__response = self.prompt_form(FORM_LAYOUT)
            return self.__response

    @led_board.trigger('Get DUT ID')
    @led_board.plug(greet=GreetPlug)
    @htf.measures(
        htf.Measurement('DUT_ID').with_validator(lambda devidin: re.match(r"^3160{1}", devidin)))  # chage ID pattern
    def hello_world(test, greet):
        """Scan DUT ID and start the test"""
        response = greet.prompt_tester_information()
        test.dut_id = response['DUT ID']
        devidin = test.dut_id
        test.measurements.DUT_ID = devidin

    @led_board.testcase('Power circuit 20V')
    @led_board.plug(greet=GreetPlug)
    @htf.measures(htf.Measurement('LED20V_measurement').with_validator(
        lambda MIC20Vmeas: isinstance(MIC20Vmeas, int) and MIC20Vmeas < 21000 and MIC20Vmeas > 19000))
    def LED20V(test, greet):
        """Voltage measurement in the 20V power circuit"""
        test.logger.info('Measure 20V')
        MIC20Vmeas = UARTcmd.cmdget("20v")
        nonlocal testresults
        if isinstance(MIC20Vmeas, int) and MIC20Vmeas < 21000 and MIC20Vmeas > 19000:
            code = 32
        else:
            code = 31
        testresults[0] = 'echo \"\e[' + str(code) + ';1m  - 20V: ' + str(MIC20Vmeas) + '\e[0m"\n'
        test.measurements.LED20V_measurement = MIC20Vmeas

    @led_board.testcase('Power circuit 5V')
    @led_board.plug(greet=GreetPlug)
    @htf.measures(htf.Measurement('LED5V_measurement').with_validator(
        lambda MIC5Vmeas: isinstance(MIC5Vmeas, int) and MIC5Vmeas < 5200 and MIC5Vmeas > 4800))
    def LED5V(test, greet):
        """Voltage measurement in the 5V power circuit"""
        test.logger.info('Measure 5V')
        MIC5Vmeas = UARTcmd.cmdget("5v")
        nonlocal testresults
        if isinstance(MIC5Vmeas, int) and MIC5Vmeas < 5200 and MIC5Vmeas > 4800:
            code = 32
        else:
            code = 31
        testresults[1] = 'echo \"\e[' + str(code) + ';1m  - 5V:  ' + str(MIC5Vmeas) + '\e[0m"\n'
        test.measurements.LED5V_measurement = MIC5Vmeas

    @led_board.testcase('STM32 Programming')
    @htf.measures(htf.Measurement('STM32_Programming').with_validator(lambda MICSTMProg: MICSTMProg == 0))
    def MICSTMPing(test):
        MICSTMProg = UARTcmd.cmdget("Ping")
        test.measurements.STM32_Programming = MICSTMProg
        if MICSTMProg != 0:
            testresults[2] = 'echo \"\e[32;1m- STM32 Programming: ' + str(MICSTMProg) + '\e[0m"\n'
        else:
            testresults[2] = 'echo \"\e[31;1m- STM32 Programming: ' + str(MICSTMProg) + '\e[0m"\n'

    @led_board.testcase('LED Screen Off Test')
    @led_board.plug(greet=GreetPlug)
    @htf.measures(htf.Measurement('LEDScreenOffTest'))  # dummy
    def LEDScreenOffTest(test, greet):
        """Cheching the status when all the LEDs are off"""
        nonlocal testresults
        photoname = 'LEDoff' + test.test_record.dut_id + '.jpeg'
        flag = Camera.LEDScreenPhoto(photoname)
        test.attach_from_file(
            os.path.join(os.path.dirname(__file__), '/home/yandex/elenchus/hwtest/LEDPhoto/%s' % photoname))
        test.measurements.LEDScreenOffTest = photoname
        if flag == True:
            testresults[3] = 'echo \"\e[32;1m- LED Screen Off Test: ' + photoname + '\e[0m"\n'
        else:
            testresults[3] = 'echo \"\e[31;1m- LED Screen Off Test: FAIL\e[0m"\n'

    @led_board.testcase('LED Screen 50% intensity Test')
    @led_board.plug(greet=GreetPlug)
    @htf.measures(htf.Measurement('LEDScreenHalfIntensityTest'))  # dummy
    def LEDScreenOffTest(test, greet):
        """Cheching the status when all the LEDs are turned on at 50% intensity"""
        nonlocal testresults
        photoname = 'LEDhalf' + test.test_record.dut_id + '.jpeg'
        flag = Camera.LEDScreenPhoto(photoname)
        if flag == True:
            testresults[4] = 'echo \"\e[32;1m- LED Screen Off Test: ' + photoname + '\e[0m"\n'
        else:
            testresults[4] = 'echo \"\e[31;1m- LED Screen Off Test: FAIL\e[0m"\n'
        test.attach_from_file(
            os.path.join(os.path.dirname(__file__), '/home/yandex/elenchus/hwtest/LEDPhoto/%s' % photoname))
        test.measurements.LEDScreenHalfIntensityTest = photoname

    @led_board.testcase('LED Screen 100% intesity Test')
    @led_board.plug(greet=GreetPlug)
    @htf.measures(htf.Measurement('LEDScreenFullIntensityTest'))  # dummy
    def LEDScreenOffTest(test, greet):
        """Cheching the status when all the LEDs are turned on at 100% intensity"""
        nonlocal testresults
        photoname = 'LEDon' + test.test_record.dut_id + '.jpeg'
        flag = Camera.LEDScreenPhoto(photoname)
        if flag == True:
            testresults[5] = 'echo \"\e[32;1m- LED Screen Off Test: ' + photoname + '\e[0m"\n'
        else:
            testresults[5] = 'echo \"\e[31;1m- LED Screen Off Test: FAIL\e[0m"\n'
        test.attach_from_file(
            os.path.join(os.path.dirname(__file__), '/home/yandex/elenchus/hwtest/LEDPhoto/%s' % photoname))
        test.measurements.LEDScreenFullIntensityTest = photoname

    @led_board.testcase('DUT Power Off')
    @htf.plugs.plug(prompts=UserInput)
    def DUTPowerOff(test, prompts):
        nonlocal testresults
        outcomes = [p.outcome for p in test.test_record.phases]
        if outcomes[1] == PhaseOutcome.PASS and outcomes[2] == PhaseOutcome.PASS:
            powertest = 32
        else:
            powertest = 31
        test.logger.info("""DUT Power Off""")
        os.system('echo "\e[36;1mDUT Power Off\e[0m"')
        if PhaseOutcome.FAIL in outcomes:
            os.system('echo "\e[36;1mTest Status:\e[0m" "\e[31;1mFAIL\e[0m"')
            teststatus = 'DUT ID' + test.dut_id + ' test status: <p><font color=red>FAIL'
        elif PhaseOutcome.PASS in outcomes:
            os.system('echo "\e[36;1mTest Status:\e[0m" "\e[32;1mFAIL\e[0m"')
            teststatus = 'DUT ID' + test.dut_id + ' test status: <p><font color=green>PASS'
        os.system('echo "\e[' + str(powertest) + ';1m- Power measurments:\e[0m"')
        os.system(testresults[0])
        os.system(testresults[1])
        os.system(testresults[2])
        os.system(testresults[3])
        os.system(testresults[4])
        os.system(testresults[5])

        prompts.prompt("""## """ + teststatus, prompt_type=PromptType.OKAY)

    led_board.run()


# ----------------LED Ring Board-------------------------------------------------
def ledring_board_test():
    ledring_board = TestPlan('LED Ring Board Test')
    testresults = [
        'echo \"\e[1m- 5V:   Not Start\e[0m"\n',
        'echo \"\e[1m- 3.3V: Not Start\e[0m"\n',
        'echo \"\e[1m- LEDs Off:            Not Start\e[0m"\n',
        'echo \"\e[1m- LEDs Red 50% intensity:    Not Start\e[0m"\n',
        'echo \"\e[1m- LEDs Green 50% intensity:  Not Start\e[0m"\n',
        'echo \"\e[1m- LEDs Blue 50% intensity:   Not Start\e[0m"\n',
        'echo \"\e[1m- LEDs Red 100% intensity:   Not Start\e[0m"\n',
        'echo \"\e[1m- LEDs Green 100% intensity: Not Start\e[0m"\n',
        'echo \"\e[1m- LEDs Blue 100% intensity:  Not Start\e[0m"\n',
        'echo \"\e[1m- LEDs 100% intensity:       Not Start\e[0m"\n',
    ]
    HERE = os.path.abspath(os.path.dirname(__file__))
    FORM_LAYOUT = {
        'schema': {
            'title': "DUT ID",
            'type': "object",
            'required': ["DUT ID"],
            'properties': {
                'DUT ID': {
                    'type': "string",
                    'title': "Enter DUT ID"
                },
            }
        },
        'layout': [
            {
                "type": "help",
                "helpvalue": markdown("""
#LED Ring Board Testing

<img src="%s" width="300px" />

""" % mic_board.image_url(os.path.join(HERE, 'MIC.jpg'))
                                      )
            },
            "DUT ID",
        ]
    }

    class GreetPlug(UserInput):
        def prompt_tester_information(self):
            self.__response = self.prompt_form(FORM_LAYOUT)
            return self.__response

    @ledring_board.trigger('Get DUT ID')
    @ledring_board.plug(greet=GreetPlug)
    @htf.measures(
        htf.Measurement('DUT_ID').with_validator(lambda devidin: re.match(r"^3160{1}", devidin)))  # chage ID pattern
    def hello_world(test, greet):
        """Scan DUT ID and start the test"""
        response = greet.prompt_tester_information()
        test.dut_id = response['DUT ID']
        devidin = test.dut_id
        test.measurements.DUT_ID = devidin

    @ledring_board.testcase('STM32 Status')
    @ledring_board.plug(greet=GreetPlug)
    @htf.measures(htf.Measurement('STM32_Status').with_validator(lambda STMPing: STMPing == 0))
    def MICSTMPing(test, greet):
        """Check STM32 status"""
        STMPing = UARTcmd.cmdget("Ping")
        test.measurements.STM32_Status = STMPing
        # if MICSTMPingMeas!=0:
        #    raise ValueError('No STM32 connection')

    @ledring_board.testcase('Power circuit 5V')
    @ledring_board.plug(greet=GreetPlug)
    @htf.measures(htf.Measurement('LEDRing5V_measurement').with_validator(
        lambda LR5Vmeas: isinstance(LR5Vmeas, int) and LR5Vmeas < 5200 and LR5Vmeas > 4800))
    def LEDRing5V(test, greet):
        """Voltage measurement in the 5V power circuit"""
        test.logger.info('Measure 5V')
        LR5Vmeas = UARTcmd.cmdget("5v")
        nonlocal testresults
        if isinstance(LR5Vmeas, int) and LR5Vmeas < 5200 and LR5Vmeas > 4800:
            code = 32
        else:
            code = 31
        testresults[0] = 'echo \"\e[' + str(code) + ';1m  - 5V:  ' + str(LR5Vmeas) + '\e[0m"\n'
        test.measurements.LEDRing5V_measurement = LR5Vmeas

    @ledring_board.testcase('Power circuit 3.3V')
    @ledring_board.plug(greet=GreetPlug)
    @htf.measures(htf.Measurement('LEDRing3V3_measurement').with_validator(
        lambda LR3V3meas: isinstance(LR3V3meas, int) and LR3V3meas < 3500 and LR3V3meas > 3100))
    def LEDRing3V3(test, greet):
        """Voltage measurement in the 3.3V power circuit"""
        test.logger.info('Measure 3.3V')
        LR3V3meas = UARTcmd.cmdget("3v3")
        nonlocal testresults
        if isinstance(LR3V3meas, int) and LR3V3meas < 3500 and LR3V3meas > 3100:
            code = 32
        else:
            code = 31
        testresults[1] = 'echo \"\e[' + str(code) + ';1m  - 3.3V: ' + str(LR3V3meas) + '\e[0m"\n'
        test.measurements.LEDRing3V3_measurement = LR3V3meas

    @ledring_board.testcase('LED Ring Off Test')
    @ledring_board.plug(greet=GreetPlug)
    @htf.measures(htf.Measurement('LEDRingOffTest'))  # dummy
    def LEDRingOffTest(test, greet):
        """Cheching the status when all the LEDs are off"""
        nonlocal testresults
        photoname = 'LEDRingoff' + test.test_record.dut_id + '.jpeg'
        flag = Camera.LEDScreenPhoto(photoname)
        # if flag==True:
        test.attach_from_file(
            os.path.join(os.path.dirname(__file__), '/home/yandex/elenchus/hwtest/LEDRingPhoto/%s' % photoname))
        test.measurements.LEDRingOffTest = photoname

    @ledring_board.testcase('LEDRing Red 50% intensity Test')
    @ledring_board.plug(greet=GreetPlug)
    @htf.measures(htf.Measurement('LEDRingRedHalfIntensityTest'))  # dummy
    def LEDRingRedHalfIntensityTest(test, greet):
        """Cheching the status when all the red LEDs are turned on at 50% intensity"""
        nonlocal testresults
        photoname = 'LEDRedHalf' + test.test_record.dut_id + '.jpeg'
        flag = Camera.LEDScreenPhoto(photoname)
        # if flag==True:
        test.attach_from_file(
            os.path.join(os.path.dirname(__file__), '/home/yandex/elenchus/hwtest/LEDRingPhoto/%s' % photoname))
        test.measurements.LEDRingRedHalfIntensityTest = photoname

    @ledring_board.testcase('LEDRing Green 50% intensity Test')
    @ledring_board.plug(greet=GreetPlug)
    @htf.measures(htf.Measurement('LEDRingGreenHalfIntensityTest'))  # dummy
    def LEDRingGreenHalfIntensityTest(test, greet):
        """Cheching the status when all the green LEDs are turned on at 50% intensity"""
        nonlocal testresults
        photoname = 'LEDGreenHalf' + test.test_record.dut_id + '.jpeg'
        flag = Camera.LEDScreenPhoto(photoname)
        # if flag==True:
        test.attach_from_file(
            os.path.join(os.path.dirname(__file__), '/home/yandex/elenchus/hwtest/LEDRingPhoto/%s' % photoname))
        test.measurements.LEDRingGreenHalfIntensityTest = photoname

    @ledring_board.testcase('LEDRing Blue 50% intensity Test')
    @ledring_board.plug(greet=GreetPlug)
    @htf.measures(htf.Measurement('LEDRingBlueHalfIntensityTest'))  # dummy
    def LEDRingBlueHalfIntensityTest(test, greet):
        """Cheching the status when all the blue LEDs are turned on at 50% intensity"""
        nonlocal testresults
        photoname = 'LEDBlueHalf' + test.test_record.dut_id + '.jpeg'
        flag = Camera.LEDScreenPhoto(photoname)
        # if flag==True:
        test.attach_from_file(
            os.path.join(os.path.dirname(__file__), '/home/yandex/elenchus/hwtest/LEDRingPhoto/%s' % photoname))
        test.measurements.LEDRingBlueHalfIntensityTest = photoname

    @ledring_board.testcase('LEDRing Red 100% intensity Test')
    @ledring_board.plug(greet=GreetPlug)
    @htf.measures(htf.Measurement('LEDRingRedFullIntensityTest'))  # dummy
    def LEDRingRedFullIntensityTest(test, greet):
        """Cheching the status when all the red LEDs are turned on at 100% intensity"""
        nonlocal testresults
        photoname = 'LEDRedFull' + test.test_record.dut_id + '.jpeg'
        flag = Camera.LEDScreenPhoto(photoname)
        # if flag==True:
        test.attach_from_file(
            os.path.join(os.path.dirname(__file__), '/home/yandex/elenchus/hwtest/LEDRingPhoto/%s' % photoname))
        test.measurements.LEDRingRedFullIntensityTest = photoname

    @ledring_board.testcase('LEDRing Green 100% intensity Test')
    @ledring_board.plug(greet=GreetPlug)
    @htf.measures(htf.Measurement('LEDRingGreenFullIntensityTest'))  # dummy
    def LEDRingGreenFullIntensityTest(test, greet):
        """Cheching the status when all the green LEDs are turned on at 100% intensity"""
        nonlocal testresults
        photoname = 'LEDGreenFull' + test.test_record.dut_id + '.jpeg'
        flag = Camera.LEDScreenPhoto(photoname)
        # if flag==True:
        test.attach_from_file(
            os.path.join(os.path.dirname(__file__), '/home/yandex/elenchus/hwtest/LEDRingPhoto/%s' % photoname))
        test.measurements.LEDRingGreenFullIntensityTest = photoname

    @ledring_board.testcase('LEDRing Blue 100% intensity Test')
    @ledring_board.plug(greet=GreetPlug)
    @htf.measures(htf.Measurement('LEDRingBlueFullIntensityTest'))  # dummy
    def LEDRingBlueFullIntensityTest(test, greet):
        """Cheching the status when all the blue LEDs are turned on at 100% intensity"""
        nonlocal testresults
        photoname = 'LEDBlueFull' + test.test_record.dut_id + '.jpeg'
        flag = Camera.LEDScreenPhoto(photoname)
        # if flag==True:
        test.attach_from_file(
            os.path.join(os.path.dirname(__file__), '/home/yandex/elenchus/hwtest/LEDRingPhoto/%s' % photoname))
        test.measurements.LEDRingBlueFullIntensityTest = photoname

    @ledring_board.testcase('LED Ring 100% intesity Test')
    @ledring_board.plug(greet=GreetPlug)
    @htf.measures(htf.Measurement('LEDRingFullIntensityTest'))  # dummy
    def LEDRingONTest(test, greet):
        """Cheching the status when all the LEDs are turned on at 100% intensity"""
        nonlocal testresults
        photoname = 'LEDon' + test.test_record.dut_id + '.jpeg'
        flag = Camera.LEDScreenPhoto(photoname)
        # if flag==True:
        test.attach_from_file(
            os.path.join(os.path.dirname(__file__), '/home/yandex/elenchus/hwtest/LEDRingPhoto/%s' % photoname))
        test.measurements.LEDRingFullIntensityTest = photoname

    @ledring_board.testcase('DUT Power Off')
    @htf.plugs.plug(prompts=UserInput)
    def DUTPowerOff(test, prompts):
        nonlocal testresults
        outcomes = [p.outcome for p in test.test_record.phases]
        if outcomes[2] == PhaseOutcome.PASS and outcomes[3] == PhaseOutcome.PASS:
            powertest = 32
        else:
            powertest = 31
        test.logger.info("""DUT Power Off""")
        os.system('echo "\e[36;1mDUT Power Off\e[0m"')
        if PhaseOutcome.FAIL in outcomes:
            os.system('echo "\e[31;1mTest Status:\e[0m" "\e[31;1mFAIL\e[0m"')
            teststatus = 'DUT ID' + test.dut_id + ' test status: <p><font color=red>FAIL'
        elif PhaseOutcome.PASS in outcomes:
            os.system('echo "\e[32;1mTest Status:\e[0m" "\e[32;1mFAIL\e[0m"')
            teststatus = 'DUT ID' + test.dut_id + ' test status: <p><font color=green>PASS'
        os.system('echo "\e[' + str(powertest) + ';1m- Power measurments:\e[0m"')
        os.system(testresults[0])
        os.system(testresults[1])
        os.system(testresults[2])
        os.system(testresults[3])
        os.system(testresults[4])
        os.system(testresults[5])
        os.system(testresults[6])
        os.system(testresults[7])
        os.system(testresults[8])
        os.system(testresults[9])

        prompts.prompt("""## """ + teststatus, prompt_type=PromptType.OKAY)

    led_board.run()


# ----------------SOM Board-------------------------------------------------

def som_board_test():
    som_board = TestPlan('LED Ring Board Test')
    testresults = [
        'echo \"\e[1m- 5V:        Not Start\e[0m"\n',
        'echo \"\e[1m- 3.3V:      Not Start\e[0m"\n',
        'echo \"\e[1m- 1.8V:      Not Start\e[0m"\n',
        'echo \"\e[1m- 1.8V EMMC: Not Start\e[0m"\n',
        'echo \"\e[1m- Vdd CPU:   Not Start\e[0m"\n',
        'echo \"\e[1m- VDDEE:     Not Start\e[0m"\n',
        'echo \"\e[1m- 1.5V DDQ:  Not Start\e[0m"\n',
        'echo \"\e[1m- USB Test: Not Start\e[0m"\n',
        'echo \"\e[1m- DDR Test: Not Start\e[0m"\n',
    ]
    HERE = os.path.abspath(os.path.dirname(__file__))
    FORM_LAYOUT = {
        'schema': {
            'title': "DUT ID",
            'type': "object",
            'required': ["DUT ID"],
            'properties': {
                'DUT ID': {
                    'type': "string",
                    'title': "Enter DUT ID"
                },
            }
        },
        'layout': [
            {
                "type": "help",
                "helpvalue": markdown("""
#SOM Board Testing

<img src="%s" width="300px" />

""" % som_board.image_url(os.path.join(HERE, 'MIC.jpg'))
                                      )
            },
            "DUT ID",
        ]
    }

    class GreetPlug(UserInput):
        def prompt_tester_information(self):
            self.__response = self.prompt_form(FORM_LAYOUT)
            return self.__response

    @som_board.trigger('Get DUT ID')
    @som_board.plug(greet=GreetPlug)
    @htf.measures(
        htf.Measurement('DUT_ID').with_validator(lambda devidin: re.match(r"^3160{1}", devidin)))  # chage ID pattern
    def hello_world(test, greet):
        """Scan DUT ID and start the test"""
        response = greet.prompt_tester_information()
        test.dut_id = response['DUT ID']
        devidin = test.dut_id
        test.measurements.DUT_ID = devidin

    @som_board.testcase('STM32 Status')
    @som_board.plug(greet=GreetPlug)
    @htf.measures(htf.Measurement('STM32_Status').with_validator(lambda STMPing: STMPing == 0))
    def SOMSTMPing(test, greet):
        """Check STM32 status"""
        STMPing = UARTcmd.cmdget("Ping")
        test.measurements.STM32_Status = STMPing
        # if MICSTMPingMeas!=0:
        #    raise ValueError('No STM32 connection')

    @som_board.testcase('Power circuit 5V')
    @som_board.plug(greet=GreetPlug)
    @htf.measures(htf.Measurement('SOM5V_measurement').with_validator(
        lambda SOM5Vmeas: isinstance(SOM5Vmeas, int) and SOM5Vmeas < 5200 and SOM5Vmeas > 4800))
    def SOM5V(test, greet):
        """Voltage measurement in the 5V power circuit"""
        test.logger.info('Measure 5V')
        SOM5Vmeas = UARTcmd.cmdget("5v")
        nonlocal testresults
        if isinstance(SOM5Vmeas, int) and SOM5Vmeas < 5200 and SOM5Vmeas > 4800:
            code = 32
        else:
            code = 31
        testresults[0] = 'echo \"\e[' + str(code) + ';1m  - 5V:        ' + str(SOM5Vmeas) + '\e[0m"\n'
        test.measurements.SOM5V_measurement = SOM5Vmeas

    @som_board.testcase('Power circuit 3.3V')
    @som_board.plug(greet=GreetPlug)
    @htf.measures(htf.Measurement('SOM3V3_measurement').with_validator(
        lambda SOM3V3meas: isinstance(SOM3V3meas, int) and SOM3V3meas < 3500 and SOM3V3meas > 3100))
    def SOM3v3(test, greet):
        """Voltage measurement in the 3.3V power circuit"""
        test.logger.info('Measure 3.3V')
        SOM3V3meas = UARTcmd.cmdget("3v3")
        nonlocal testresults
        if isinstance(SOM3V3meas, int) and SOM3V3meas < 3500 and SOM3V3meas > 3100:
            code = 32
        else:
            code = 31
        testresults[1] = 'echo \"\e[' + str(code) + ';1m  - 3.3V:      ' + str(SOM3V3meas) + '\e[0m"\n'
        test.measurements.SOM3V3_measurement = SOM3V3meas

    @som_board.testcase('Power circuit 1.8V')
    @som_board.plug(greet=GreetPlug)
    @htf.measures(htf.Measurement('SOM1V8_measurement').with_validator(
        lambda SOM1V8meas: isinstance(SOM1V8meas, int) and SOM1V8meas < 2000 and SOM1V8meas > 1600))
    def SOM1v8(test, greet):
        """Voltage measurement in the 1.8V power circuit"""
        test.logger.info('Measure 1.8V')
        SOM1V8meas = UARTcmd.cmdget("1v8")
        nonlocal testresults
        if isinstance(SOM1V8meas, int) and SOM1V8meas < 2000 and SOM1V8meas > 1600:
            code = 32
        else:
            code = 31
        testresults[2] = 'echo \"\e[' + str(code) + ';1m  - 1.8V:      ' + str(SOM1V8meas) + '\e[0m"\n'
        test.measurements.SOM1V8_measurement = SOM1V8meas

    @som_board.testcase('Power circuit 1.8V EMMC')
    @som_board.plug(greet=GreetPlug)
    @htf.measures(htf.Measurement('SOM1V8EMMC_measurement').with_validator(
        lambda SOM1V8emmcmeas: isinstance(SOM1V8emmcmeas, int) and SOM1V8emmcmeas < 2000 and SOM1V8emmcmeas > 1600))
    def SOM1v8EMMC(test, greet):
        """Voltage measurement in the 1.8V EMMC power circuit"""
        test.logger.info('Measure 1.8V EMMC')
        SOM1V8emmcmeas = UARTcmd.cmdget("1v8emmc")
        nonlocal testresults
        if isinstance(SOM1V8emmcmeas, int) and SOM1V8meas < 2000 and SOM1V8meas > 1600:
            code = 32
        else:
            code = 31
        testresults[3] = 'echo \"\e[' + str(code) + ';1m  - 1.8V EMMC: ' + str(SOM1V8emmcmeas) + '\e[0m"\n'
        test.measurements.SOM1V8EMMC_measurement = SOM1V8emmcmeas

    @som_board.testcase('Power circuit Vdd CPU')
    @som_board.plug(greet=GreetPlug)
    @htf.measures(htf.Measurement('VDDCPU_measurement').with_validator(
        lambda VDDCPU: isinstance(VDDCPU, int) and VDDCPU < 2000 and VDDCPU > 1600))
    def SOMVDDCPU(test, greet):
        """Voltage measurement in the Vdd CPU power circuit"""
        test.logger.info('Measure VDDCPU')
        VDDCPU = UARTcmd.cmdget("vddcpu")
        nonlocal testresults
        if isinstance(VDDCPU, int) and VDDCPU < 2000 and VDDCPU > 1600:
            code = 32
        else:
            code = 31
        testresults[4] = 'echo \"\e[' + str(code) + ';1m  - Vdd CPU:   ' + str(VDDCPU) + '\e[0m"\n'
        test.measurements.VDDCPU_measurement = VDDCPU

    @som_board.testcase('Power circuit VDDEE')
    @som_board.plug(greet=GreetPlug)
    @htf.measures(htf.Measurement('VDDEE_measurement').with_validator(
        lambda VDDEE: isinstance(VDDEE, int) and VDDEE < 5200 and VDDEE > 4800))
    def SOMVDDEE(test, greet):
        """Voltage measurement in the VDDEE power circuit"""
        test.logger.info('Measure VDDEE')
        VDDEE = UARTcmd.cmdget("vddee")
        nonlocal testresults
        if isinstance(VDDEE, int) and VDDEE < 5200 and VDDEE > 4800:
            code = 32
        else:
            code = 31
        testresults[5] = 'echo \"\e[' + str(code) + ';1m  - VDDEE:     ' + str(VDDEE) + '\e[0m"\n'
        test.measurements.VDDEE_measurement = VDDEE

    @som_board.testcase('Power circuit 5V DDQ')
    @som_board.plug(greet=GreetPlug)
    @htf.measures(htf.Measurement('SOM5VDDQ_measurement').with_validator(
        lambda SOM5VDDQmeas: isinstance(SOM5VDDQmeas, int) and SOM5VDDQmeas < 5200 and SOM5VDDQmeas > 4800))
    def SOM5VDDQ(test, greet):
        """Voltage measurement in the 5V DDQ power circuit"""
        test.logger.info('Measure 5V DDQ')
        SOM5VDDQmeas = UARTcmd.cmdget("5vddq")
        nonlocal testresults
        if isinstance(SOM5VDDQmeas, int) and SOM5VDDQmeas < 5200 and SOM5VDDQmeas > 4800:
            code = 32
        else:
            code = 31
        testresults[6] = 'echo \"\e[' + str(code) + ';1m  - 5V DDQ:    ' + str(SOM5VDDQmeas) + '\e[0m"\n'
        test.measurements.SOM5VDDQ_measurement = SOM5VDDQmeas

    @som_board.testcase('USB Test')
    @htf.measures(htf.Measurement('USBTest').with_validator(
        lambda SOMUSBresponse: SOMUSBresponse.find('serialno:') != -1 and SOMUSBresponse.find(
            'finished. total time:') != -1))  # Dummy
    def USBTest(test):
        SOMUSBresponse = uBootLoadFile.uBootLoad()
        nonlocal testresults
        if SOMUSBresponse.find('serialno:') != -1 and SOMUSBresponse.find('finished. total time:') != -1:
            testresults[7] = ('echo \"\e[32;1m- USB Test:  Pass\e[0m"\n')
        else:
            testresults[7] = ('echo \"\e[31;1m- USB Test:  Fail\e[0m"\n')
        test.measurements.USBTest = SOMUSBresponse

    @som_board.testcase('DDR Test')
    @htf.measures(htf.Measurement('DDRTest'))  # Dummy
    def DDRTest(test):
        DDRmeas = True
        nonlocal testresults
        if DDRmeas == True:
            testresults[8] = ('echo \"\e[32;1m- USB Test:  Pass\e[0m"\n')
        else:
            testresults[8] = ('echo \"\e[31;1m- USB Test:  Fail\e[0m"\n')
        test.measurements.DDRTest = DDRmeas

    @som_board.testcase('DUT Power Off')
    @htf.plugs.plug(prompts=UserInput)
    def DUTPowerOff(test, prompts):
        nonlocal testresults
        outcomes = [p.outcome for p in test.test_record.phases]
        if outcomes[2] == PhaseOutcome.PASS and outcomes[3] == PhaseOutcome.PASS and outcomes[
            4] == PhaseOutcome.PASS and outcomes[5] == PhaseOutcome.PASS and outcomes[6] == PhaseOutcome.PASS and \
                outcomes[7] == PhaseOutcome.PASS and outcomes[8] == PhaseOutcome.PASS:
            powertest = 32
        else:
            powertest = 31
        test.logger.info("""DUT Power Off""")
        os.system('echo "\e[36;1mDUT Power Off\e[0m"')
        if PhaseOutcome.FAIL in outcomes:
            os.system('echo "\e[31;1mTest Status:\e[0m" "\e[31;1mFAIL\e[0m"')
            teststatus = 'DUT ID' + test.dut_id + ' test status: <p><font color=red>FAIL'
        elif PhaseOutcome.PASS in outcomes:
            os.system('echo "\e[32;1mTest Status:\e[0m" "\e[32;1mFAIL\e[0m"')
            teststatus = 'DUT ID' + test.dut_id + ' test status: <p><font color=green>PASS'
        os.system('echo "\e[' + str(powertest) + ';1m- Power measurments:\e[0m"')
        os.system(testresults[0])
        os.system(testresults[1])
        os.system(testresults[2])
        os.system(testresults[3])
        os.system(testresults[4])
        os.system(testresults[5])
        os.system(testresults[6])
        os.system(testresults[7])
        os.system(testresults[8])

        prompts.prompt("""## """ + teststatus, prompt_type=PromptType.OKAY)

    som_board.run()


# ---------Backplane Board---------------------------------------------------------------------------------

def backplane_board_test():
    backplane_board = TestPlan('Backplane Board Test')
    testresults = [
        'echo \"\e[1m- 20V:  Not Start\e[0m"\n',
        'echo \"\e[1m- 5V:   Not Start\e[0m"\n',
        'echo \"\e[1m- 3.3V: Not Start\e[0m"\n',
        'echo \"\e[1m- 1.8V: Not Start\e[0m"\n',
        'echo \"\e[1m- DC-DC Test (Res. load):   Not Start\e[0m"\n',
        'echo \"\e[1m- DC-DC Test (Cap. load):   Not Start\e[0m"\n',
        'echo \"\e[1m- I2C Test:                 Not Start\e[0m"\n',
        'echo \"\e[1m- Amplifiers Configuration: Not Start\e[0m"\n',
        'echo \"\e[1m- Amplifiers Test:          Not Start\e[0m"\n',
        'echo \"\e[1m- RTC Test:                 Not Start\e[0m"\n',
    ]
    HERE = os.path.abspath(os.path.dirname(__file__))
    FORM_LAYOUT = {
        'schema': {
            'title': "DUT ID",
            'type': "object",
            'required': ["DUT ID"],
            'properties': {
                'DUT ID': {
                    'type': "string",
                    'title': "Enter DUT ID"
                },
            }
        },
        'layout': [
            {
                "type": "help",
                "helpvalue": markdown("""
#Backplane Board Testing

<img src="%s" width="300px" />

""" % backplane_board.image_url(os.path.join(HERE, 'MIC.jpg'))
                                      )
            },
            "DUT ID",
        ]
    }

    class GreetPlug(UserInput):
        def prompt_tester_information(self):
            self.__response = self.prompt_form(FORM_LAYOUT)
            return self.__response

    @backplane_board.trigger('Get DUT ID')
    @backplane_board.plug(greet=GreetPlug)
    @htf.measures(
        htf.Measurement('DUT_ID').with_validator(lambda devidin: re.match(r"^3160{1}", devidin)))  # chage ID pattern
    def hello_world(test, greet):
        """Scan DUT ID and start the test"""
        response = greet.prompt_tester_information()
        test.dut_id = response['DUT ID']
        devidin = test.dut_id
        test.measurements.DUT_ID = devidin

    @backplane_board.testcase('STM32 Status')
    @backplane_board.plug(greet=GreetPlug)
    @htf.measures(htf.Measurement('STM32_Status').with_validator(lambda STMPing: STMPing == 0))
    def SOMSTMPing(test, greet):
        """Check STM32 status"""
        STMPing = UARTcmd.cmdget("Ping")
        test.measurements.STM32_Status = STMPing
        # if MICSTMPingMeas!=0:
        #    raise ValueError('No STM32 connection')

    @backplane_board.testcase('Power circuit 20V')
    @backplane_board.plug(greet=GreetPlug)
    @htf.measures(htf.Measurement('BP20V_measurement').with_validator(
        lambda BP20Vmeas: isinstance(BP20Vmeas, int) and BP20Vmeas < 21000 and BP20Vmeas > 19000))
    def BP20V(test, greet):
        """Voltage measurement in the 20V power circuit"""
        test.logger.info('Measure 20V')
        BP20Vmeas = UARTcmd.cmdget("20v")
        nonlocal testresults
        if isinstance(BP20Vmeas, int) and BP20Vmeas < 5200 and BP20Vmeas > 4800:
            code = 32
        else:
            code = 31
        testresults[0] = 'echo \"\e[' + str(code) + ';1m  - 5V:        ' + str(BP20Vmeas) + '\e[0m"\n'
        test.measurements.BP20V_measurement = BP20Vmeas

    @backplane_board.testcase('Power circuit 5V')
    @backplane_board.plug(greet=GreetPlug)
    @htf.measures(htf.Measurement('BP5V_measurement').with_validator(
        lambda BP5Vmeas: isinstance(BP5Vmeas, int) and BP5Vmeas < 5200 and BP5Vmeas > 4800))
    def BP5V(test, greet):
        """Voltage measurement in the 5V power circuit"""
        test.logger.info('Measure 5V')
        BP5Vmeas = UARTcmd.cmdget("5v")
        nonlocal testresults
        if isinstance(BP5Vmeas, int) and BP5Vmeas < 5200 and BP5Vmeas > 4800:
            code = 32
        else:
            code = 31
        testresults[1] = 'echo \"\e[' + str(code) + ';1m  - 5V:        ' + str(BP5Vmeas) + '\e[0m"\n'
        test.measurements.BP5V_measurement = BP5Vmeas

    @backplane_board.testcase('Power circuit 3.3V')
    @backplane_board.plug(greet=GreetPlug)
    @htf.measures(htf.Measurement('BP3V3_measurement').with_validator(
        lambda BP3V3meas: isinstance(BP3V3meas, int) and BP3V3meas < 3500 and BP3V3meas > 3100))
    def BP3v3(test, greet):
        """Voltage measurement in the 3.3V power circuit"""
        test.logger.info('Measure 3.3V')
        BP3V3meas = UARTcmd.cmdget("3v3")
        nonlocal testresults
        if isinstance(BP3V3meas, int) and BP3V3meas < 3500 and BP3V3meas > 3100:
            code = 32
        else:
            code = 31
        testresults[2] = 'echo \"\e[' + str(code) + ';1m  - 3.3V:      ' + str(BP3V3meas) + '\e[0m"\n'
        test.measurements.BP3V3_measurement = BP3V3meas

    @backplane_board.testcase('Power circuit 1.8V')
    @backplane_board.plug(greet=GreetPlug)
    @htf.measures(htf.Measurement('BP1V8_measurement').with_validator(
        lambda BP1V8meas: isinstance(BP1V8meas, int) and BP1V8meas < 2000 and BP1V8meas > 1600))
    def BP1v8(test, greet):
        """Voltage measurement in the 1.8V power circuit"""
        test.logger.info('Measure 1.8V')
        BP1V8meas = UARTcmd.cmdget("1v8")
        nonlocal testresults
        if isinstance(BP1V8meas, int) and BP1V8meas < 2000 and BP1V8meas > 1600:
            code = 32
        else:
            code = 31
        testresults[3] = 'echo \"\e[' + str(code) + ';1m  - 1.8V:      ' + str(BP1V8meas) + '\e[0m"\n'
        test.measurements.BP1V8_measurement = BP1V8meas

    @backplane_board.testcase('DC-DC Test on Resisitive Load')
    @htf.measures(htf.Measurement('DCDCResistiveLoadTest'))  # Dummy
    def DCDCRes(test):
        DCmeas = True
        nonlocal testresults
        if DCmeas == True:
            testresults[4] = ('echo \"\e[32;1m- DC-DC Test (Res. load):   Pass\e[0m"\n')
        else:
            testresults[4] = ('echo \"\e[31;1m- DC-DC Test (Res. load):   Fail\e[0m"\n')
        test.measurements.DCDCResistiveLoadTest = DCmeas

    @backplane_board.testcase('DC-DC Test on Capacitive Load')
    @htf.measures(htf.Measurement('DCDCCapacitiveLoadTest'))  # Dummy
    def DCDCCap(test):
        DCmeas = True
        nonlocal testresults
        if DCmeas == True:
            testresults[5] = ('echo \"\e[32;1m- DC-DC Test (Cap. load):   Pass\e[0m"\n')
        else:
            testresults[5] = ('echo \"\e[31;1m- DC-DC Test (Cap. load):   Fail\e[0m"\n')
        test.measurements.DCDCCapacitiveLoadTest = DCmeas

    @backplane_board.testcase('I2C Test')
    @htf.measures(htf.Measurement('I2CTest'))  # Dummy
    def I2CTest(test):
        I2Cmeas = True
        nonlocal testresults
        if I2Cmeas == True:
            testresults[6] = ('echo \"\e[32;1m- I2C Test:                 Pass\e[0m"\n')
        else:
            testresults[6] = ('echo \"\e[31;1m- I2C Test:                 Fail\e[0m"\n')
        test.measurements.I2CTest = I2Cmeas

    @backplane_board.testcase('Amplifiers Configuration')
    @htf.measures(htf.Measurement('AmplifiersConfiguration'))  # Dummy
    def AmpConf(test):
        AmpConfmeas = True
        nonlocal testresults
        if AmpConfmeas == True:
            testresults[7] = ('echo \"\e[32;1m- Amplifiers Configuration: Pass\e[0m"\n')
        else:
            testresults[7] = ('echo \"\e[31;1m- Amplifiers Configuration: Fail\e[0m"\n')
        test.measurements.AmplifiersConfiguration = AmpConfmeas

    @backplane_board.testcase('Amplifiers Test')
    @htf.measures(htf.Measurement('AmplifiersTest'))  # Dummy
    def AmpTest(test):
        AmpTestmeas = True
        nonlocal testresults
        if AmpTestmeas == True:
            testresults[8] = ('echo \"\e[32;1m- Amplifiers Test:          Pass\e[0m"\n')
        else:
            testresults[8] = ('echo \"\e[31;1m- Amplifiers Test:          Fail\e[0m"\n')
        test.measurements.AmplifiersTest = AmpTestmeas

    @backplane_board.testcase('Real Time Clock Test')
    @htf.measures(htf.Measurement('RTCTest'))  # Dummy
    def RTCTest(test):
        RTCmeas = True
        nonlocal testresults
        if RTCmeas == True:
            testresults[9] = ('echo \"\e[32;1m- RTC Test:                 Pass\e[0m"\n')
        else:
            testresults[9] = ('echo \"\e[31;1m- RTC Test:                 Fail\e[0m"\n')
        test.measurements.RTCTest = RTCmeas

    @backplane_board.testcase('DUT Power Off')
    @htf.plugs.plug(prompts=UserInput)
    def DUTPowerOff(test, prompts):
        nonlocal testresults
        outcomes = [p.outcome for p in test.test_record.phases]
        if outcomes[2] == PhaseOutcome.PASS and outcomes[3] == PhaseOutcome.PASS and outcomes[
            4] == PhaseOutcome.PASS and outcomes[5] == PhaseOutcome.PASS:
            powertest = 32
        else:
            powertest = 31
        test.logger.info("""DUT Power Off""")
        os.system('echo "\e[36;1mDUT Power Off\e[0m"')
        if PhaseOutcome.FAIL in outcomes:
            os.system('echo "\e[31;1mTest Status:\e[0m" "\e[31;1mFAIL\e[0m"')
            teststatus = 'DUT ID' + test.dut_id + ' test status: <p><font color=red>FAIL'
        elif PhaseOutcome.PASS in outcomes:
            os.system('echo "\e[32;1mTest Status:\e[0m" "\e[32;1mPASS\e[0m"')
            teststatus = 'DUT ID' + test.dut_id + ' test status: <p><font color=green>PASS'
        os.system('echo "\e[' + str(powertest) + ';1m- Power measurments:\e[0m"')
        os.system(testresults[0])
        os.system(testresults[1])
        os.system(testresults[2])
        os.system(testresults[3])
        os.system(testresults[4])
        os.system(testresults[5])
        os.system(testresults[6])
        os.system(testresults[7])
        os.system(testresults[8])
        os.system(testresults[9])

        prompts.prompt("""## """ + teststatus, prompt_type=PromptType.OKAY)

    backplane_board.run()


# ---------Backplane Board---------------------------------------------------------------------------------
def bt_chamber_test():
    BTChamber = TestPlan('BT Chamber')
    FORM_LAYOUT = {
        'schema': {
            'title': "DUT ID",
            'type': "object",
            'required': ["DUT ID"],
            'properties': {
                'DUT ID': {
                    'type': "string",
                    'title': "Enter DUT ID"
                },
            }
        },
        'layout': [
            "DUT ID",
        ]
    }

    class GreetPlug(UserInput):
        def prompt_tester_information(self):
            self.__response = self.prompt_form(FORM_LAYOUT)
            return self.__response

    class COMportPlug(BasePlug):
        def btcomm(self, outputdata, port, baud):
            serialport = serial.Serial()
            serialport.port = port
            serialport.baudrate = baud
            serialport.bytesize = serial.EIGHTBITS
            serialport.parity = serial.PARITY_NONE
            serialport.stopbits = serial.STOPBITS_ONE
            serialport.timeout = 2
            serialport.xonxoff = False
            serialport.rtscts = False
            serialport.dsrdtr = False
            serialport.writeTimeout = 1

            try:
                serialport.open()
            except serial.SerialException:
                print("error open serial port")
                responce = 'ERROR'
            if (serialport.isOpen() == True):
                serialport.flushInput()
                serialport.flushOutput()
                cmd = outputdata.encode('utf-8')
                print(cmd)
                serialport.write(cmd)
                responcebyte = serialport.readall()
                responce = responcebyte.decode("utf-8")
                print(responce)
                # my_file=open("serial.txt", "w")
                # my_file.write(str(responce))
                # my_file.close()
            try:
                serialport.close()
            except serial.SerialException:
                print("error close serial port")

            return responce

    @BTChamber.trigger('DUT ID')
    @BTChamber.plug(greet=GreetPlug)
    @htf.measures(
        htf.Measurement('DUT_ID').with_validator(lambda devidin: re.match(r"^3160{1}", devidin)))  # chage ID pattern
    def DUTID(test, greet):
        """Scan DUT ID and start the test"""
        response = greet.prompt_tester_information()
        test.dut_id = response['DUT ID']
        devidin = test.dut_id
        test.measurements.DUT_ID = devidin

    @BTChamber.testcase('ResetBT18')
    @BTChamber.plug(serialplug=COMportPlug)
    @htf.measures(htf.Measurement('ResetBT18resp'))
    def ResetBT18(test, serialplug):
        test.logger.info('Reset Bluetooth device')
        responce = serialplug.btcomm('AT+MRST=1\r\n', "/dev/ttyUSB0", 115200)
        if responce.find('+MRST:END') != -1:
            test.measurements.ResetBT18resp = responce
        else:
            test.measurements.ResetBT18resp = "Can't reset BT device"
            return PhaseResult.FAIL_AND_CONTINUE

    @BTChamber.testcase('ConnectionBT18')
    @BTChamber.plug(serialplug=COMportPlug)
    @htf.measures(htf.Measurement('ConnectionBT18resp').with_validator(
        lambda responce: responce.find('A2DP connected') != -1 and responce.find('A2DP Media Streaming') != -1))
    def ConnectionBT18(test, serialplug):
        test.logger.info('Connect to DUT Bluetooth')
        responce = serialplug.btcomm('AT+SCON=B0024748F961\r\n', "/dev/ttyUSB0", 115200)
        if responce.find('A2DP connected') != -1 and responce.find('A2DP Media Streaming') != -1:
            test.measurements.ConnectionBT18resp = responce
        else:
            test.measurements.ConnectionBT18resp = 'No DUT connection'

    @BTChamber.testcase('RSSIBT18')
    @BTChamber.plug(serialplug=COMportPlug)
    @htf.measures(htf.Measurement('RSSIBT18resp').in_range(-70, 0, type=int))
    def RSSIBT18(test, serialplug):
        test.logger.info('Read RSSI')
        responce = serialplug.btcomm('AT+RSSI=B0024748F961\r\n', "/dev/ttyUSB0", 115200)
        if responce.find('+RSSI=-') != -1:
            rssi = int(''.join(re.findall('(\d+)', responce))) * -1
            test.measurements.RSSIBT18resp = rssi

    @BTChamber.testcase('STATUSBT18aftertest')
    @BTChamber.plug(serialplug=COMportPlug)
    @htf.measures(htf.Measurement('StatusAfterTest'))
    def STATUSBT18aftertest(test, serialplug):
        test.logger.info('Read connection status')
        responce = serialplug.btcomm('AT+STAT=?\r\n', "/dev/ttyUSB0", 115200)
        test.measurements.StatusAfterTest = responce

    @BTChamber.testcase('DisconnectionBT18')
    @BTChamber.plug(serialplug=COMportPlug)
    @htf.measures(
        htf.Measurement('DisconnectionBT18resp').with_validator(lambda responce: responce.find('+SDSC:END') != -1))
    def DisconnectionBT18(test, serialplug):
        test.logger.info('Disconnect from DUT Bluetooth')
        responce = serialplug.btcomm('AT+SDSC\r\n', "/dev/ttyUSB0", 115200)
        test.measurements.DisconnectionBT18resp = responce
        if responce.find('Device Disconnected Already !') != -1:
            test.measurements.DisconnectionBT18resp = 'Connection lost before test end!'
            return PhaseResult.FAIL_AND_CONTINUE

    @BTChamber.testcase('Test Results')
    @htf.plugs.plug(prompts=UserInput)
    def TestResults(test, prompts):
        outcomes = [p.outcome for p in test.test_record.phases]
        if PhaseOutcome.FAIL in outcomes:
            os.system('echo "\e[31;1mTest Status:\e[0m" "\e[31;1mFAIL\e[0m"')
            teststatus = 'DUT ID' + test.dut_id + ' test status: <p><font color=red>FAIL'
        else:
            os.system('echo "\e[32;1mTest Status:\e[0m" "\e[32;1mPASS\e[0m"')
            teststatus = 'DUT ID' + test.dut_id + ' test status: <p><font color=green>PASS'

        prompts.prompt("""## """ + teststatus, prompt_type=PromptType.OKAY)

    BTChamber.run()


# ---------------------------------------------------------------------------------------------------------

class PerformTest():
    def __init__(self, server, test_type=None):
        super(self.__class__, self).__init__()
        logging.info("started %s" % test_type.name)

        if test_type == TestTypes.LED_BOARD_TEST:
            led_board_test()
        elif test_type == TestTypes.LEDRING_BOARD_TEST:
            ledring_board_test()
        elif test_type == TestTypes.MIC_BOARD_TEST:
            mic_board_test()
        elif test_type == TestTypes.SOM_BOARD_TEST:
            som_board_test()
        elif test_type == TestTypes.BACKPLANE_BOARD_TEST:
            backplane_board_test()
        elif test_type == TestTypes.BT_CHAMBER_TEST:
            bt_chamber_test()
        else:
            exit("No such test type")


def main(args=None):
    """
    start and navigate to UI, run tests, terminate UI
    """
    start_dir = os.path.dirname(__file__)

    if start_dir:
        # start_dir is empty if it's current dir
        os.chdir(start_dir)

    parser = argparse.ArgumentParser()
    parser.add_argument('--test_type', type=TestTypes, choices=list(TestTypes), required=True)
    parser.add_argument('--no_barcode', action='store_true', default=False)
    parser.add_argument('--no_ftp', action='store_true', default=False)
    parser.add_argument('--no_ui', action='store_true', default=False)
    parser.add_argument('--once', action='store_true', default=False)
    parser.add_argument('--config_file', default=default_config())

    args = parser.parse_args(args)
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(levelname)s: %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S')

    # with open(args.config_file) as config_file:
    #   conf.load_from_file(config_file)

    # conf.load(station_server_port='4444', capture_docstring=True)
    with station_server.StationServer() as server:
        try:
            subprocess.Popen(['pkill', 'chromium']).wait()
        except:
            logging.info("no browser to kill")
            # webbrowser.get(using='chromium-browser').open_new_tab('http://localhost:4444/')
            # time.sleep(4)
            # os.system('xdotool search --onlyvisible --class "chromium" windowfocus && xdotool key F11')

        PerformTest(server, test_type=args.test_type)


def default_config():
    """
    Returns path to an appropriate config file
    """
    # os.uname()[1] gives short hostname, like `quasar-test`
    # see config/README.md for more info
    return os.path.abspath(os.path.join(os.path.dirname(__file__), 'configs', '%s.config.yml' % os.uname()[1]))


if __name__ == '__main__':
    main()

    print('OK')
