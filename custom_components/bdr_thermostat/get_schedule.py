from BdrAPI import BdrAPI, get_config
from const import *

import click
import asyncio
from functools import wraps
from openhab import OpenHAB
import __main__ as main

def coro(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        return asyncio.run(f(*args, **kwargs))
    return wrapper


## Main program
@click.group()
def cli():
    """
    Clock params
    """
    pass

  
@cli.command()
@coro
async def get_schedule(date):
  data = {'monday': [{'time': '07:30', 'activity': 2}, {'time': '13:00', 'activity': 4}, {'time': '17:20', 'activity': 2}, {'time': '21:00', 'activity': 4}], 'tuesday': [{'time': '07:00', 'activity': 2}, {'time': '07:10', 'activity': 4}, {'time': '17:20', 'activity': 2}, {'time': '21:00', 'activity': 4}], 'wednesday': [{'time': '07:00', 'activity': 2}, {'time': '07:10', 'activity': 4}, {'time': '17:20', 'activity': 2}, {'time': '21:00', 'activity': 4}], 'thursday': [{'time': '07:00', 'activity': 2}, {'time': '07:10', 'activity': 4}, {'time': '17:20', 'activity': 2}, {'time': '21:00', 'activity': 4}], 'friday': [{'time': '07:00', 'activity': 2}, {'time': '07:10', 'activity': 4}, {'time': '17:20', 'activity': 2}, {'time': '21:00', 'activity': 4}], 'saturday': [{'time': '17:20', 'activity': 2}, {'time': '21:00', 'activity': 4}], 'sunday': [{'time': '08:00', 'activity': 2}, {'time': '13:30', 'activity': 4}, {'time': '21:00', 'activity': 4}]}
  

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