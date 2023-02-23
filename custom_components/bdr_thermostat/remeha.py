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

HISTORY_ADDRESS = "4aade00c-c738-4dfe-8ff6-c39c5984da75"

def coro(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        return asyncio.run(f(*args, **kwargs))

    return wrapper

def string_to_time(string):
  return time.strptime(string,"%H:%M")

def add_values(amount, val):
    array = []
    for i in range(0, amount):
        array = array + [val]
    return array

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
    item_currentSetpoint = openhab.get_item('Thermostat_TemperatureControl')
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
        item_nextSwitchDate.update(nextSwitch.replace("T"," "))

    # Get current temperature
    currentTemperature = resp.get("roomTemperature",{}).get("value",None)
    item_currentTemperature.update(currentTemperature)
    
    # Get current setpoint
    currentSetpointTemperature = resp.get("roomTemperatureSetpoint",{}).get("value",None)
    item_currentSetpoint.update(currentSetpointTemperature)

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
async def get_schedule():
    api = await get_api()
    resp = await api.get_time_programs()
    #program = {'monday': [{'time': '07:30', 'activity': 2}, {'time': '13:00', 'activity': 4}, {'time': '17:20', 'activity': 2}, {'time': '21:00', 'activity': 4}], 'tuesday': [{'time': '07:00', 'activity': 2}, {'time': '07:10', 'activity': 4}, {'time': '17:20', 'activity': 2}, {'time': '21:00', 'activity': 4}], 'wednesday': [{'time': '07:00', 'activity': 2}, {'time': '07:10', 'activity': 4}, {'time': '17:20', 'activity': 2}, {'time': '21:00', 'activity': 4}], 'thursday': [{'time': '07:00', 'activity': 2}, {'time': '07:10', 'activity': 4}, {'time': '17:20', 'activity': 2}, {'time': '21:00', 'activity': 4}], 'friday': [{'time': '07:00', 'activity': 2}, {'time': '07:10', 'activity': 4}, {'time': '17:20', 'activity': 2}, {'time': '21:00', 'activity': 4}], 'saturday': [{'time': '17:20', 'activity': 2}, {'time': '21:00', 'activity': 4}], 'sunday': [{'time': '08:00', 'activity': 2}, {'time': '13:30', 'activity': 4}, {'time': '21:00', 'activity': 4}]}
    program = resp.get("heating").get("1")
    days = ('monday','tuesday','wednesday','thursday','friday','saturday','sunday')
    index = 1
    data = {}
    activity = 0
    for day in days:
        blocks = program.get(day)
        value_array = []
        time_prev = time.gmtime(0)
        round_result = 0
        for block in blocks:
            time_string = block.get('time')
            time_val = string_to_time(time_string) 
            time_val_blocks_pre = (time_val[3] - time_prev[3] + (time_val[4]-time_prev[4])/60)*4
            time_val_blocks = round(round_result + time_val_blocks_pre)
            round_result = time_val_blocks_pre - time_val_blocks
            time_prev = time_val
            value_array = value_array + add_values(time_val_blocks,activity)
            #print(time_val_blocks)
            activity = block.get('activity')
            if(activity == 2): 
                activity = 1
            else:
                activity= 0
        value_array = value_array + add_values(96-len(value_array),activity)
        #print(len(value_array))

        data.update({str(index):
            {
                "key":str(index),
                "value":value_array
            }
        })
        index += 1
    data.update({
        "99":"noc,dzień","100":{"event":False,"lastItemState":-1,"inactive":False}
    })
    # data in format of timeline picker
    # https://community.openhab.org/t/timeline-picker-to-setup-heating-light-and-so-on/55564
    data_str = str(data).replace("'",'"').replace("False","false").replace(" ","")
    openhab = OpenHAB(base_url,None, None, None, 1)
    item_schedule = openhab.get_item('TransferItem1')
    item_schedule.update(data_str)
    #print(data_str)

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
@click.option('--mode',
              required=True,
              default=None,
              help=(('Switch to anti frost'
                     'Antifrost mode')))
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
              help=(('Set water mode - always eco or hot, '
                     'anti-frost or comfort')))
async def set_water_mode(mode):
    api = await get_api()
    if mode == "anti-frost":
        await api.set_water_mode_reduced()
    elif mode == "comfort":
        await api.set_water_mode_comfort()

def statistics_to_openhab(openhab,item_name,data):
    value = data[0].get('value')
    item_daily = openhab.get_item(item_name + '_Daily')
    item_hourly = openhab.get_item(item_name + '_Hourly')
    use_daily_previous = item_daily.state
    if use_daily_previous is None:
        use_daily_previous = 0
    item_daily.update(value)
    use_hourly = value - use_daily_previous
    item_hourly.update(use_hourly)


@cli.command()
@click.option('--datefrom',
              required=True,
              default=None,
              help=(('Get heating history from selected date, '
                     'Data in format YYYY-MM-DD')))
@click.option('--dateto',
              required=False,
              default=None,
              help=(('Get heating history from selected date, '
                     'Data in format YYYY-MM-DD')))
@click.option('--type',
              required=False,
              default='both',
              help=(('Data type, '
                     'Can be heating, hotwater or both')))
@coro
async def get_history(datefrom, dateto, type):
    api = await get_api()
    if(dateto is None):
        dateto = datefrom

    openhab = OpenHAB(base_url,None, None, None, 1)
    if(type == 'both'):
        resp = await api.get_history(HISTORY_ADDRESS, datefrom, dateto, 'heating')
        statistics_to_openhab(openhab,'Thermostat_HeatingUsage',resp)
        resp = await api.get_history(HISTORY_ADDRESS, datefrom, dateto, 'hotwater')
        statistics_to_openhab(openhab,'Thermostat_HotWaterUsage',resp)
    else:
        resp = await api.get_history(HISTORY_ADDRESS, datefrom, dateto, type)
    print(resp)

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
              required=True,
              default="monday",
              help=(('Day to modify, '
                     'Day of the week in format monday, tuesday, wednesday, etc')))
@click.option('--schedule',
              required=True,
              default=None,
              help=(('Schedule for selected day, '
                     'Array of activities')))
@coro
async def set_time_program(day,schedule):
    api = await get_api()
    print(schedule)
    await api.set_time_program("1",day,schedule)

async def set_time_program2(day,schedule):
    api = await get_api()
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