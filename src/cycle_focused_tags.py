import sys
from pywayland.client import Display
from pywayland.protocol.wayland import WlOutput
from pywayland.protocol.wayland import WlSeat
try:
    from pywayland.protocol.river_control_unstable_v1 import ZriverControlV1
    from pywayland.protocol.river_status_unstable_v1 import ZriverStatusManagerV1
    from pywayland.protocol.river_status_unstable_v1 import ZriverOutputStatusV1
    from pywayland.protocol.river_status_unstable_v1 import ZriverSeatStatusV1
except:
    errtext='''
    Your pywayland package does not have bindings for river-control-unstable-v1
    and/or river-status-unstable-v1.
    These bindings can be generated with the following command:

    python3 -m pywayland.scanner -i /usr/share/wayland/wayland.xml /usr/share/river-protocols/river-control-unstable-v1.xml  /usr/share/river-protocols/river-status-unstable-v1.xml

    Adjust the path of /usr/share/river-protocols/ as approriate for your installation.
'''

    print(errtxt)
    quit()

status_manager = None
control = None

outputs = []
seat = None

class Output(object):
    def __init__(self):
        self.wl_output = None
        self.focused_tags = None
        self.status = None

    def destroy(self):
        if self.wl_output is not None:
            self.wl_output.destroy()
        if self.status is not None:
            self.status.destroy()

    def configure(self):
        global status_manager
        self.status = status_manager.get_river_output_status(self.wl_output)
        self.status.user_data = self
        self.status.dispatcher["focused_tags"] = self.handle_focused_tags

    def handle_focused_tags(self, output_status, tags):
        self.focused_tags = tags

class Seat(object):
    def __init__(self):
        self.wl_seat = None
        self.status = None
        self.focused_output = None

    def destroy(self):
        if self.wl_seat is not None:
            self.wl_seat.destroy()

        if self.status is not None:
            self.status.destroy()

    def configure(self):
        global status_manager
        self.status = status_manager.get_river_seat_status(self.wl_seat)
        self.status.user_data = self
        self.status.dispatcher["focused_output"] = self.handle_focused_output

    def handle_focused_output(self, seat_status, wl_output):
        global outputs
        for output in outputs:
            if output.wl_output == wl_output:
                self.focused_output = output

def registry_handle_global(registry, id, interface, version):
    global status_manager
    global control
    global outputs
    global seat

    if interface == 'zriver_status_manager_v1':
        status_manager = registry.bind(id, ZriverStatusManagerV1, version)
    elif interface == 'zriver_control_v1':
        control = registry.bind(id, ZriverControlV1, version)
    elif interface == 'wl_output':
        output = Output()
        output.wl_output = registry.bind(id, WlOutput, version)
        outputs.append(output)
    elif interface == 'wl_seat':
        # We only care about the first seat
        if seat is None:
            seat = Seat()
            seat.wl_seat = registry.bind(id, WlSeat, version)


USAGE='''usage: cycle-focused-tags [DIRECTION] [NTAGS]

Change to either the next or previous focused tags.

The DIRECTION argument shold be either 'next' or 'previous'.  The
NTAGS argument indicates at which tag number the cycling should loop
back to the first tag or to the last tag from the first tag.

If NTAGS is ommiteed, 32 is assumed if both arguments are ommitted
'next' is used as the DIRECTION.
'''

def main():
    n_tags = 32
    direction = 'next'

    if len(sys.argv) > 1:
        direction = sys.argv[1]

    if len(sys.argv) > 2:
        n_tags = int(sys.argv[2])

    if direction in ('-h', '--help'):
        print(USAGE)
        sys.exit(0)
    
    display = Display()
    display.connect()

    registry = display.get_registry()
    registry.dispatcher["global"] = registry_handle_global

    display.dispatch(block=True)
    display.roundtrip()

    if status_manager is None:
        print("Failed to bind river status manager")
        quit()

    if control is None:
        print("Failed to bind river control")
        quit()

    # Configuring all outputs, even the ones we do not care about, should be faster
    # than first waiting for river to advertise the focused output of the seat.
    for output in outputs:
        output.configure()

    seat.configure()

    display.dispatch(block=True)
    display.roundtrip()
    tags = seat.focused_output.focused_tags

    if direction == 'next':
        mask = (1<< (n_tags-1) )
        wrap = ( (tags & mask) != 0 )
        #If highest bit (last tag) is set => unset it
        if wrap:
            tags ^= mask

        new_tags = (tags << 1)

        # If highest bit was set => set lowest bit to wrap to first tag
        if wrap:
            new_tags |= 1

    else:
        wrap = ((tags & 1) != 0)
        # If lowest bit is set (first tag) => unset it
        if wrap:
            tags ^= 1

        new_tags = (tags >> 1)

        # If lowest bit was set => set highest bit to wrap to last tag
        if wrap:
            mask = (1<< (n_tags-1) )
            new_tags |= mask

    control.add_argument("set-focused-tags")
    control.add_argument( str(new_tags) )
    control.run_command(seat.wl_seat)

    display.dispatch(block=True)
    display.roundtrip()

    seat.destroy()
    for output in outputs:
        output.destroy()

    if status_manager is not None:
        status_manager.destroy()


    if control is not None:
        control.destroy()

    display.disconnect()

if __name__ == '__main__':
    main()
