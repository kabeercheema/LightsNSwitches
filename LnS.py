import RPi.GPIO as GPIO
import threading
import can 
import cantools
import sys
from time import sleep 
from datetime import datetime

'''Program that controls the lights and switches in the car, 
	by communicating on EVC CAN'''

# Message IDs
PSC_Lights_MSG_ID = 0x700
ADAS_Lights_MSG_ID = 0x701
LnS_SwitchStatus_MSG_ID = 0x702
LnS_LightsStatus_MSG_ID = 0x703

# Configure GPIO
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)

# Define switch pin configurations
SWITCH_PINS = [17, 27, 22, 5]  # The four switch pins
LIGHT_PINS = [23, 24, 12, 16, 7]  

# Define light pin configurations - five light pins
PropSysLightPin = 23
HVSysLightPin = 24
CAVLongCtrlLightPin = 12
CAVLatCtrlLightPin = 16
CAVV2XCtrlLightPin = 7

# Define light pin state values
PropSysLightState = 0
HVSysLightState = 0
CAVLongCtrlLightState = 0
CAVLatCtrlLightState = 0
CAVV2XCtrlLightState = 0

# Configure switch pins as inputs with pull-up resistors
for pin in SWITCH_PINS:
    GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

# Configure light pins as outputs
for pin in LIGHT_PINS:
    GPIO.setup(pin, GPIO.OUT)
    GPIO.output(pin, GPIO.LOW)  # Initialize all lights as off

#configure can1 as our can bus
filters = [
	{"can_id": 0x700, "can_mask": 0x7FF, "extended": False}, # Only accept 0x700
	{"can_id": 0x701, "can_mask": 0x7FF, "extended": False}, 
	] # Only accept 0x701
try:
    bus = can.interface.Bus(channel='can1', interface='socketcan')
    bus.set_filters(filters)
    
    
except OSError:
    print("Error: CAN bus not available. Make sure it's properly configured.")
    exit(1)

# Communication monitoring variables
last_message_time = datetime.now()
COMM_TIMEOUT = 5.0  # 5 seconds timeout
comm_ok = True      # Flag to track communication status
led_control_mode_normal = True

lock = threading.Lock() #adds lock to prevent racing conditions

# Load DBC file
try:
	db = cantools.database.load_file('EVC_DataLogging_Rev3_EDITED.dbc')
	switch_message = db.get_message_by_frame_id(LnS_SwitchStatus_MSG_ID)
	lns_light_message = db.get_message_by_frame_id(LnS_LightsStatus_MSG_ID)
except Exception as e:
    print(f"Error loading DBC file: {e}")


def set_light_state(pin, state):
	"""Sets the lights to their corresponding state"""
	if state == 0:
		GPIO.output(pin, GPIO.LOW)
	elif state == 1:
		GPIO.output(pin, GPIO.HIGH)
	elif state == 2:
		toggle_light(pin)  # Toggle state (flashing LEDs)
	else:
		print(f"Invalid state {state} for pin {pin}")
		
def toggle_light(pin):
	"""Toggle the state of a light pin, used to create a flashing effect"""
	current_state = GPIO.input(pin)
	GPIO.output(pin, not current_state)  # Toggle the state

def lights():	
	global last_message_time, comm_ok, led_control_mode_normal
	global PropSysLightState, HVSysLightState, CAVLongCtrlLightState, CAVLatCtrlLightState, CAVV2XCtrlLightState
	'''Thread to receive CAN messages and control lights'''
	#for controlling the lights based on if they have changed states
	oldPropSysLightState = 0
	oldHVSysLightState = 0
	oldCAVLatCtrlLightState = 0 
	oldCAVV2XCtrlLightState = 0
	oldCAVLongCtrlLightState = 0

	while True:
		with lock:
			try:
				message = bus.recv(0.5)
				
				#for restoring comms
				if message is not None:
					print(message)
					led_control_mode_normal = True
					if not comm_ok:
						comm_ok = True

						#set_light_state(light, 0)
						PropSysLightState = 0
						HVSysLightState = 0
						CAVLongCtrlLightState = 0 
						CAVV2XCtrlLightState = 0
						CAVLatCtrlLightState = 0											
						print("Communication Restored")
						
					last_message_time = datetime.now()
			
					try:
						# Check if this message can be decoded with our database
						decoded_message = db.decode_message(message.arbitration_id, message.data)						
					
					#Check if this is a light control message			
						if message.arbitration_id == PSC_Lights_MSG_ID:
							#print(message)
							PropSysLightState = decoded_message['PropulsionSystemStatusLight']
							HVSysLightState = decoded_message['HVSystemStatusLight']
							print(f"Updated PSC lights {PropSysLightState}, {HVSysLightState}")
						elif message.arbitration_id == ADAS_Lights_MSG_ID:
							CAVLongCtrlLightState = decoded_message['CAVLongCtrlStatusLight']
							CAVLatCtrlLightState = decoded_message['CAVLatCtrlStatusLight']
							CAVV2XCtrlLightState = decoded_message['CAVV2XStatusLight']
							print(f"Updated CAV lights {CAVLongCtrlLightState}, {CAVLatCtrlLightState}, {CAVV2XCtrlLightState}")
				
					except:
						#if we could not decode the message
						led_control_mode_normal = False
						print("asdfsdaf", message)
						print("Exception: Cannot decode")
				 
				#toggle lights if loss of comms
				if not led_control_mode_normal:
					PropSysLightState = 2
					HVSysLightState = 2
					CAVLongCtrlLightState = 2 
					CAVV2XCtrlLightState = 2
					CAVLatCtrlLightState = 2

			# Change light only if state has changed	
			
				if oldPropSysLightState != PropSysLightState or PropSysLightState == 2:
					set_light_state(PropSysLightPin, PropSysLightState)
					oldPropSysLightState = PropSysLightState
					
				if oldHVSysLightState != HVSysLightState or HVSysLightState == 2:
					set_light_state(HVSysLightPin, HVSysLightState)
					oldHVSysLightState = HVSysLightState	
					
				if oldCAVLongCtrlLightState != CAVLongCtrlLightState or CAVLongCtrlLightState == 2:
					set_light_state(CAVLongCtrlLightPin, CAVLongCtrlLightState)
					oldCAVLongCtrlLightState = CAVLongCtrlLightState	
					
				if oldCAVLatCtrlLightState != CAVLatCtrlLightState or CAVLatCtrlLightState == 2:
					set_light_state(CAVLatCtrlLightPin, CAVLatCtrlLightState)
					oldCAVLatCtrlLightState = CAVLatCtrlLightState	
					
				if oldCAVV2XCtrlLightState != CAVV2XCtrlLightState or CAVV2XCtrlLightState == 2:
					set_light_state(CAVV2XCtrlLightPin, CAVV2XCtrlLightState)
					oldCAVV2XCtrlLightState = CAVV2XCtrlLightState	
					
			except can.CanError:
				print("Error receiving CAN message")
			
			
		#loss of comms detection
		time_since_last_msg = (datetime.now() - last_message_time).total_seconds()
		if comm_ok and time_since_last_msg > COMM_TIMEOUT:
			comm_ok = False
			with lock:
				led_control_mode_normal = False
				print(f"WARNING: Communication lost! No messages received for {COMM_TIMEOUT} seconds")
				print("Toggling all lights to show loss of communication")
			#turn all lights off so they are in sync when flashing
			for light_pin in LIGHT_PINS:
				GPIO.output(light_pin, GPIO.LOW)

		sleep(0.01)
        
def switches():
	"""Thread to read switch statuses and send CAN messages every 0.25 seconds"""
	while True:
		switch_statuses = []
		# Read status of all switches, store them in switch_statuses list
		for pin in SWITCH_PINS:
			status = 0 if GPIO.input(pin) else 1  # 0=OFF, 1=ON
			switch_statuses.append(status)

		try:
			# Create signal data dictionary according to DBC definition
			data = {
			'LnS_RegenBrakingSwitchStatus': switch_statuses[0],
			'LnS_CAVLongControlSwitchStatus': switch_statuses[1],
			'LnS_CAVLatControlSwitchStatus': switch_statuses[2],
			'LnS_CAVV2XControlSwitchStatus': switch_statuses[3]
			}
			# Encode the message data using the DBC definition
			message_data = switch_message.encode(data)
			message = can.Message(
				arbitration_id=switch_message.frame_id,
				data=message_data,
				is_extended_id=switch_message.is_extended_frame
			)
			with lock:
				try:
					bus.send(message,timeout=1)
				except can.CanError as e:
					#waits for the buffer space to flush 
					if "buffer space" in str(e).lower():
						time.sleep(0.05) 
					try:
						bus.send(message) #retries to send the message
						print(f"Sent switch after error statuses: {switch_statuses}")
					except Exception as e2:
						print(f"error sending can message after retry")
					else:
						print(f"error sending can message: {e}")
		except Exception as e:
			print(f"Error sending CAN message: {e}")

		# Wait for next cycle (0.25 seconds)
		sleep(0.01)

if __name__ == "__main__" :
	try:
		try:
			#runs command on the terminal to increase the CAN transmit buffer size to 1000
			import subprocess
			subprocess.run(["sudo", "ip", "link", "set", "can1", "txqueuelen", "1000"], check = True)
			print("Increased CAN buffer size to 1000")
		except:
			print("Using default CAN buffer size")
        
		switch_thread = threading.Thread(target=switches)
		light_thread = threading.Thread(target=lights)

		switch_thread.daemon = True
		light_thread.daemon = True
        
		switch_thread.start()
		light_thread.start()
		#while loop to keep main thread alive
		while True:
			sleep(0.05)
	except KeyboardInterrupt:
		print("\nProgram stopped by user")
		
	finally:
		# Clean up GPIO on exit and explicitly turn off lights
		for pin in LIGHT_PINS:
			GPIO.output(pin, GPIO.LOW)
			sleep(0.1)
		GPIO.cleanup()
		print("GPIO cleaned up")
		try:
			bus.shutdown()
			print("Bus shut down")
		except Exception as e:
			print(f"Errorshuting down CAN bus: {e}")

