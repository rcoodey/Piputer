/**
 *  Piputer
 *
 *  Copyright 2016 Ryan Coodey
 *
 *  Licensed under the Apache License, Version 2.0 (the "License"); you may not use this file except
 *  in compliance with the License. You may obtain a copy of the License at:
 *
 *      http://www.apache.org/licenses/LICENSE-2.0
 *
 *  Unless required by applicable law or agreed to in writing, software distributed under the License is distributed
 *  on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License
 *  for the specific language governing permissions and limitations under the License.
 *
 */
metadata {
    definition (name: "Piputer", namespace: "rcoodey", author: "Ryan Coodey") {
        capability "Switch"
        command "statusEvent"
    }

    tiles {
        standardTile("switch", "device.switch", width: 3, height: 2) {
            state "on", label: 'On', action: "switch.off", icon: "st.Electronics.electronics18", backgroundColor: "#79b821", nextState:"turningOff"
            state "turningOn", label: 'Turning On', icon: "st.Electronics.electronics18", backgroundColor: "#79b821", nextState:"turningOff"
            state "off", label: 'Off', action: "switch.on", icon: "st.Electronics.electronics18", backgroundColor: "#ffffff", nextState:"turningOn"
            state "turningOff", label: 'Turning Off', icon: "st.Electronics.electronics18", backgroundColor: "#ffffff", nextState:"turningOn"
        }
        main(["switch"])
        details(["switch"]) 
    }
}

// handle commands
def statusEvent(state) {
    sendEvent(name: "switch", value: state)
}

def on() {
    changePCPowerState("on")
}

def off() {
    changePCPowerState("off")
}

def changePCPowerState(requestedState)
{
    try {
        log.debug "Turning $requestedState $device.name"
        
        //Get URL command and update button label depending on requested state
        def commandPath = null
        if(requestedState == "on") {
            commandPath = "WakePC"
            sendEvent(name: "switch", value: "turningOn")
        }
        else if (requestedState == "off") {
            commandPath = "ShutdownPC"
            sendEvent(name: "switch", value: "turningOff")
        }
        else
            return
 
        //Setup a hub action to make http request
        def getAction = new physicalgraph.device.HubAction(
            method: "GET",
            path: "/" + commandPath + "/" + device.deviceNetworkId.replace("Piputer", ""),
            headers: [HOST: "192.168.1.4:81"]
        )
        getAction
        //Dont add any code below here, causes the action to not go through for some reason
    } catch (e) {
        log.debug "Error turning $requestedState PC: $e"
    }
}