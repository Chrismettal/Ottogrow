#############################################################################
##                               GRASS                                     ##
#############################################################################
# PiPLC / Raspberry Pi based controller for a growtent

# Secrets
import mqttsecrets

# General libraries
import os
import sys
import glob
import time
import datetime
# GPIO
import RPi.GPIO as GPIO
# MQTT
import paho.mqtt.client as mqtt
# Sensors 
import board
from adafruit_seesaw.seesaw import Seesaw
import adafruit_ahtx0
import libds18b20
import cv2

#############################################################################
##                           Global variables                              ##
#############################################################################
# General
snapLocation    = "~/GrassSnaps/"

# MQTT
mqttTopicOutput = "grass/outputs/"
mqttTopicInput  = "grass/inputs/#"
mqttQos         = 2

# Machine parameters, set through recipe or MQTT outputs
controlMode     = "local"
airTempSet      = 20    # Air Temperature setpoint in C
airTempHyst     = 1     # Hysterysis for AirTemperature contoller
airHumMax       = 90    # Maximum air humidity in % before ventilation starts
soilMoistSet    = 1000  # Soil moisture setpoint in whatever unit Adafruit found appropriate (200 .. 2000)
wateringPulseOn = 10    # How long the water can be turned on
wateringPulseOff= 30    # How long the water needs to be off
airCircDuration = 30    # Duration of air circulation when triggered
airCircTime     = 60    # Time in minutes between air circulations
lightSet        = 2000  # Target brightness in Lux
lightOn         = 1     # Binary output of Light switch
cameraTime      = 15    # Time in minutes between camera pictures
sensorInterval  = 30    # Interval to measure inputs in seconds
s0kWhPerPulse   = 0.1   # kWH to be added to total counter per pulse

# Machine thinking
lastCameraSnap  = 1
lastAirCirc     = 0
runFan          = 0
runHeater       = 0
runLight        = 0
lastWaterOff    = 0
lastSensors     = 0
soilSensors     = []    # List of soil sensor entities
topic           = ""
payload         = ""
lightOnTime     = 3     # Hour at which light is switched on 
lightOffTime    = 21    # Hour at which light is switched off
energyUsed      = 0.0   # Total energy used in kwh

# Sensor states
CameraOK        = True
mqttOK          = False
allStemmasOK    = True
lightSensorOK   = True
airSensorOK     = True

###################
# GPIO mapping
###################
# Pin Config
digitalInputs   = [17, 27, 22, 10,  9, 11, 13, 26]  # I1 - I8
digitalOutputs  = [24, 25,  8,  7, 12, 16, 20, 21]  # Q1 - Q8
pwmOutputs      = [18, 19]
oneWire         = [23]

# Digital Inputs
S0counter       = 17

# Relays
relayLight      = 24    # Q1
relayHeater     = 25    # Q2
relayExhaust    =  8    # Q3
relayWater      = 12    # Q5
relayCirc       = 16    # Q6

# PWM
pwmCircFan      = 18    # PWM 1 

#############################################################################
##                           Global Constants                              ##
#############################################################################
# Stemma soil adresses
SOIL_MOIST_ADR  = [0x36, 0x37, 0x38, 0x39]

#############################################################################
##                               Helpers                                   ##
#############################################################################
#######################################
# S0 counter
#######################################
def s0callback():
    global energyUsed
    energyUsed += s0kWhPerPulse

#######################################
# Paho connection established
#######################################
def on_connect(client, userdata, flags, rc, properties=None):
    global mqttOK
    print("Connection established")
    mqttOK = True

#######################################
# Callback on received message
#######################################
def callback(client, userdata, message):
    print("Message received: " + str(message.payload.decode("utf-8")))

#######################################
# Subscription successful
#######################################
def on_subscribe(client, userdata, mid, granted_ops, properties=None):
    print("On subscribe called")

#######################################
# Paho setup
#######################################
def pahoSetup():
    global mqttc
    mqttc = mqtt.Client(callback_api_version = mqtt.CallbackAPIVersion.VERSION2, client_id=mqttsecrets.ClientId)
    mqttc.on_message = callback
    mqttc.on_connect = on_connect
    mqttc.on_subscribe = on_subscribe
    mqttc.username_pw_set(mqttsecrets.Username, mqttsecrets.Password)
    mqttc.connect(mqttsecrets.Broker, mqttsecrets.Port)
    mqttc.subscribe(mqttTopicInput, qos=1)
    # Start the mqtt loop, no intension to ever end
    mqttc.loop_start()

#######################################
# Picture snapper
#######################################
def snapPicture():
    global cam
    ret, image = cam.read()
    if not ret:
        print("failed to snap picture")
        return
    cv2.imwrite(snapLocation + datetime.datetime.now(), image)
    cam.release()

#######################################
# Sensor setup
#######################################
def sensorSetup():
    global cam
    global cameraOK, allStemmasOK, lightSensorOK, airSensorOK

    # Pin setup
    GPIO.setmode(GPIO.BCM)
    for pin in digitalOutputs:
        GPIO.setup(pin, GPIO.OUT)
    for pin in digitalInputs:
        GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    #for pin in pwmOutputs:
    #    GPIO.setup(pin, GPIO.OUT)
    #    #TODO

    # S0 counter
    GPIO.add_event_detect(S0counter, GPIO.FALLING, 
        callback=s0callback, bouncetime=50)

    # I2C Adafruit
    i2c_bus = board.I2C()

    # Stemma soil moisture sensor
    for address in SOIL_MOIST_ADR:
        try:
            ss = Seesaw(i2c_bus, addr=address)
            soilSensors.append(ss)
        except stemmaException:
            print("Stemma soil sensor " + str(address) + " not found!")
            allStemmasOK = False

    # Light sensor
    try:
        lightSensor = adafruit_bh1750.BH1750(i2c_bus)
    except lightException:
        print("Light sensor couldn't be added!")
        lightSensorOK = False

    # Temp / Air hum sensor
    try:
        airSensor = adafruit_ahtx0.AHTx0(i2c_bus)
    except airException:
        print("Air sensor couldn't be found!")
        airSensorOK = False

    # Camera
    try:
        cam = cv2.VideoCapture(0)
    except cameraInstanceException:
        print("Camera instancing didn't work!")
        cameraOK = False

    # Upload detected sensor states to MQTT
    try:
        # Stemmas
        topic = mqttTopicOutput + "sensorstates/soil"
        infot = mqttc.publish(topic, str(allStemmasOK), qos=mqttQos)
        infot.wait_for_publish()
        # Light
        topic = mqttTopicOutput + "sensorstates/light"
        infot = mqttc.publish(topic, str(lightSensorOK), qos=mqttQos)
        infot.wait_for_publish()
        # Air
        topic = mqttTopicOutput + "sensorstates/air"
        infot = mqttc.publish(topic, str(airSensorOK), qos=mqttQos)
        infot.wait_for_publish()
        # Camera
        topic = mqttTopicOutput + "sensorstates/camera"
        infot = mqttc.publish(topic, str(cameraOK), qos=mqttQos)
        infot.wait_for_publish()
    except soilSensorMQTTException:
        print("Sending sensor states to MQTT didn't work!")

#######################################
# Actual machine code
#######################################
def machineCode():
    # Import global vars
    global lastCameraSnap, lastAirCirc, runFan, runHeater, runLight, lastWaterOff, lastSensors, soilSensors, topic, payload
    global controlMode, airTempSet, airTempHyst, airHumMax, soilMoistSet, wateringPulseOn, wateringPulseOff, airCircDuration
    global airTemp, airHum
    global airCircTime, lightSet, lightOn, cameraTime, sensorInterval
    global cameraOK, allStemmasOK, lightSensorOK, airSensorOK
    global s0kWhPerPulse, energyUsed
    lastRunLight = False

    # Remember timestamp
    now = time.time()

    # ---------------------------------
    # Camera Snapshot
    # ---------------------------------
    if cameraOK and now > lastCameraSnap + (cameraTime * 60):
        # Snap a pic
        lastCameraSnap = now
        print("Taking Snapshot")
        try:
            snapPicture()
        except cameraSnapException:
            print("Taking picture didn't work!")

    # ---------------------------------
    # Measure sensors
    # ---------------------------------
    if now > lastSensors + sensorInterval:
        lastSensors = now

        # -----------------------------
        # Measure soil humidities and temperatures
        # -----------------------------
        soilMoistAvg = 0
        # Iterate through all connected sensors
        for idx, soilSensor in enumerate(soilSensors):
            # Grab soil inputs
            try:
                soilTemp        = soilSensor.moisture_read()
                soilMoist       = soilSensor.get_temp()
            except soilSensorException:
                print("Soil sensor " + str(idx) + " reading didn't work!")

            soilMoistAvg    = soilMoistAvg + soilMoist
            print("Bucket " + str(idx) + ": Temperature: " + str(soilTemp) + ", Moisture: " + str(soilMoist))

            try:
                # Send moisture
                topic = mqttTopicOutput + "bucketmoists/" + str(idx)
                infot = mqttc.publish(topic, str(soilMoist), qos=mqttQos)
                infot.wait_for_publish()
                # Send temperature
                topic = mqttTopicOutput + "buckettemps/" + str(idx)
                infot = mqttc.publish(topic, str(soilTemp), qos=mqttQos)
                infot.wait_for_publish()
            except soilSensorMQTTException:
                print("Sending soil sensor " + str(idx) + " to MQTT didn't work!")

        if len(soilSensors) > 0:
            soilMoistAvg = soilMoistAvg / len(soilSensors)

        # -----------------------------
        # Measure water temp
        # -----------------------------
        try:
            waterTemp = ds18b20_read_temp()
        except waterTempException:
            print("Reading water temperature didn't work!")
        try:
            topic = mqttTopicOutput + "watertemp"
            infot = mqttc.publish(topic, str(waterTemp), qos=mqttQos)
            infot.wait_for_publish()
        except waterTempMQTTException:
            print("Sending water temperature to MQTT didn't work!")

        # -----------------------------
        # Measure light brightness
        # -----------------------------
        try:
            print("%.2f Lux" % 123)
            topic = mqttTopicOutput + "brightness"
            infot = mqttc.publish(topic, str(123), qos=mqttQos) # TODO
            infot.wait_for_publish()
        except lightSensorException:
            print("Reading or sending Light Sensor didn't work!")

        # -----------------------------
        # Measure Air temp and humidity
        # -----------------------------
        try:
            airTemp = airSensor.temperature
            airHum  = airSensor.relative_humidity
            print("Air temperature: %0.1f C" % airTemp)
            print("Air humidity: %0.1f %%" % airHum)
        except airSensorException:
            print("Reading the air sensor didn't work!")
        try:
            # Send humidity
            topic = mqttTopicOutput + "airhum"
            infot = mqttc.publish(topic, str(airHum), qos=mqttQos)
            infot.wait_for_publish()
            # Send temperature
            topic = mqttTopicOutput + "airtemp"
            infot = mqttc.publish(topic, str(airTemp), qos=mqttQos)
            infot.wait_for_publish()
        except airSensorMQTTException:
            print("Sending air sensor to MQTT didn't work!")

        # -----------------------------
        # Measure water level in reservoir
        # -----------------------------
        # TODO

        # -----------------------------
        # Energy used
        # -----------------------------
        # Remember in case we die
        with open('GrassEnergyUsed.txt', 'w') as f:
            f.write(str(energyUsed))
        # Upload to MQTT
        try:
            topic = mqttTopicOutput + "energy"
            infot = mqttc.publish(topic, str(energyUsed), qos=mqttQos)
            infot.wait_for_publish()
        except s0uploadException:
            print("Uploading energy to MQTT didn't work!")

    # ---------------------------------
    # Heater
    # ---------------------------------
    if airTemp < (airTempSet - airTempHyst):
        runHeater = 1
        print("Heater On")
    elif airTemp < (airTempSet + airTempHyst):
        runHeater = 0
        print("Heater Off")

    # ---------------------------------
    # Circulation
    # ---------------------------------
    # If time since last circulation exceeded the setpoint:
    if now > lastAirCirc + (airCircTime * 60):
        # Turn fan on
        runFan = 1
        print("Circulation fan on")
        # If time since last circulation exceeded the setpoint + fan duration:
        if now > lastAirCirc + (airCircTime * 60) + (airCircDuration):
            # Turn fan off and remember circulation time
            runFan = 0
            lastAirCirc = now
            print("Circulation fan off")

    # ---------------------------------
    # Exhaust
    # ---------------------------------
    # TODO
    runExhaust = False

    # ---------------------------------
    # Lighting
    # ---------------------------------
    currentHour = datetime.datetime.now().hour
    runLight    = currentHour > lightOnTime and currentHour < lightOffTime
    if runLight and not lastRunlight:
        print("Turning light on!")
    elif not runlight and lastRunLight:
        print("Turning light off!")
    if runLight != lastRunLight:
        try:
            # Send light state
            topic = mqttTopicOutput + "runlight"
            infot = mqttc.publish(topic, str(runLight), qos=mqttQos)
            infot.wait_for_publish()
        except lightNotifierException:
            print("Sending light state to MQTT didn't work!")
    lastRunLight = runLight

    # ---------------------------------
    # Watering
    # ---------------------------------
    # Never attempt watering if WateringPulseOff hasn't elapsed yet
    if now > lastWaterOff + wateringPulseOff:
        if soilMoistAvg < soilMoistSet:
            GPIO.output(relayWater, True)
            print("Water pump on")
            time.sleep(wateringPulseOn) # (Blocking so we don't risk keeping water on)
            GPIO.output(relayWater, False)
            print("Water pump off")
            lastWaterOff = now

    # ---------------------------------
    # HW Output updates
    # ---------------------------------
    GPIO.output(relayLight,     runLight)
    GPIO.output(relayHeater,    runHeater)
    GPIO.output(relayExhaust,   runExhaust)
    GPIO.output(relayCirc,      runFan)

#############################################################################
##                               main()                                    ##
#############################################################################
def main():
    print("---------------------")
    print("---Starting  Grass---")
    print("---------------------")

    global mqttOK, energyUsed

    # Read out remembered energy if present
    try:
        with open('GrassEnergyUsed.txt', 'r') as f:
            energyUsed = float(f.read())
            print("Read out " + str(energyUsed) + "kWh energy used from memory!")
    except readEnergyException:
        print("No energy memory present. Starting at 0kwh!")

    # Paho setup
    while not mqttOK:
        try:
            pahoSetup()
        except pahoException:
            print("Paho setup failed!")
        machine.sleep(3)

    # Sensor setup
    sensorSetup()

    # Machine code
    while(1):
        machineCode()
        time.sleep(1)


#############################################################################
##                         main() idiom                                    ##
#############################################################################
if __name__ == "__main__":
    main()
