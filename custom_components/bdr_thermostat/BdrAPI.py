import requests
from typing import cast
from const import *
import logging
from configparser import ConfigParser
import sys
import os

def get_config(config_dir):
    # Load configuration file
    config = ConfigParser(delimiters=('=', ))
    config.optionxform = str
    config.read([os.path.join(config_dir, 'config.ini.dist'), os.path.join(config_dir, 'config.ini')])
    return config

_LOGGER = logging.getLogger(__name__)
settings = get_config(sys.path[0])

class BdrAPI:
    BASE_URL = "https://ruapi.remoteapp.bdrthermea.com/v1.0"
    BASE_HEADER = {
        "Accept": "application/json, text/plain, */*",
        "Connection": "keep-alive",
        "X-Requested-With": "com.bdrthermea.roomunitapplication.remeha",
        "Content-Type": "application/json;charset=UTF-8",
        "Sec-Fetch-Site": "cross-site",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Dest": "empty",
        "Accept-Encoding": "gzip, deflate",
        "Authorization": "Basic cnVhcHA6V25AW1tjJF1QfjghM2AoW35BZiUnSDI/bEh3XWNpaXE6cn1MT3pqTGsueTVNSCtfcT0=",
    }
    endpoints = {
        "PAIR": BASE_URL + "/pairings",
        "CONNECTION": BASE_URL + "/system/gateway/connection",
        "CAPABILITIES": BASE_URL + "/capabilities",
    }
    capabilities = {}

    def __init__(self, user, password, pairing_code, brand: str):
        self._brand = brand
        self._bootstraped = False
        self._user = user
        self._password = password
        self._pairing_code = pairing_code

    async def bootstrap(self):
        if self._bootstraped:
            return
        if not await self._load_stored_token() or not await self.connection_status():
            await self._login()
            await self._pair()

        await self._load_capabilities()
        await self._load_device_information()
        self._bootstraped = True

    async def _load_stored_token(self):
        #data = await self.hass_storage.async_load()
        self.token = settings['General'].get('token','')
        #data.get("token", None) if data else None
        return bool(self.token)

    async def _store_token(self, token):
        data = {"token": token}
        settings['General']['token'] = token
        with open('example.ini', 'w') as configfile:
            settings.write(configfile)
        #await self.hass_storage.async_save(data)
        #print(token)
        self.token = token

    async def _login(self):
        api_endpoint = f"https://remoteapp.bdrthermea.com/user/{self._brand}/login"

        payload = {
            "username": self._user,
            "password": self._password,
        }

        response = await self.async_post_request(endpoint=api_endpoint, payload=payload)
        if not response:
            logging.error('ERROR logging to BDR. Perhaps wrong password??')
            raise Exception('ERROR logging to BDR. Perhaps wrong password??')
        self.amdatu_token = response.headers.get("amdatu_token")

    async def _pair(self):
        api_endpoint = self.endpoints["PAIR"]
        payload = {
            "account": self._user,
            "brand": self._brand,
            "password": self._password,
            "device": "OpenHAB",
            "otp": self._pairing_code,
        }

        response = await self.async_post_request(endpoint=api_endpoint, payload=payload)

        if not response:
            logging.error('Error pairing integration with BDR')
            raise Exception('Error pairing integration with BDR')

        token = response.json().get("token", None)
        await self._store_token(token)

    def _sync_request(self, request, url, headers, payload=None):
        try:
            if request == "get":
                response = requests.get(url=url, headers=headers)
                #print(response.json().get('status'))
            elif request == "put":
                response = requests.put(url=url, json=payload, headers=headers)
            elif request == "post":
                response = requests.post(url=url, json=payload, headers=headers)
        except Exception as e:
            _LOGGER.exception(f"EXCEPTION with {request} request to {url}:", e)
            raise e
        if not response.ok:
            _LOGGER.error(
                f"ERROR with {request} request to {url}: {response.status_code}"
            )
            return None
        try:
            response = response.json()
            #print(response)
        except:
            return None
        return response

    async def async_post_request(self, endpoint, payload, headers=BASE_HEADER):

        return self._sync_request("post", endpoint, headers, payload)
        return await self.hass.async_add_executor_job(
            self._sync_request, "post", endpoint, headers, payload
        )

    async def async_put_request(self, endpoint, payload, headers=BASE_HEADER):

        headers = headers.copy()
        headers["X-Bdr-Pairing-Token"] = self.token

        return self._sync_request("put", endpoint, headers, payload)
        return await self.hass.async_add_executor_job(
            self._sync_request, "put", endpoint, headers, payload
        )

    async def async_get_request(self, endpoint, headers=BASE_HEADER):

        headers = headers.copy()
        headers["X-Bdr-Pairing-Token"] = self.token

        return self._sync_request("get", endpoint, headers)
        response = await self.hass.async_add_executor_job(
            self._sync_request, "get", endpoint, headers
        )

        return response.json() if response else response

    async def connection_status(self):
        api_endpoint = self.endpoints["CONNECTION"]

        response = await self.async_get_request(api_endpoint)
        #print("response " + str(response))
        return response and response.get("status") == "connected_to_appliance"

    async def _load_capabilities(self):
        api_endpoint = self.endpoints["CAPABILITIES"]

        capabilities = await self.async_get_request(api_endpoint)
        #print("capabilities " + str(capabilities))

        for subsystem_name, subsystem in capabilities.items():
            if isinstance(subsystem, list):
                if len(subsystem) > 0:
                    subsystem = subsystem[0]
                else:
                    continue
            self.capabilities[subsystem_name] = {}
            for function, uri in subsystem.items():
                self.capabilities[subsystem_name][function] = self.BASE_URL + str(uri)

    def is_feature_enabled(self, feature):
        if feature == FEATURE_OPERATING_MODE:
            return (
                self.capabilities.get("system", {}).get("operatingModeUri", None)
                is not None
            )
        elif feature == FEATURE_ENERGY_CONSUMPTION:
            return (
                self.capabilities.get("producers", {}).get("energyConsumptionUri", None)
                is not None
            )
        else:
            logging.warning(f"Feature {feature} not enable")
        return False

    async def _load_device_information(self):
        api_endpoint = self.capabilities["system"]["deviceInformationUri"]

        self.info = await self.async_get_request(api_endpoint)

    async def get_operating_mode(self):
        api_endpoint = self.capabilities["system"]["operatingModeUri"]

        return await self.async_get_request(api_endpoint)

    def get_device_information(self):
        return self.info

    def is_bootstraped(self):
        return self._bootstraped

    async def get_status(self):
        #api_endpoint = self.capabilities["centralHeatingZones"]["statusUri"]        
        api_endpoint = self.capabilities["centralHeatingZones"]["uri"] + "/status"  # EDITED FOR REMEHA eTWIST
        return await self.async_get_request(api_endpoint)

    async def set_target_temperature(self, target_temp):
        api_endpoint = self.capabilities["centralHeatingZones"]["putSetpointManualUri"]
        payload = {
            "roomTemperatureSetpoint": target_temp,
        }
        return await self.async_put_request(api_endpoint, payload)

    async def set_override_temperature(self, target_temp, override_end):
        api_endpoint = self.capabilities["centralHeatingZones"][
            "putSetpointTemporaryOverrideUri"
        ]
        payload = {
            "roomTemperatureSetpoint": target_temp,
            "temporaryOverrideEnd": override_end,
        }
        return await self.async_put_request(api_endpoint, payload)

    async def set_schedule(self, schedule_program):
        api_endpoint = self.capabilities["centralHeatingZones"][
            "putSetpointScheduleUri"
        ]
        payload = {
            "currentHeatingTimeProgram": schedule_program,
        }
        return await self.async_put_request(api_endpoint, payload)
        
    async def set_antifrost(self, mode):
        api_endpoint = self.capabilities["centralHeatingZones"][
            "putSetpointAntiFrostUri"
        ]
        payload = {
            "mode": mode,
        }
        return await self.async_put_request(api_endpoint, payload)

    async def set_water_mode_reduced(self):
        api_endpoint = self.capabilities["domesticHotWaterZones"][
            "putSetpointReducedUri"
        ]
        payload = {
        }
        return await self.async_put_request(api_endpoint, payload)
        
    async def set_water_mode_comfort(self):
        api_endpoint = self.capabilities["domesticHotWaterZones"][
            "putSetpointComfortUri"
        ]
        payload = {
        }
        return await self.async_put_request(api_endpoint, payload)

    async def get_water_mode(self):
        api_endpoint = self.capabilities["domesticHotWaterZones"]["uri"] + "/setpoint"  # EDITED FOR REMEHA eTWIST
        return await self.async_get_request(api_endpoint)

    async def set_time_program(self, program, day, schedule):
        api_endpoint = self.capabilities["centralHeatingZones"][
            "timeProgramsUri"
        ]
        payload = {
            "heating": {
                program: {
                day:  schedule     
                }
            }
        }
        print(payload)
        return await self.async_put_request(api_endpoint, payload)


    async def get_time_programs(self):
        api_endpoint = self.capabilities["centralHeatingZones"]["timeProgramsUri"]

        return await self.async_get_request(api_endpoint)


    async def set_operating_mode(self, mode):
        #api_endpoint = self.capabilities["system"]["operatingModeUri"]
        #print(api_endpoint)
        #payload = {
        #    "mode": mode,
        #}
        #return await self.async_put_request(api_endpoint, payload)
        return

    async def set_history(self,address):
        api_endpoint = "https://remoteapp.bdrthermea.com" + "/history/register"
        payload = {
            "address": address
        }
        print(payload)
        return await self.async_put_request(api_endpoint, payload)

    async def get_history(self,address):
        api_endpoint = "https://remoteapp.bdrthermea.com" + "/history/"+address+"/query?type=heating&from=2022-11-14&to=2022-11-20&groupBy=DAY"
        #api_endpoint = "https://remoteapp.bdrthermea.com" + "/history/register"
        #api_endpoint = "https://remoteapp.bdrthermea.com" + "/user/remeha/current"
        #api_endpoint = self.capabilities["system"]["errorStatusUri"]
        print(api_endpoint)

        return await self.async_get_request(api_endpoint)

    async def get_consumptions(self):
        api_endpoint = self.capabilities["producers"]["energyConsumptionUri"]

        return await self.async_get_request(api_endpoint)

    async def get_water_pressure(self):
        api_endpoint = self.capabilities["system"]["waterPressureUri"]

        return await self.async_get_request(api_endpoint)
    
    async def get_errors(self):
        api_endpoint = self.capabilities["system"]["errorStatusUri"]

        return await self.async_get_request(api_endpoint)

    async def get_flow_temperature(self):
        api_endpoint = self.capabilities["system"]["flowTemperatureUri"]

        return await self.async_get_request(api_endpoint)
