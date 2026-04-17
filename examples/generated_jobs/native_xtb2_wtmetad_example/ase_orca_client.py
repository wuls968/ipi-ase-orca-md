from ase.calculators.orca import ORCA, OrcaProfile
from ase.calculators.socketio import SocketClient
from ase.io import read

profile = OrcaProfile(command='orca')
calc = ORCA(
    profile=profile,
    directory='orca_native_xtb2',
    charge=0,
    mult=1,
    orcasimpleinput='Native-XTB2 Engrad',
    orcablocks='%pal nprocs 1 end\n%maxcore 1000',
)
atoms = read('init.xyz')
atoms.calc = calc
client = SocketClient(unixsocket='orca_driver')
client.run(atoms)
