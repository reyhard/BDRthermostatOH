from BdrAPI import BdrAPI
from const import *

import click
import asyncio
#from config_schema import CONF_PAIR_CODE, CONF_BRAND
from functools import wraps
from openhab import OpenHAB
import __main__ as main

base_url = 'http://openhab:8080/rest'

def coro(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        return asyncio.run(f(*args, **kwargs))

    return wrapper

async def get_api():
    print("init data")
    api = BdrAPI(
        "anfiertjew@gmail.com",
        "ky7@9ddXH#",
        "652467576",
        "remeha",
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
    item_currentTemperature = openhab.get_item('Thermostat_Temperature')
    
    mode = resp.get("mode","")
    item_mode.update(str(mode))

    # Get data for next switch
    if(mode == "schedule"):
        nextSwitch = resp.get("nextSwitch")
        timeChange = nextSwitch.get("time",None)
        dayOffset = nextSwitch.get("dayOffset",None)
        temperature = nextSwitch.get("roomTemperatureSetpoint",{}).get("value",None)

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

@cli.command()
@coro
@click.option('--mode',
              required=True,
              default=None,
              help=(('Switch to selected heating program'
                     'Manual override')))
async def set_schedule(mode):
    api = await get_api()
    await api.set_schedulemode(mode)

@cli.command()
@coro
async def get_water_mode():
    api = await get_api()
    resp = await api.get_water_mode()
    
    openhab = OpenHAB(base_url,None, None, None, 1)
    item_mode = openhab.get_item('Thermostat_Water_Mode')
    mode = resp.get("mode","")
    item_mode.update(str(mode))

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
        await api.set_water_mode_comfort()
    elif mode == "comfort":
        await api.set_water_mode_reduced()

@cli.command()
@click.option('--value',
              required=True,
              default=None,
              help=(('Target temperature in degrees, '
                     'Manual override')))
@coro
async def set_temperature(value):
    api = await get_api()
    await api.set_override_temperature(value)


#asyncio.run(set_temperature(16))

#loop = asyncio.get_event_loop()
#loop.run_until_complete(main())
#loop.close()

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