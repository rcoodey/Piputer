#!/usr/bin/env python3
import os
import configparser 
import time
import requests
import logging
import socketserver 
import threading
import subprocess
from http.server import BaseHTTPRequestHandler

#Open configuration file
config = configparser.ConfigParser()
script_dir = os.path.dirname(__file__) 
config.read(os.path.join(script_dir, 'PiputerServer.conf'))

#Get SmartThings settings
smartthings_application_id = config.get('SmartThings', 'application_id') 
smartthings_access_token = config.get('SmartThings', 'access_token') 
smartthings_event_url = "https://graph.api.smartthings.com/api/smartapps/installations/" + smartthings_application_id + "/{0}/{1}?access_token=" + smartthings_access_token 
smartthings_all_pc_statuses_event_url = smartthings_event_url.format("piputer", "allPCStatusesEvent")
smartthings_update_frequency = int(config.get('SmartThings', 'update_frequency'))
smartthings_accelerated_update_frequency = int(config.get('SmartThings', 'accelerated_update_frequency'))
smartthings_accelerated_update_count = int(config.get('SmartThings', 'accelerated_update_count'))

#Get Piputer settings and configure logging
http_port = int(config.get('Piputer', 'http_port'))
pc_ip_addresses = config.get('Piputer', 'pc_ip_addresses').split(',')
pc_physical_addresses = config.get('Piputer', 'pc_physical_addresses').split(',')
pc_user_names = config.get('Piputer', 'pc_user_names').split(',')
pc_passwords = config.get('Piputer', 'pc_passwords').split(',')
pc_shutdown_type = config.get('Piputer', 'pc_shutdown_type').split(',')
log_file = config.get('Piputer', 'log_file') 
logging.basicConfig(filename=log_file, filemode='a', format="%(asctime)s %(levelname)s %(message)s", datefmt="%m-%d-%y %H:%M:%S", level=logging.INFO)
logging.getLogger("urllib3").setLevel(logging.WARNING)

#Global counters
update_frequency_accelerated_states = ['Unknown'] * len(pc_ip_addresses)
update_frequency_accelerated_counts = [0] * len(pc_ip_addresses) #Default 0 (false)

#Return JSON string for one pc (single option used if output will be combined with additional pcs)
def get_pc_status_json(pcIndex, single = True):
    try:
        ret = subprocess.call("ping -c 1 " + pc_ip_addresses[pcIndex],
            shell=True,
            stdout=open('/dev/null', 'w'),
            stderr=subprocess.STDOUT)
        json = '"' + str(pcIndex) + '":'
        if ret == 0:
            json = json + '"1' #On
        else:
            json = json + '"0' #Off

        if update_frequency_accelerated_counts[pcIndex]:
            #Stop accelerated counter when status changes
            if (update_frequency_accelerated_states[pcIndex] == 'On' and ret == 0) or (update_frequency_accelerated_states[pcIndex] == 'Off' and ret != 0):
                update_frequency_accelerated_counts[pcIndex] = 0
            else:
                json = json + 'A' #Accelerated (send to SmartThings for proper labeling
        
        json = json + '"'
        
        if single:
            json = '{' + json + '}'

        return json
    except Exception as e:
        logging.exception("Error getting PC status: " + str(e))

#Return JSON string for all pcs
def get_all_pc_statuses_json():
    json = '{'
    for index, ip in enumerate(pc_ip_addresses):
        json = json + get_pc_status_json(index, False)

        if ip == pc_ip_addresses[-1]:
            json = json + '}'
        else:
            json = json + ','
    return json

#Send WOL packet to one pc
def wake_pc(pcIndex):
    try:
        subprocess.call("wakeonlan " + pc_physical_addresses[pcIndex],
            shell=True,
            stdout=open('/dev/null', 'w'),
            stderr=subprocess.STDOUT)
        
        global update_frequency_accelerated_counts
        global update_frequency_accelerated_states
        update_frequency_accelerated_counts[pcIndex] = 1
        update_frequency_accelerated_states[pcIndex] = 'On'

        message = 'Wake up sent to physical address: ' + pc_physical_addresses[pcIndex]
        print(message)
        logging.info(message)
        return message
    except Exception as e:
        logging.exception("Error waking pc: " + str(e))

#Send shutdown request to one pc
def shutdown_pc(pcIndex):
    try:
        if pc_shutdown_type[pcIndex] == "ssh":
            command = "ssh " +  pc_user_names[pcIndex] + "@" + pc_ip_addresses[pcIndex] + " poweroff"
        else:
            command = "net rpc shutdown -I " + pc_ip_addresses[pcIndex] + " -U " + pc_user_names[pcIndex] + '%' + pc_passwords[pcIndex]
        subprocess.call(command,
            shell=True,
            stdout=open('/dev/null', 'w'),
            stderr=subprocess.STDOUT)

        global update_frequency_accelerated_counts
        global update_frequency_accelerated_states
        update_frequency_accelerated_counts[pcIndex] = 1
        update_frequency_accelerated_states[pcIndex] = 'Off'
        
        message = 'Shutdown sent to IP: ' + pc_ip_addresses[pcIndex]
        print(message)
        logging.info(message)
        return message
    except Exception as e:
        logging.exception("Error shutting down pc: " + str(e))

#Parses and responds to incoming HTTP requests
class GetHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
	    #Get index for commands that need it
            indexSplit = self.path.split('/')
            index = None
            if len(indexSplit) > 2 and indexSplit[2].isdigit():
                index = int(indexSplit[2])

            #Parse URL command and send response
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            if '/GetPCStatus' in self.path and index is not None:
                self.wfile.write(bytes(get_pc_status_json(index),'utf-8'))
            elif self.path == '/GetAllPCStatuses':
                self.wfile.write(bytes(get_all_pc_statuses_json(),'utf-8'))
            elif '/WakePC' in self.path and index is not None:
                self.wfile.write(bytes(wake_pc(index),'utf-8'))
            elif '/ShutdownPC' in self.path and index is not None:
                self.wfile.write(bytes(shutdown_pc(index),'utf-8'))
            else:
                self.wfile.write(bytes("Invalid command",'utf-8'))

        except Exception as e:
            logging.exception("Error processing HTTP request: " + str(e))

class ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer): 
     pass 

logging.info('Initializing Piputer')

#Setup and start http server
httpServer = ThreadedTCPServer(("", http_port), GetHandler)
http_server_thread = threading.Thread(target=httpServer.serve_forever) 
http_server_thread.daemon = True 
http_server_thread.start() 

#Initialize counter for checks during infinite run loop
current_count = 0

logging.info('Beginning Piputer loop')

#Program loop to send status events to SmartThings
while True:
    try:
        #Check if time to update all Piputer statuses
        if any(update_frequency_accelerated_counts) or current_count >= smartthings_update_frequency / smartthings_accelerated_update_frequency:
            requests.put(smartthings_all_pc_statuses_event_url, data=get_all_pc_statuses_json())
            print("All PC statuses event")
            
            #Update accelerated flag and counter
            for index, accelerated_count in enumerate(update_frequency_accelerated_counts):
                if accelerated_count >= smartthings_accelerated_update_count:
                    update_frequency_accelerated_counts[index] = 0
                elif accelerated_count > 0:
                    update_frequency_accelerated_counts[index] = accelerated_count + 1
            
            current_count = 0

        #Wait for next loop
        time.sleep(smartthings_accelerated_update_frequency)
        current_count = current_count + 1

    #Handle all errors so alarm loop does not end
    except Exception as e:
        logging.exception("Error in loop: " + str(e))
    
logging.info('Exited Piputer loop and shutting down')

#Close down HTTP server
httpServer.shutdown()
httpServer.server_close()
