from BdrAPI import BdrAPI, get_config
from const import *

import click
import asyncio
#from config_schema import CONF_PAIR_CODE, CONF_BRAND
from functools import wraps
from openhab import OpenHAB
import __main__ as main
import time
from datetime import datetime, timedelta, date
import json
import sys

settings = get_config(sys.path[0])
base_url = settings['Openhab'].get('openhab_url','')

def coro(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        return asyncio.run(f(*args, **kwargs))

    return wrapper

def datetime_to_string(timestamp, dt_format='%Y-%m-%d %H:%M:%S'):
    """
    Format datetime object to string
    """
    return timestamp.strftime(dt_format)


def simple_time(value):
    """
    Format a datetime or timedelta object to a string of format HH:MM
    """
    if isinstance(value, timedelta):
        return ':'.join(str(value).split(':')[:2])
    return datetime_to_string(value, '%H:%M')

async def get_api():
    #print("init data")
    api = BdrAPI(
        settings['General'].get('email',''),
        settings['General'].get('password',''),
        settings['General'].get('pairing',''),
        settings['General'].get('device',''),
    )
    await api.bootstrap()

    return api

## Main program
@click.group()
def cli():
    """
    BDR Thermea API
    """
    pass

@cli.command()
@coro
async def get_status():
    print("get status")
    api = await get_api()
    resp = await api.get_status()

    # Setup openhab items
    openhab = OpenHAB(base_url,None, None, None, 1)
    item_mode = openhab.get_item('Thermostat_Mode')
    item_program = openhab.get_item('Thermostat_Program')
    item_nextSwitchDate = openhab.get_item('Thermostat_NextSwitch_Time')
    item_nextSwitchTemperature = openhab.get_item('Thermostat_NextSwitch_Temperature')
    item_currentTemperature = openhab.get_item('Thermostat_Temperature')
    item_flowTemperature = openhab.get_item('Thermostat_FlowTemperature')
    
    mode = resp.get("mode","")
    item_mode.update(str(mode))

    # Get data for next switch
    if(mode == "schedule"):
        nextSwitch = resp.get("nextSwitch")
        timeChange = nextSwitch.get("time",None)
        dayOffset = nextSwitch.get("dayOffset",0)
        endtime = str(date.today() + timedelta(days=dayOffset)) +" "+timeChange
        temperature = nextSwitch.get("roomTemperatureSetpoint",{}).get("value",None)
        item_nextSwitchDate.update(endtime)
        item_nextSwitchTemperature.update(temperature)

    if(mode == "temporary-override"):
        nextSwitch = resp.get("temporaryOverrideEnd")
        item_nextSwitchDate.update(nextSwitch)

    # Get current temperature
    currentTemperature = resp.get("roomTemperature",{}).get("value",None)
    item_currentTemperature.update(currentTemperature)

    # Get current program
    program = resp.get("timeProgram",1)
    item_program.update(str(program))

    print(resp)

    # Get current water mode
    resp = await api.get_water_mode()
    
    openhab = OpenHAB(base_url,None, None, None, 1)
    item_waterMode = openhab.get_item('Thermostat_Water_Mode')
    mode = resp.get("mode","")
    item_waterMode.update(str(mode))
    print(resp)

    # Get current flow temperature
    resp = await api.get_flow_temperature()
    item_flowTemperature = openhab.get_item('Thermostat_FlowTemperature')
    mode = resp.get("systemFlowTemperature","")
    item_flowTemperature.update(str(mode))
    print(resp)


@cli.command()
@coro
@click.option('--mode',
              required=True,
              default=None,
              help=(('Switch to selected heating program'
                     'Manual override')))
async def set_schedule(mode):
    api = await get_api()
    await api.set_schedule(mode)

@cli.command()
@coro
async def set_antifrost(mode):
    api = await get_api()
    await api.set_antifrost(mode)

@cli.command()
@coro
async def get_water_mode():
    api = await get_api()
    resp = await api.get_water_mode()
    
    openhab = OpenHAB(base_url,None, None, None, 1)
    item_mode = openhab.get_item('Thermostat_Water_Mode')
    mode = resp.get("mode","")
    item_mode.update(str(mode))
    print(resp)

@cli.command()
@coro
@click.option('--mode',
              required=True,
              default=None,
              help=(('Target temperature in degrees, '
                     'Manual override')))
async def set_water_mode(mode):
    api = await get_api()
    if mode == "anti-frost":
        await api.set_water_mode_reduced()
    elif mode == "comfort":
        await api.set_water_mode_comfort()

@cli.command()
@click.option('--value',
              required=True,
              default=None,
              help=(('Target temperature in degrees, '
                     'Manual override')))
@coro
async def set_temperature(value):
    api = await get_api()
    
    resp = await api.get_status()
    mode = resp.get("mode","")
    if mode == "temporary-override":
        endtime = resp.get("temporaryOverrideEnd")
    elif mode == 'schedule':
        nextSwitch = resp.get("nextSwitch")
        timeChange = nextSwitch.get("time",None)
        dayOffset = nextSwitch.get("dayOffset",0)
        endtime = str(date.today() + timedelta(days=dayOffset)) +"T"+timeChange
    #print(endtime)
    await api.set_override_temperature(value,endtime)
    print("temperature changed to " + str(value))

@cli.command()
@click.option('--day',
              required=False,
              default="monday",
              help=(('Day to modify, '
                     'Day of the week in format monday, tuesday, wednesday, etc')))
@click.option('--schedule',
              required=False,
              default=None,
              help=(('Schedule for selected day, '
                     'Array of activities')))
@coro
async def set_time_program(day,schedule):
    api = await get_api()
    
    schedule = []

    openhab = OpenHAB(base_url,None, None, None, 1)
    item_alarm = openhab.get_item('Phone_01_AlarmClockDate')
    try:
        alarm_time = datetime.strptime(item_alarm.state,"%Y-%m-%d %H:%M")
        alarm_max = alarm_time.replace(hour=12, minute=0)
        if(alarm_time < alarm_max):
            day = alarm_time.strftime("%A").lower()
            heating_start = alarm_time.strftime("%H:%M")
            # If its HO day, then keep heating on for longer time (4 hours)
            item_ho_day = openhab.get_item('HO_01_' + day.capitalize())
            print(day)
            heating_duration = 10
            if(item_ho_day.state == 'ON'):
                heating_duration = 60*4
            heating_end = (alarm_time + timedelta(minutes=heating_duration)).strftime("%H:%M")
            

            resp = await api.get_time_programs()
            print(resp.get('heating',{}).get("1",{}).get(day))

            schedule = schedule + [
                {
                    "time": heating_start,
                    "activity": 2
                },
                {
                    "time": heating_end,
                    "activity": 4
                }
            ]
        else:
            print("alarm late")
    except:
        print("no alarm #1")
        
    item_alarm2 = openhab.get_item('Phone_02_AlarmClockDate')
    try:
        alarm_time2 = datetime.strptime(item_alarm2.state,"%Y-%m-%d %H:%M")
        if(alarm_time < alarm_max):
            print("ok")
    except:
        print("no alarm #2")
        
    schedule = schedule + [
        {
            "time": "17:20",
            "activity": 2
        },
        {
            "time": "21:00",
            "activity": 4
        }
    ]
    #schedule = json.dumps(schedule)
    print(schedule)
    await api.set_time_program("1",day,schedule)

if not hasattr(main, '__file__'):
    """
    Running in interactive mode in the Python shell
    """
    print("Running interactively in Python shell")

elif __name__ == '__main__':
    """
    CLI mode
    """
    cli()